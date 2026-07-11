from __future__ import annotations

import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict

from rtc_pipeline.io import write_json
from rtc_pipeline.models import Vehicle, utc_now_iso


NHTSA_API_BASE = "https://api.nhtsa.gov"
RECALLS_PATH = "/recalls/recallsByVehicle"
COMPLAINTS_PATH = "/complaints/complaintsByVehicle"

def nhtsa_url(path: str, vehicle: Vehicle) -> str:
    make = vehicle.nhtsa_make or vehicle.make
    model = vehicle.nhtsa_model or vehicle.model
    query = urllib.parse.urlencode(
        {
            "make": make,
            "model": model,
            "modelYear": vehicle.year,
        }
    )
    return f"{NHTSA_API_BASE}{path}?{query}"


def fetch_json(url: str, timeout: int = 30, retries: int = 2) -> Dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": os.environ.get("NHTSA_USER_AGENT", "researchthecar-pilot/0.1"),
        },
    )
    import json

    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return json.loads(response.read().decode(charset))
        except urllib.error.HTTPError as exc:
            if exc.code not in {408, 429, 500, 502, 503, 504} or attempt >= retries:
                raise
            time.sleep(2**attempt)
        except (urllib.error.URLError, TimeoutError, socket.timeout):
            if attempt >= retries:
                raise
            time.sleep(2**attempt)

    raise RuntimeError(f"Unable to fetch {url}")


def fetch_and_cache(vehicle: Vehicle, source_type: str, output_root: Path = Path("data/raw/nhtsa")) -> Path:
    output_path = raw_cache_path(vehicle, source_type, output_root)
    if output_path.exists():
        return output_path

    return refetch_and_cache(vehicle, source_type, output_root)


def raw_cache_path(vehicle: Vehicle, source_type: str, output_root: Path = Path("data/raw/nhtsa")) -> Path:
    if source_type not in {"recalls", "complaints"}:
        raise ValueError(f"Unsupported NHTSA source type: {source_type}")
    return output_root / vehicle.slug / f"{source_type}.json"


def refetch_and_cache(vehicle: Vehicle, source_type: str, output_root: Path = Path("data/raw/nhtsa")) -> Path:
    if source_type == "recalls":
        path = RECALLS_PATH
    elif source_type == "complaints":
        path = COMPLAINTS_PATH
    else:
        raise ValueError(f"Unsupported NHTSA source type: {source_type}")

    url = nhtsa_url(path, vehicle)
    fetched_at = utc_now_iso()
    response = fetch_json(url)
    payload = {
        "vehicle": vehicle.to_dict(),
        "source": {
            "name": "NHTSA",
            "type": source_type,
            "url": url,
            "retrieved_at": fetched_at,
        },
        "response": response,
    }
    output_path = raw_cache_path(vehicle, source_type, output_root)
    write_json(output_path, payload)
    return output_path
