"""Analysis-confidence calculation.

Confidence describes how much required information has been verified. It is
not a safety score or an accident probability.
"""

from __future__ import annotations

from typing import Any, Mapping

VERIFIED_SOURCE_TYPES = {"official", "user_confirmed"}
CONFIRMED_GUARANTEE_STATUSES = {
    "officially_eligible",
    "applied",
    "enrolled",
    "ineligible",
}

FIELD_WEIGHTS = {
    "property_type": 1,
    "reference_value": 2,
    "mortgage_status": 2,
    "seizure_status": 2,
    "joint_collateral": 1,
    "guarantee_status": 2,
    "housing_required_info": 1,
}


def _has_known_value(field: Mapping[str, Any]) -> bool:
    value = field.get("value", field.get("amount"))
    if isinstance(value, Mapping):
        return bool(value) and all(item is True for item in value.values())
    return value is not None and value != "" and value != "unknown"


def _reference_value_is_complete(field: Mapping[str, Any]) -> bool:
    return all(
        field.get(key)
        for key in ("amount", "value_type", "source_name", "reference_date")
    )


def is_verified(name: str, field: Mapping[str, Any] | None) -> bool:
    if not field or field.get("source_type") not in VERIFIED_SOURCE_TYPES:
        return False
    if name == "reference_value":
        return _reference_value_is_complete(field)
    if name == "guarantee_status":
        return field.get("value") in CONFIRMED_GUARANTEE_STATUSES
    return _has_known_value(field)


def build_confidence_breakdown(
    fields: Mapping[str, Mapping[str, Any] | None],
) -> dict[str, Any]:
    """Return an auditable field-by-field confidence calculation."""

    rows = []
    verified_weight = 0
    for name, weight in FIELD_WEIGHTS.items():
        verified = is_verified(name, fields.get(name))
        if verified:
            verified_weight += weight
        rows.append({"field": name, "weight": weight, "verified": verified})

    total_weight = sum(FIELD_WEIGHTS.values())
    score = round(verified_weight / total_weight * 100) if total_weight else 0
    return {
        "score": score,
        "verified_weight": verified_weight,
        "total_weight": total_weight,
        "fields": rows,
        "notice": "분석 신뢰도는 안전도가 아니라 필수정보의 확인 정도입니다.",
    }


def calculate_analysis_confidence(
    fields: Mapping[str, Mapping[str, Any] | None],
) -> int:
    """Return the weighted percentage of verified analysis fields."""

    return build_confidence_breakdown(fields)["score"]
