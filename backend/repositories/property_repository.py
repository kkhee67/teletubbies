import csv
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "sample_properties.csv"

INT_FIELDS = {"reference_value", "built_year"}
PUBLIC_FIELDS = {
    "property_id",
    "address_display",
    "district",
    "legal_dong",
    "housing_type",
    "reference_value",
    "value_source",
    "mortgage_status",
    "seizure_status",
    "joint_collateral",
    "guarantee_status",
    "guarantee_product_type",
    "market_note",
}


@lru_cache(maxsize=1)
def _load_rows() -> list[dict[str, Any]]:
    with DATA_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    normalized = []
    for row in rows:
        item: dict[str, Any] = {}
        for key, value in row.items():
            if key in INT_FIELDS:
                item[key] = int(value) if value else 0
            else:
                item[key] = value.strip() if isinstance(value, str) else value
        normalized.append(item)
    return normalized


def _public_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item[key] for key in PUBLIC_FIELDS if key in item}


def search(query: str) -> list[dict[str, Any]]:
    q = (query or "").strip().lower()
    rows = _load_rows()
    if not q:
        return [_public_item(row) for row in rows]

    matched = []
    for row in rows:
        haystack = " ".join(
            [
                row.get("address_display", ""),
                row.get("district", ""),
                row.get("legal_dong", ""),
                row.get("housing_type", ""),
            ]
        ).lower()
        if q in haystack:
            matched.append(_public_item(row))
    return matched


def get(property_id: str) -> dict[str, Any] | None:
    for row in _load_rows():
        if row.get("property_id") == property_id:
            return _public_item(row)
    return None
