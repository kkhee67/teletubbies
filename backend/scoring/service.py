"""Small integration layer used by the backend API or demo script."""

from __future__ import annotations

import json
from pathlib import Path

from .risk_rules import analyze_property

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _load_json(filename: str):
    return json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))


def list_sample_properties() -> list[dict]:
    """Return safe, display-only metadata for the sample selector."""

    return [
        {
            "property_id": item["property_id"],
            "dataset_type": item["dataset_type"],
            "data_version": item["data_version"],
            "updated_at": item["updated_at"],
            "display_address": item["display_address"],
            "is_mock": item["is_mock"],
        }
        for item in _load_json("mock_properties.json")
    ]


def analyze_sample(property_id: str, planned_deposit: int) -> dict:
    """Analyze one prepared mock property by ID."""

    properties = _load_json("mock_properties.json")
    property_data = next(
        (item for item in properties if item["property_id"] == property_id), None
    )
    if property_data is None:
        raise KeyError(f"모의 매물을 찾을 수 없습니다: {property_id}")
    locations = _load_json("location_context.json")
    return analyze_property(
        property_data,
        planned_deposit,
        location_context=locations.get(property_id),
    )
