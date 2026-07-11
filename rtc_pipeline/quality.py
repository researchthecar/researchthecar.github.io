from __future__ import annotations

from collections import Counter
import glob
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from rtc_pipeline.io import read_json, write_json
from rtc_pipeline.models import utc_now_iso


MIN_READY_EVIDENCE = 25
LOW_EVIDENCE_THRESHOLD = 10
HIGH_COMPLAINT_THRESHOLD = 1500
HIGH_OTHER_RATIO = 0.25
HIGH_UNKNOWN_COMPONENT_RATIO = 0.25
HIGH_CATEGORY_CONCENTRATION = 0.85
MIN_CATEGORY_VARIETY = 2


def build_source_failure_report(
    summary_path: Path = Path("data/rendered/pilot_summary.json"),
    output_path: Path = Path("data/rendered/source_failures.json"),
) -> Dict[str, Any]:
    summary = read_json(summary_path)
    results = summary.get("results", []) if isinstance(summary, dict) else []
    failures: List[Dict[str, Any]] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        source_errors = result.get("source_errors") or {}
        if not source_errors:
            continue
        failures.append(
            {
                "vehicle": result.get("vehicle", {}),
                "source_errors": source_errors,
                "raw_paths": result.get("raw_paths", {}),
                "normalized_path": result.get("normalized_path", ""),
                "rendered_path": result.get("rendered_path", ""),
                "recommended_action": "Patch data/vehicle_registry.json for this vehicle, then rerun the batch.",
            }
        )

    report = {
        "generated_at": utc_now_iso(),
        "summary_path": str(summary_path),
        "failure_count": len(failures),
        "failures": failures,
    }
    write_json(output_path, report)
    return report


def build_quality_report(
    normalized_glob: str = "data/normalized/vehicles/*.json",
    summary_path: Path = Path("data/rendered/pilot_summary.json"),
    output_path: Path = Path("data/rendered/pilot_quality_report.json"),
) -> Dict[str, Any]:
    summary_by_slug = summary_results_by_slug(summary_path)
    vehicle_reports = []
    normalized_paths = normalized_paths_from_summary(summary_by_slug)
    if not normalized_paths:
        normalized_paths = [Path(path) for path in sorted(glob.glob(normalized_glob))]

    for path in normalized_paths:
        payload = read_json(Path(path))
        vehicle_reports.append(score_vehicle_payload(payload, Path(path), summary_by_slug.get(payload["vehicle"]["slug"], {})))

    status_counts = Counter(report["status"] for report in vehicle_reports)
    flag_counts = Counter(flag for report in vehicle_reports for flag in report["flags"])
    report = {
        "generated_at": utc_now_iso(),
        "normalized_glob": normalized_glob,
        "summary_path": str(summary_path),
        "vehicle_count": len(vehicle_reports),
        "status_counts": dict(sorted(status_counts.items())),
        "flag_counts": dict(sorted(flag_counts.items())),
        "thresholds": {
            "min_ready_evidence": MIN_READY_EVIDENCE,
            "low_evidence_threshold": LOW_EVIDENCE_THRESHOLD,
            "high_complaint_threshold": HIGH_COMPLAINT_THRESHOLD,
            "high_other_ratio": HIGH_OTHER_RATIO,
            "high_unknown_component_ratio": HIGH_UNKNOWN_COMPONENT_RATIO,
            "high_category_concentration": HIGH_CATEGORY_CONCENTRATION,
            "min_category_variety": MIN_CATEGORY_VARIETY,
        },
        "vehicles": vehicle_reports,
    }
    write_json(output_path, report)
    return report


def summary_results_by_slug(summary_path: Path) -> Dict[str, Dict[str, Any]]:
    if not summary_path.exists():
        return {}
    summary = read_json(summary_path)
    results = summary.get("results", []) if isinstance(summary, dict) else []
    by_slug = {}
    for result in results:
        if isinstance(result, dict):
            vehicle = result.get("vehicle") or {}
            slug = vehicle.get("slug")
            if slug:
                by_slug[slug] = result
    return by_slug


def normalized_paths_from_summary(summary_by_slug: Dict[str, Dict[str, Any]]) -> List[Path]:
    paths: List[Path] = []
    seen = set()
    for result in summary_by_slug.values():
        normalized_path = result.get("normalized_path")
        if normalized_path and normalized_path not in seen:
            paths.append(Path(normalized_path))
            seen.add(normalized_path)
    return sorted(paths)


