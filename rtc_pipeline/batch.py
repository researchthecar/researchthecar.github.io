from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from rtc_pipeline.inventory import find_vehicle, load_inventory
from rtc_pipeline.io import read_json, write_json
from rtc_pipeline.models import Vehicle, vehicle_from_mapping, utc_now_iso
from rtc_pipeline.nhtsa import fetch_and_cache, raw_cache_path, refetch_and_cache
from rtc_pipeline.normalize import normalize_to_file
from rtc_pipeline.registry import load_registry
from rtc_pipeline.render import render_normalized_file
from rtc_pipeline.validate import validate_normalized_file


@dataclass
class VehicleRunResult:
    vehicle: Dict[str, Any]
    status: str
    raw_paths: Dict[str, str] = field(default_factory=dict)
    source_errors: Dict[str, str] = field(default_factory=dict)
    normalized_path: str = ""
    rendered_path: str = ""
    validation_errors: List[str] = field(default_factory=list)
    error: str = ""


def load_manifest(path: Path) -> List[Vehicle]:
    rows = read_json(path)
    if not isinstance(rows, list):
        raise ValueError(f"Expected a list of vehicles in {path}")
    return [vehicle_from_mapping(row) for row in rows]


def resolve_manifest_vehicles(manifest_path: Path, inventory_path: Path) -> List[Vehicle]:
    if inventory_path.name == "vehicle_registry.json":
        inventory = load_registry(inventory_path)
    else:
        inventory = load_inventory(inventory_path)
    resolved: List[Vehicle] = []
    missing: List[str] = []
    for vehicle in load_manifest(manifest_path):
        match = find_vehicle(inventory, vehicle.year, vehicle.make, vehicle.model)
        if match:
            resolved.append(match)
        else:
            missing.append(f"{vehicle.year} {vehicle.make} {vehicle.model}")
    if missing:
        raise ValueError("Manifest vehicles missing from inventory: " + "; ".join(missing))
    return resolved


def run_vehicle_pipeline(
    vehicle: Vehicle,
    sources: List[str],
    skip_ingest: bool = False,
    refresh: bool = False,
) -> VehicleRunResult:
    result = VehicleRunResult(vehicle=vehicle.to_dict(), status="ok")
    try:
        if not skip_ingest:
            for source_type in sources:
                try:
                    if refresh:
                        raw_path = refetch_and_cache(vehicle, source_type)
                    else:
                        raw_path = fetch_and_cache(vehicle, source_type)
                    result.raw_paths[source_type] = str(raw_path)
                except Exception as exc:  # pragma: no cover - network variability.
                    result.source_errors[source_type] = f"{type(exc).__name__}: {exc}"
                    existing_path = raw_cache_path(vehicle, source_type)
                    if existing_path.exists():
                        result.raw_paths[source_type] = str(existing_path)
        else:
            for source_type in sources:
                raw_path = raw_cache_path(vehicle, source_type)
                if raw_path.exists():
                    result.raw_paths[source_type] = str(raw_path)
                else:
                    result.source_errors[source_type] = f"Missing raw cache: {raw_path}"

        normalized_path = normalize_to_file(vehicle)
        result.normalized_path = str(normalized_path)
        errors = validate_normalized_file(normalized_path)
        result.validation_errors = errors
        if errors:
            result.status = "validation_failed"
            return result

        rendered_path = render_normalized_file(normalized_path)
        result.rendered_path = str(rendered_path)
        if result.source_errors:
            result.status = "source_error"
        return result
    except Exception as exc:  # pragma: no cover - kept broad for batch reporting resilience.
        result.status = "error"
        result.error = f"{type(exc).__name__}: {exc}"
        return result


def run_pilot(
    manifest_path: Path = Path("data/pilot_vehicles.json"),
    inventory_path: Path = Path("data/vehicle_registry.json"),
    summary_path: Path = Path("data/rendered/pilot_summary.json"),
    sources: List[str] | None = None,
    skip_ingest: bool = False,
    refresh: bool = False,
    limit: int | None = None,
    progress: bool = False,
) -> Dict[str, Any]:
    selected_sources = sources or ["recalls", "complaints"]
    vehicles = resolve_manifest_vehicles(manifest_path, inventory_path)
    if limit is not None:
        vehicles = vehicles[:limit]

    results: List[VehicleRunResult] = []
    total = len(vehicles)
    for index, vehicle in enumerate(vehicles, start=1):
        if progress:
            print(f"[{index}/{total}] {vehicle.slug}: running", flush=True)
        result = run_vehicle_pipeline(vehicle, selected_sources, skip_ingest=skip_ingest, refresh=refresh)
        results.append(result)
        if progress:
            detail = f" - {result.error}" if result.error else ""
            print(f"[{index}/{total}] {vehicle.slug}: {result.status}{detail}", flush=True)

    summary = {
        "generated_at": utc_now_iso(),
        "manifest_path": str(manifest_path),
        "inventory_path": str(inventory_path),
        "sources": selected_sources,
        "skip_ingest": skip_ingest,
        "refresh": refresh,
        "progress": progress,
        "requested_vehicle_count": len(vehicles),
        "status_counts": status_counts(results),
        "results": [asdict(result) for result in results],
    }
    write_json(summary_path, summary)
    return summary


def status_counts(results: List[VehicleRunResult]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return dict(sorted(counts.items()))
