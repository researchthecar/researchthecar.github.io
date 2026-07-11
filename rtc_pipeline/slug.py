from __future__ import annotations

import re


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-")


def vehicle_slug(year: int, make: str, model: str) -> str:
    return f"{int(year)}-{slugify(make)}-{slugify(model)}"
