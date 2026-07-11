from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

from rtc_pipeline.io import read_json
from rtc_pipeline.models import Vehicle, vehicle_from_mapping
from rtc_pipeline.slug import slugify


def load_inventory(path: Path = Path("assets/cars_parsed.json")) -> List[Vehicle]:
    rows = read_json(path)
    if not isinstance(rows, list):
        raise ValueError(f"Expected a list of vehicles in {path}")
    return [vehicle_from_mapping(row) for row in rows]


def find_vehicle(
    vehicles: Iterable[Vehicle],
    year: int,
    make: str,
    model: str,
) -> Optional[Vehicle]:
    make_key = slugify(make)
    model_key = slugify(model)
    for vehicle in vehicles:
        if vehicle.year != int(year):
            continue
        if slugify(vehicle.make) == make_key and slugify(vehicle.model) == model_key:
            return vehicle
        if slugify(vehicle.legacy_make or "") == make_key and slugify(vehicle.legacy_model or "") == model_key:
            return vehicle
    return None
