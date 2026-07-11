from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from rtc_pipeline.io import ensure_object, read_json, write_json
from rtc_pipeline.models import EvidenceItem, NormalizedVehicleEvidence, Vehicle, get_first, utc_now_iso


CATEGORY_KEYWORDS: List[Tuple[str, Tuple[str, ...]]] = [
    ("engine", ("engine", "fuel", "cooling", "oil", "exhaust", "vehicle speed control")),
    ("transmission", ("transmission", "automatic transmission", "manual transmission")),
    ("drivetrain", ("power train", "driveline", "differential", "axle", "transfer case")),
    ("safety", ("air bag", "air bags", "seat belt", "forward collision", "lane", "back over prevention")),
    ("steering", ("steering",)),
    ("brakes", ("brake", "service brakes", "parking brake")),
    ("suspension", ("suspension", "wheels", "tires")),
    ("electrical", ("electrical", "battery", "alternator", "starter", "lighting", "software")),
    ("interior", ("seat", "latch", "equipment adaptive", "child seat")),
    ("exterior", ("visibility", "wiper", "glass", "mirror", "door", "latch")),
    ("hvac", ("air conditioner", "heater", "defroster", "hvac")),
    ("body_paint", ("structure", "body", "paint")),
]


def _records(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    response = payload.get("response", payload)
    if not isinstance(response, dict):
        return []
    rows = response.get("results", response.get("Results", []))
    return rows if isinstance(rows, list) else []


def categorize(component: str, summary: str = "") -> str:
    haystack = f"{component} {summary}".lower()
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            return category
    return "other"


def component_text(record: Dict[str, Any]) -> str:
    direct = get_first(record, ["Component", "component"])
    if direct:
        return direct

    components = record.get("components")
    if isinstance(components, list):
        parts: List[str] = []
        for component in components:
            if isinstance(component, str):
                parts.append(component)
            elif isinstance(component, dict):
                parts.append(get_first(component, ["name", "component", "componentName"]))
        joined = ", ".join(part for part in parts if part)
        if joined:
            return joined
    if isinstance(components, str) and components.strip():
        return components.strip()

    return "Unknown component"


def normalize_recall(record: Dict[str, Any], payload: Dict[str, Any], index: int, raw_ref: str) -> EvidenceItem:
    source = payload["source"]
    campaign = get_first(record, ["NHTSACampaignNumber", "nhtsaCampaignNumber", "CampaignNumber"], f"recall-{index}")
    component = component_text(record)
    summary = get_first(record, ["Summary", "summary"])
    consequence = get_first(record, ["Consequence", "consequence"])
    remedy = get_first(record, ["Remedy", "remedy"])
    title = get_first(record, ["Subject", "ReportReceivedDate"], f"Recall {campaign}")
    combined = " ".join(part for part in [summary, consequence, remedy] if part)
    return EvidenceItem(
        evidence_id=f"nhtsa-recall-{campaign}",
        source_type="recall",
        source_name="NHTSA",
        source_id=campaign,
        category=categorize(component, combined),
        component=component,
        title=title,
        summary=combined or "Recall record did not include a summary.",
        url=source["url"],
        retrieved_at=source["retrieved_at"],
        raw_ref=raw_ref,
        metadata={
            "report_received_date": get_first(record, ["ReportReceivedDate", "reportReceivedDate"]),
            "manufacturer": get_first(record, ["Manufacturer", "manufacturer"]),
        },
    )


def normalize_complaint(record: Dict[str, Any], payload: Dict[str, Any], index: int, raw_ref: str) -> EvidenceItem:
    source = payload["source"]
    complaint_id = get_first(record, ["ODINumber", "ODINO", "odiNumber", "ComplaintNumber"], f"complaint-{index}")
    component = component_text(record)
    summary = get_first(record, ["Summary", "summary", "Description", "description"], "Complaint record did not include a summary.")
    title = f"Complaint {complaint_id}"
    return EvidenceItem(
        evidence_id=f"nhtsa-complaint-{complaint_id}",
        source_type="complaint",
        source_name="NHTSA",
        source_id=complaint_id,
        category=categorize(component, summary),
        component=component,
        title=title,
        summary=summary,
        url=source["url"],
        retrieved_at=source["retrieved_at"],
        raw_ref=raw_ref,
        metadata={
            "date_filed": get_first(record, ["DateComplaintFiled", "dateComplaintFiled"]),
            "crash": get_first(record, ["Crash", "crash"]),
            "fire": get_first(record, ["Fire", "fire"]),
            "injuries": get_first(record, ["Injuries", "injuries", "NumberOfInjuries", "numberOfInjuries"]),
            "deaths": get_first(record, ["Deaths", "deaths", "NumberOfDeaths", "numberOfDeaths"]),
        },
    )


def normalize_nhtsa_cache(vehicle: Vehicle, raw_root: Path = Path("data/raw/nhtsa")) -> NormalizedVehicleEvidence:
    vehicle_root = raw_root / vehicle.slug
    evidence: List[EvidenceItem] = []
    warnings: List[str] = []
    raw_inputs: Dict[str, str] = {}

    for source_type, normalizer in (("recalls", normalize_recall), ("complaints", normalize_complaint)):
        raw_path = vehicle_root / f"{source_type}.json"
        if not raw_path.exists():
            warnings.append(f"Missing raw NHTSA {source_type} cache: {raw_path}")
            continue
        payload = ensure_object(read_json(raw_path), raw_path)
        raw_inputs[f"nhtsa_{source_type}"] = str(raw_path)
        for index, record in enumerate(_records(payload), start=1):
            if isinstance(record, dict):
                evidence.append(normalizer(record, payload, index, str(raw_path)))

    source_counts = Counter(item.source_type for item in evidence)
    category_counts = Counter(item.category for item in evidence)
    return NormalizedVehicleEvidence(
        vehicle=vehicle,
        generated_at=utc_now_iso(),
        evidence=evidence,
        source_counts=dict(sorted(source_counts.items())),
        category_counts=dict(sorted(category_counts.items())),
        warnings=warnings,
        raw_inputs=raw_inputs,
    )


def normalize_to_file(vehicle: Vehicle, output_root: Path = Path("data/normalized/vehicles")) -> Path:
    normalized = normalize_nhtsa_cache(vehicle)
    output_path = output_root / f"{vehicle.slug}.json"
    write_json(output_path, normalized.to_dict())
    return output_path
