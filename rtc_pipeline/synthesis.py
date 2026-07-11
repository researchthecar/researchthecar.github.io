from __future__ import annotations

from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import urllib.request
import glob
from typing import Any, Dict, Iterable, List

from rtc_pipeline.io import read_json, write_json, write_text
from rtc_pipeline.models import utc_now_iso
from rtc_pipeline.slug import slugify


SYNTHESIS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["vehicle", "generated_at", "provider", "summary", "issues", "source_ids", "warnings"],
    "properties": {
        "vehicle": {"type": "object"},
        "generated_at": {"type": "string"},
        "provider": {"type": "string"},
        "summary": {"type": "string"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["category", "title", "summary", "evidence_ids", "confidence"],
                "properties": {
                    "category": {"type": "string"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "additionalProperties": False,
            },
        },
        "source_ids": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}


def ready_paths_from_quality_report(quality_path: Path, limit: int | None = None) -> List[Path]:
    quality = read_json(quality_path)
    paths = [
        Path(vehicle["normalized_path"])
        for vehicle in quality.get("vehicles", [])
        if vehicle.get("status") == "ready_for_synthesis"
    ]
    return paths[:limit] if limit is not None else paths


def synthesize_ready_group(
    quality_path: Path = Path("data/rendered/pilot_quality_report.json"),
    provider_name: str = "draft",
    limit: int | None = None,
) -> List[Path]:
    output_paths = []
    for normalized_path in ready_paths_from_quality_report(quality_path, limit):
        report_path = synthesize_file(normalized_path, provider_name=provider_name)
        output_paths.append(report_path)
    return output_paths


def synthesize_file(normalized_path: Path, provider_name: str = "draft") -> Path:
    payload = read_json(normalized_path)
    provider = provider_for_name(provider_name)
    report = provider.synthesize(payload)
    validate_synthesis_report(report)
    output_path = Path("data/reports") / f"{payload['vehicle']['slug']}.json"
    write_json(output_path, report)
    return output_path


def provider_for_name(provider_name: str) -> "SynthesisProvider":
    if provider_name == "draft":
        return DraftSynthesisProvider()
    if provider_name == "gemini":
        return GeminiSynthesisProvider()
    raise ValueError(f"Unknown synthesis provider: {provider_name}")


class SynthesisProvider:
    name = "base"

    def synthesize(self, normalized: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class DraftSynthesisProvider(SynthesisProvider):
    name = "draft"

    def synthesize(self, normalized: Dict[str, Any]) -> Dict[str, Any]:
        evidence = normalized.get("evidence", [])
        vehicle = normalized["vehicle"]
        issues = draft_issues(evidence)
        summary = draft_summary(vehicle, normalized.get("source_counts", {}), issues)
        return {
            "vehicle": vehicle,
            "generated_at": utc_now_iso(),
            "provider": self.name,
            "summary": summary,
            "issues": issues,
            "source_ids": source_ids_from_issues(issues, evidence),
            "warnings": [
                "Draft provider uses deterministic evidence grouping, not an LLM. Use for pipeline validation only."
            ],
        }


class GeminiSynthesisProvider(SynthesisProvider):
    name = "gemini"

    def __init__(self) -> None:
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required for provider=gemini")

    def synthesize(self, normalized: Dict[str, Any]) -> Dict[str, Any]:
        prompt = build_prompt(normalized)
        body = {
            "model": self.model,
            "system_instruction": (
                "You write used-car reliability summaries from provided evidence only. "
                "Do not add claims that are not supported by the supplied evidence IDs."
            ),
            "input": prompt,
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": SYNTHESIS_SCHEMA,
            },
        }
        request = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
        output_text = data.get("output_text", "")
        if not output_text:
            output_text = extract_interaction_text(data)
        report = json.loads(output_text)
        report["provider"] = self.name
        report.setdefault("generated_at", utc_now_iso())
        return report


def draft_issues(evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_category: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in evidence:
        by_category[item.get("category", "other")].append(item)

    category_counts = Counter({category: len(items) for category, items in by_category.items()})
    issues = []
    for category, _count in category_counts.most_common(6):
        if category == "other":
            continue
        items = by_category[category]
        components = Counter(item.get("component", "Unknown component") for item in items)
        recall_count = sum(1 for item in items if item.get("source_type") == "recall")
        complaint_count = sum(1 for item in items if item.get("source_type") == "complaint")
        representative = select_representative_evidence(items)
        confidence = "high" if recall_count and complaint_count >= 20 else "medium" if len(items) >= 20 else "low"
        top_component = components.most_common(1)[0][0]
        issues.append(
            {
                "category": category,
                "title": f"{category.replace('_', ' ').title()} concerns around {top_component}",
                "summary": (
                    f"NHTSA evidence includes {complaint_count} complaint records and {recall_count} recall records "
                    f"in this category. The most common component label is '{top_component}'."
                ),
                "evidence_ids": [item["evidence_id"] for item in representative],
                "confidence": confidence,
            }
        )
    return issues


def select_representative_evidence(items: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    recalls = [item for item in items if item.get("source_type") == "recall"]
    complaints = [item for item in items if item.get("source_type") == "complaint"]
    selected = recalls[:2] + complaints[: max(0, limit - min(2, len(recalls)))]
    return selected[:limit]


def draft_summary(vehicle: Dict[str, Any], source_counts: Dict[str, Any], issues: List[Dict[str, Any]]) -> str:
    issue_names = ", ".join(issue["category"].replace("_", " ") for issue in issues[:4])
    return (
        f"The {vehicle['year']} {vehicle['make']} {vehicle['model']} has "
        f"{source_counts.get('complaint', 0)} NHTSA complaint records and "
        f"{source_counts.get('recall', 0)} recall records in the current evidence set. "
        f"The strongest evidence clusters are: {issue_names or 'none identified'}."
    )


def source_ids_from_issues(issues: List[Dict[str, Any]], evidence: List[Dict[str, Any]]) -> List[str]:
    by_evidence_id = {item.get("evidence_id"): item for item in evidence}
    source_ids = []
    for issue in issues:
        for evidence_id in issue.get("evidence_ids", []):
            source_id = by_evidence_id.get(evidence_id, {}).get("source_id")
            if source_id:
                source_ids.append(source_id)
    return sorted(set(source_ids))


def build_prompt(normalized: Dict[str, Any], max_records: int = 160) -> str:
    vehicle = normalized["vehicle"]
    records = compact_evidence(normalized.get("evidence", []), max_records)
    return json.dumps(
        {
            "task": "Create a structured vehicle reliability report from evidence only.",
            "rules": [
                "Every issue must cite evidence_ids from the provided records.",
                "Use cautious wording. NHTSA complaints are reports, not proof of defects.",
                "Prefer recurring issue clusters over isolated one-off records.",
                "Do not estimate repair costs.",
            ],
            "vehicle": vehicle,
            "source_counts": normalized.get("source_counts", {}),
            "category_counts": normalized.get("category_counts", {}),
            "evidence_records": records,
            "output_schema": SYNTHESIS_SCHEMA,
        },
        indent=2,
        sort_keys=True,
    )


def compact_evidence(evidence: List[Dict[str, Any]], max_records: int) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in evidence:
        grouped[item.get("category", "other")].append(item)

    selected = []
    for _category, items in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
        selected.extend(select_representative_evidence(items, limit=12))
        if len(selected) >= max_records:
            break
    return [
        {
            "evidence_id": item.get("evidence_id"),
            "source_type": item.get("source_type"),
            "source_id": item.get("source_id"),
            "category": item.get("category"),
            "component": item.get("component"),
            "summary": item.get("summary"),
        }
        for item in selected[:max_records]
    ]


def validate_synthesis_report(report: Dict[str, Any]) -> None:
    for key in SYNTHESIS_SCHEMA["required"]:
        if key not in report:
            raise ValueError(f"Synthesis report missing required field: {key}")
    if not isinstance(report.get("issues"), list):
        raise ValueError("Synthesis report issues must be a list")
    source_ids = set(report.get("source_ids", []))
    for index, issue in enumerate(report["issues"]):
        for key in ["category", "title", "summary", "evidence_ids", "confidence"]:
            if key not in issue:
                raise ValueError(f"Synthesis issue {index} missing required field: {key}")
        if issue["confidence"] not in {"high", "medium", "low"}:
            raise ValueError(f"Synthesis issue {index} has invalid confidence: {issue['confidence']}")
        if not issue["evidence_ids"]:
            raise ValueError(f"Synthesis issue {index} must cite evidence IDs")


def extract_interaction_text(data: Dict[str, Any]) -> str:
    texts: List[str] = []
    for step in data.get("steps", []):
        for part in step.get("content", []):
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(part.get("text", ""))
    return "".join(texts)


def render_synthesis_markdown(report_path: Path, output_root: Path = Path("data/rendered/synthesis")) -> Path:
    report = read_json(report_path)
    vehicle = report["vehicle"]
    output_path = output_root / f"{vehicle['slug']}.md"
    lines = [
        f"# {vehicle['year']} {vehicle['make']} {vehicle['model']} Reliability Draft",
        "",
        f"> Provider: `{report.get('provider')}`. Generated: `{report.get('generated_at')}`.",
        "",
        "## Summary",
        "",
        report.get("summary", ""),
        "",
        "## Issues",
        "",
    ]
    for issue in report.get("issues", []):
        lines.extend(
            [
                f"### {issue['title']}",
                "",
                f"- Category: `{issue['category']}`",
                f"- Confidence: `{issue['confidence']}`",
                f"- Evidence: {', '.join(f'`{evidence_id}`' for evidence_id in issue['evidence_ids'])}",
                "",
                issue["summary"],
                "",
            ]
        )
    warnings = report.get("warnings") or []
    if warnings:
        lines.extend(["## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")
    write_text(output_path, "\n".join(lines))
    return output_path


def render_synthesis_reports(report_glob: str = "data/reports/*.json") -> List[Path]:
    return [render_synthesis_markdown(Path(path)) for path in sorted(glob.glob(report_glob))]