def score_vehicle_payload(payload: Dict[str, Any], path: Path, summary_result: Dict[str, Any]) -> Dict[str, Any]:
    evidence = payload.get("evidence", [])
    source_counts = payload.get("source_counts", {})
    category_counts = payload.get("category_counts", {})
    warnings = payload.get("warnings", [])
    flags: List[str] = []
    notes: List[str] = []

    total_evidence = len(evidence)
    complaint_count = int(source_counts.get("complaint", 0))
    recall_count = int(source_counts.get("recall", 0))
    other_count = int(category_counts.get("other", 0))
    populated_categories = sum(1 for count in category_counts.values() if count)
    top_category, top_category_count = top_count(category_counts)
    unknown_component_count = count_unknown_components(evidence)

    if summary_result.get("status") == "source_error" or summary_result.get("source_errors"):
        flags.append("missing_source")
        notes.append("At least one source failed or is missing.")
    if recall_count == 0:
        flags.append("missing_recalls")
    if complaint_count == 0:
        flags.append("missing_complaints")
    if total_evidence < LOW_EVIDENCE_THRESHOLD:
        flags.append("low_evidence")
    elif total_evidence < MIN_READY_EVIDENCE:
        flags.append("thin_evidence")
    if complaint_count > HIGH_COMPLAINT_THRESHOLD:
        flags.append("needs_deduping")
    if ratio(other_count, total_evidence) > HIGH_OTHER_RATIO:
        flags.append("high_other_category_ratio")
    if ratio(unknown_component_count, total_evidence) > HIGH_UNKNOWN_COMPONENT_RATIO:
        flags.append("high_unknown_component_ratio")
    if total_evidence >= MIN_READY_EVIDENCE and ratio(top_category_count, total_evidence) > HIGH_CATEGORY_CONCENTRATION:
        flags.append("category_concentrated")
        notes.append(f"Top category '{top_category}' accounts for most evidence.")
    if populated_categories < MIN_CATEGORY_VARIETY and total_evidence >= MIN_READY_EVIDENCE:
        flags.append("low_category_variety")
    if warnings:
        flags.append("normalization_warnings")

    status = readiness_status(flags, total_evidence)
    return {
        "vehicle": payload.get("vehicle", {}),
        "normalized_path": str(path),
        "status": status,
        "flags": sorted(set(flags)),
        "notes": notes,
        "metrics": {
            "total_evidence": total_evidence,
            "complaints": complaint_count,
            "recalls": recall_count,
            "warnings": len(warnings),
            "populated_categories": populated_categories,
            "top_category": top_category,
            "top_category_count": top_category_count,
            "top_category_ratio": round(ratio(top_category_count, total_evidence), 4),
            "other_category_ratio": round(ratio(other_count, total_evidence), 4),
            "unknown_component_ratio": round(ratio(unknown_component_count, total_evidence), 4),
        },
        "source_errors": summary_result.get("source_errors", {}),
    }


def readiness_status(flags: Iterable[str], total_evidence: int) -> str:
    flag_set = set(flags)
    if "missing_source" in flag_set or "missing_complaints" in flag_set or "missing_recalls" in flag_set:
        return "needs_source_fix"
    if "low_evidence" in flag_set:
        return "low_evidence"
    if "needs_deduping" in flag_set:
        return "needs_deduping"
    if flag_set & {"high_other_category_ratio", "high_unknown_component_ratio"}:
        return "needs_review"
    if total_evidence >= MIN_READY_EVIDENCE:
        return "ready_for_synthesis"
    return "needs_review"


def top_count(counts: Dict[str, Any]) -> Tuple[str, int]:
    if not counts:
        return "", 0
    key, value = max(counts.items(), key=lambda item: int(item[1]))
    return str(key), int(value)


def ratio(numerator: int, denominator: int) -> float:
    return (numerator / denominator) if denominator else 0.0


def count_unknown_components(evidence: List[Dict[str, Any]]) -> int:
    count = 0
    for item in evidence:
        component = str(item.get("component", "")).lower()
        if not component or component == "unknown component" or "unknown or other" in component:
            count += 1
    return count
