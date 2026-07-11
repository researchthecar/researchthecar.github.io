from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class Vehicle:
    year: int
    make: str
    model: str
    vehicle_id: str = ""
    legacy_make: str = ""
    legacy_model: str = ""
    nhtsa_make: str = ""
    nhtsa_model: str = ""

    @property
    def slug(self) -> str:
        if self.vehicle_id:
            return self.vehicle_id
        from rtc_pipeline.slug import vehicle_slug

        return vehicle_slug(self.year, self.make, self.model)

    def to_dict(self) -> Dict[str, Any]:
        data = {"year": self.year, "make": self.make, "model": self.model, "slug": self.slug}
        if self.legacy_make or self.legacy_model:
            data["legacy"] = {"make": self.legacy_make or self.make, "model": self.legacy_model or self.model}
        if self.nhtsa_make or self.nhtsa_model:
            data["sources"] = {
                "nhtsa": {
                    "make": self.nhtsa_make or self.make,
                    "model": self.nhtsa_model or self.model,
                }
            }
        return data


@dataclass
class EvidenceItem:
    evidence_id: str
    source_type: str
    source_name: str
    source_id: str
    category: str
    component: str
    title: str
    summary: str
    url: str
    retrieved_at: str
    raw_ref: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NormalizedVehicleEvidence:
    vehicle: Vehicle
    generated_at: str
    evidence: List[EvidenceItem]
    source_counts: Dict[str, int]
    category_counts: Dict[str, int]
    warnings: List[str] = field(default_factory=list)
    raw_inputs: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vehicle": self.vehicle.to_dict(),
            "generated_at": self.generated_at,
            "source_counts": self.source_counts,
            "category_counts": self.category_counts,
            "warnings": self.warnings,
            "raw_inputs": self.raw_inputs,
            "evidence": [item.to_dict() for item in self.evidence],
        }


SYSTEM_CATEGORIES = [
    "engine",
    "transmission",
    "drivetrain",
    "suspension",
    "steering",
    "brakes",
    "electrical",
    "interior",
    "exterior",
    "hvac",
    "safety",
    "body_paint",
    "other",
]


def vehicle_from_mapping(data: Dict[str, Any]) -> Vehicle:
    sources = data.get("sources") if isinstance(data.get("sources"), dict) else {}
    nhtsa = sources.get("nhtsa") if isinstance(sources.get("nhtsa"), dict) else {}
    legacy = data.get("legacy") if isinstance(data.get("legacy"), dict) else {}
    return Vehicle(
        year=int(data["year"]),
        make=str(data["make"]),
        model=str(data["model"]),
        vehicle_id=str(data.get("vehicle_id") or data.get("slug") or ""),
        legacy_make=str(legacy.get("make") or data.get("legacy_make") or ""),
        legacy_model=str(legacy.get("model") or data.get("legacy_model") or ""),
        nhtsa_make=str(nhtsa.get("make") or data.get("nhtsa_make") or ""),
        nhtsa_model=str(nhtsa.get("model") or data.get("nhtsa_model") or ""),
    )


def get_first(record: Dict[str, Any], keys: List[str], default: Optional[str] = "") -> str:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default or ""
