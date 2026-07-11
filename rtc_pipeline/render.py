from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

from rtc_pipeline.io import ensure_object, read_json, write_text
from rtc_pipeline.models import SYSTEM_CATEGORIES


def _markdown_escape(value: Any) -> str:
    text = str(value or "").replace("\n", " ").strip()
    return text.replace("|", "\\|")


def _shorten(text: str, limit: int = 360) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def render_markdown(payload: Dict[str, Any]) -> str:
    vehicle = payload["vehicle"]
    title = f"{vehicle['year']} {vehicle['make']} {vehicle['model']} Reliability Evidence Pilot"
    evidence = payload.get("evidence", [])
    source_counts = Counter(item.get("source_type", "unknown") for item in evidence)
    category_counts = Counter(item.get("category", "other") for item in evidence)
    by_category: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in evidence:
        by_category[item.get("category", "other")].append(item)

    lines: List[str] = [
        "---",
        "layout: post",
        f"title: {title}",
        "categories: [\"Pilot\", \"Evidence\"]",
        f"tags: [\"{vehicle['make']}\", \"{vehicle['model']}\", \"{vehicle['year']}\", \"pilot\"]",
        "---",
        "",
        f"# {title}",
        "",
        "> This is a no-LLM pilot render from normalized source evidence. It is not ready to replace the production page.",
        "",
        "## Evidence Snapshot",
        "",
        f"- Vehicle: **{vehicle['year']} {vehicle['make']} {vehicle['model']}**",
        f"- Normalized evidence records: **{len(evidence)}**",
        f"- NHTSA recalls: **{source_counts.get('recall', 0)}**",
        f"- NHTSA complaints: **{source_counts.get('complaint', 0)}**",
        f"- Generated at: `{payload.get('generated_at', '')}`",
        "",
    ]

    warnings = payload.get("warnings", [])
    if warnings:
        lines.extend(["## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.extend(["## Category Counts", ""])
    if category_counts:
        for category in SYSTEM_CATEGORIES:
            if category_counts.get(category):
                lines.append(f"- **{category.replace('_', ' ').title()}**: {category_counts[category]}")
    else:
        lines.append("- No normalized evidence records found.")
    lines.append("")

    lines.extend(["## Evidence By Category", ""])
    for category in SYSTEM_CATEGORIES:
        items = by_category.get(category, [])
        if not items:
            continue
        lines.extend([f"### {category.replace('_', ' ').title()}", ""])
        components = Counter(item.get("component", "Unknown component") for item in items)
        lines.append("Top components:")
        for component, count in components.most_common(5):
            lines.append(f"- {component}: {count}")
        lines.append("")
        lines.append("| Type | ID | Component | Summary |")
        lines.append("| --- | --- | --- | --- |")
        for item in items[:10]:
            lines.append(
                "| {source_type} | {source_id} | {component} | {summary} |".format(
                    source_type=_markdown_escape(item.get("source_type")),
                    source_id=_markdown_escape(item.get("source_id")),
                    component=_markdown_escape(item.get("component")),
                    summary=_markdown_escape(_shorten(item.get("summary", ""))),
                )
            )
        if len(items) > 10:
            lines.append(f"| ... | ... | ... | {len(items) - 10} more records in normalized JSON |")
        lines.append("")

    lines.extend(["## Source Files", ""])
    raw_inputs = payload.get("raw_inputs", {})
    if raw_inputs:
        for name, path in sorted(raw_inputs.items()):
            lines.append(f"- `{name}`: `{path}`")
    else:
        lines.append("- No raw input files were linked.")
    lines.append("")

    return "\n".join(lines)


def render_normalized_file(input_path: Path, output_root: Path = Path("data/rendered")) -> Path:
    payload = ensure_object(read_json(input_path), input_path)
    vehicle = payload["vehicle"]
    output_path = output_root / f"{vehicle['slug']}.md"
    write_text(output_path, render_markdown(payload))
    return output_path
