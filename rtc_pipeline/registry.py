from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from rtc_pipeline.inventory import load_inventory
from rtc_pipeline.io import read_json, write_json
from rtc_pipeline.models import Vehicle, vehicle_from_mapping
from rtc_pipeline.slug import vehicle_slug


REGISTRY_VERSION = 1

KNOWN_CANONICAL_MODELS = {
    ("tesla", "3"): "Model 3",
}


def registry_entry_from_vehicle(vehicle: Vehicle) -> Dict[str, Any]:
    canonical_model = KNOWN_CANONICAL_MODELS.get((vehicle.make.lower(), vehicle.model.lower()), vehicle.model)
    canonical = Vehicle(year=vehicle.year, make=vehicle.make, model=canonical_model)
    entry = {
        "vehicle_id": vehicle_slug(canonical.year, canonical.make, canonical.model),
        "year": canonical.year,
        "make": canonical.make,
        "model": canonical.model,
        "legacy": {
            "make": vehicle.make,
            "model": vehicle.model,
            "slug": vehicle.slug,
        },
        "sources": {
            "nhtsa": {
                "make": canonical.make,
                "model": canonical.model,
                "status": "candidate",
            }
        },
        "status": "candidate",
        "notes": [],
    }
    if canonical.model != vehicle.model:
        entry["status"] = "patched"
        entry["sources"]["nhtsa"]["status"] = "patched"
        entry["notes"].append(f"Canonical model patched from legacy '{vehicle.model}' to '{canonical.model}'.")
    return entry


def build_registry(
    inventory_path: Path = Path("assets/cars_parsed.json"),
    output_path: Path = Path("data/vehicle_registry.json"),
) -> Path:
    vehicles = load_inventory(inventory_path)
    entries = [registry_entry_from_vehicle(vehicle) for vehicle in vehicles]
    registry = {
        "version": REGISTRY_VERSION,
        "source_inventory": str(inventory_path),
        "vehicle_count": len(entries),
        "vehicles": entries,
    }
    write_json(output_path, registry)
    return output_path


def load_registry(path: Path = Path("data/vehicle_registry.json")) -> List[Vehicle]:
    payload = read_json(path)
    if isinstance(payload, dict):
        rows = payload.get("vehicles")
    else:
        rows = payload
    if not isinstance(rows, list):
        raise ValueError(f"Expected vehicle registry list in {path}")
    return [vehicle_from_mapping(row) for row in rows]
