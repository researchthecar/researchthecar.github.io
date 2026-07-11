from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from rtc_pipeline.io import ensure_object, read_json
from rtc_pipeline.models import SYSTEM_CATEGORIES


REQUIRED_EVIDENCE_FIELDS = [
    "evidence_id",
    "source_type",
    "source_name",
    "source_id",
    "category",
    "component",
    "title",
    "summary",
    "url",
    "retrieved_at",
    "raw_ref",
]


def validate_normalized_payload(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    vehicle = payload.get("vehicle")
    if not isinstance(vehicle, dict):
        errors.append("vehicle must be an object")
    else:
        for field in ["year", "make", "model", "slug"]:
            if field not in vehicle or vehicle[field] in ("", None):
                errors.append(f"vehicle.{field} is required")

    evidence = payload.get("evidence")
    if not isinstance(evidence, list):
        errors.append("evidence must be a list")
        return errors

    seen_ids = set()
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            errors.append(f"evidence[{index}] must be an object")
            continue
        for field in REQUIRED_EVIDENCE_FIELDS:
            if item.get(field) in ("", None):
                errors.append(f"evidence[{index}].{field} is required")
        evidence_id = item.get("evidence_id")
        if evidence_id in seen_ids:
            errors.append(f"duplicate evidence_id: {evidence_id}")
        seen_ids.add(evidence_id)
        category = item.get("category")
        if category not in SYSTEM_CATEGORIES:
            errors.append(f"evidence[{index}].category is invalid: {category}")
        if item.get("source_type") not in ("recall", "complaint"):
            errors.append(f"evidence[{index}].source_type is invalid: {item.get('source_type')}")
        if item.get("source_name") != "NHTSA":
            errors.append(f"evidence[{index}].source_name must be NHTSA in the first pilot")

    return errors


def validate_normalized_file(path: Path) -> List[str]:
    payload = ensure_object(read_json(path), path)
    return validate_normalized_payload(payload)
