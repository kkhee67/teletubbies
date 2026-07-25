import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "properties.json"
DEFAULT_TTL_SECONDS = 60

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
    "built_year",
}


@dataclass
class PropertySnapshot:
    rows: list[dict[str, Any]]
    signature: tuple[int, int]
    expires_at: float


_snapshot: PropertySnapshot | None = None


def _data_path() -> Path:
    return Path(os.getenv("PROPERTY_DATA_PATH", str(DEFAULT_DATA_PATH))).resolve()


def _ttl_seconds() -> int:
    raw_value = os.getenv("PROPERTY_STORE_TTL_SECONDS", str(DEFAULT_TTL_SECONDS))
    try:
        return max(1, int(raw_value))
    except ValueError:
        return DEFAULT_TTL_SECONDS


def _file_signature(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size)


def _load_rows_from_store(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        raw_rows = json.load(f)

    if not isinstance(raw_rows, list):
        raise ValueError("PROPERTY_DATA_PATH must contain a JSON array")

    return [_normalize_row(row) for row in raw_rows]


def _load_rows() -> list[dict[str, Any]]:
    global _snapshot

    path = _data_path()
    signature = _file_signature(path)
    now = time.time()

    if (
        _snapshot is not None
        and _snapshot.signature == signature
        and now < _snapshot.expires_at
    ):
        return _snapshot.rows

    rows = _load_rows_from_store(path)
    _snapshot = PropertySnapshot(
        rows=rows,
        signature=signature,
        expires_at=now + _ttl_seconds(),
    )
    return rows


def clear_cache() -> None:
    global _snapshot
    _snapshot = None


def _field_value(row: dict[str, Any], key: str, default: Any = "") -> Any:
    value = row.get(key, default)
    if isinstance(value, dict):
        return value.get("value", value.get("amount", default))
    return value


def _source_name(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if isinstance(value, dict):
        return str(value.get("source_name") or value.get("source_type") or "")
    return ""


def _normalize_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("Each property row must be an object")

    reference_value = _field_value(row, "reference_value", 0)
    item: dict[str, Any] = {
        "property_id": str(row.get("property_id", "")),
        "address_display": str(
            row.get("address_display") or row.get("display_address") or ""
        ),
        "district": str(row.get("district", "")),
        "legal_dong": str(row.get("legal_dong", "")),
        "housing_type": str(
            _field_value(
                row,
                "housing_type",
                _field_value(row, "property_type", "unknown"),
            )
        ),
        "reference_value": int(reference_value or 0),
        "value_source": str(
            row.get("value_source")
            or _source_name(row, "reference_value")
            or "property datastore"
        ),
        "mortgage_status": str(_field_value(row, "mortgage_status", "unknown")),
        "seizure_status": str(_field_value(row, "seizure_status", "unknown")),
        "joint_collateral": str(_field_value(row, "joint_collateral", "unknown")),
        "guarantee_status": str(_field_value(row, "guarantee_status", "unknown")),
        "guarantee_product_type": str(
            row.get("guarantee_product_type") or "jeonse_return"
        ),
        "market_note": str(row.get("market_note", "")),
    }

    if not item["property_id"]:
        raise ValueError("property_id is required")

    for key in INT_FIELDS:
        if key in row and key not in item:
            item[key] = int(row[key] or 0)

    return item


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
                row.get("property_id", ""),
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
