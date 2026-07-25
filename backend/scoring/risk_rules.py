"""Explainable contract-risk rules for the address-based MVP.

Implements ``analysis/05_risk_rules/risk_rules_spec.json``. Outputs are
decision-support signals, not an accident probability or a 100-point score.
"""

from __future__ import annotations

from copy import deepcopy
from numbers import Real
from typing import Any, Mapping

from .confidence import VERIFIED_SOURCE_TYPES, build_confidence_breakdown, is_verified

RISK_RULES_VERSION = "1.0.0"

GUARANTEE_STATUSES = {
    "estimated_eligible", "officially_eligible", "applied",
    "enrolled", "ineligible", "unknown",
}
GUARANTEE_GROUPS = {
    "estimated_eligible": ("confirmation_required", "가입 가능성 확인 필요"),
    "officially_eligible": ("in_progress", "가입 절차 진행"),
    "applied": ("in_progress", "가입 신청 중"),
    "enrolled": ("protected", "보호장치 확보"),
    "ineligible": ("deep_analysis", "가입 어려움"),
    "unknown": ("confirmation_required", "확인 필요"),
}
MORTGAGE_STATUSES = {"none", "exists", "promised_removal", "removed", "unknown"}
SEIZURE_STATUSES = {"none", "exists", "unknown"}
JOINT_COLLATERAL_STATUSES = {"none", "exists", "unknown"}


def _field(property_data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = property_data.get(name)
    return value if isinstance(value, Mapping) else {}


def _field_value(property_data: Mapping[str, Any], name: str, default="unknown"):
    field = property_data.get(name)
    if isinstance(field, Mapping):
        return field.get("value", field.get("amount", default))
    return field if field is not None else default


def _signal_source_is_usable(property_data: Mapping[str, Any], name: str) -> bool:
    """Accept verified sources plus explicitly labelled mock demo records."""

    source_type = _field(property_data, name).get("source_type")
    if source_type in VERIFIED_SOURCE_TYPES:
        return True
    return bool(property_data.get("is_mock")) and source_type == "mock"


def _risk(code: str, title: str, severity: str, explanation: str, action: str):
    return {
        "code": code, "title": title, "severity": severity,
        "explanation": explanation, "action": action,
    }


def _check(code: str, title: str, action: str):
    return {"code": code, "title": title, "severity": "check", "action": action}


def _append_unique(items: list[dict[str, Any]], item: dict[str, Any]) -> None:
    if not any(existing["code"] == item["code"] for existing in items):
        items.append(item)


def _validate_status(name: str, value: str, allowed: set[str]) -> None:
    if value not in allowed:
        raise ValueError(f"지원하지 않는 {name} 상태입니다: {value}")


def calculate_deposit_ratio(deposit: int | float, reference_value: int | float | None):
    if isinstance(deposit, bool) or not isinstance(deposit, Real) or deposit <= 0:
        raise ValueError("계약 예정 보증금은 0보다 큰 숫자여야 합니다.")
    if reference_value is None or isinstance(reference_value, bool):
        return None
    if not isinstance(reference_value, Real) or reference_value <= 0:
        return None
    return round(float(deposit) / float(reference_value) * 100, 1)


def _deposit_signals(ratio, reference_field, confirmed, required):
    reference_verified = is_verified("reference_value", reference_field)
    comparable = reference_field.get("comparison_unit_confirmed") is True

    if ratio is None:
        _append_unique(required, _check(
            "REFERENCE_VALUE_UNKNOWN", "참고 주택가액을 확인하지 못했습니다",
            "공식 가격자료의 종류·출처·기준일을 확인하세요.",
        ))
        return reference_verified, comparable

    if not reference_verified:
        _append_unique(required, _check(
            "REFERENCE_VALUE_UNVERIFIED", "참고 주택가액의 공식 근거를 확인해야 합니다",
            "가격 종류·출처·기준일을 확인하세요.",
        ))
    if not comparable:
        _append_unique(required, _check(
            "VALUE_UNIT_COMPARABILITY_UNKNOWN", "보증금과 주택가액의 비교 단위를 확인해야 합니다",
            "개별 호실 보증금과 건물 전체가액을 단순 비교하지 마세요.",
        ))
    if not (reference_verified and comparable):
        return reference_verified, comparable

    if ratio >= 100:
        _append_unique(confirmed, _risk(
            "HIGH_DEPOSIT_RATIO", "보증금이 참고 주택가액 이상입니다", "high",
            f"계약 예정 보증금이 검증된 참고 주택가액의 {ratio}%입니다.",
            "가격 산정 근거를 재확인하고 보증금 조정을 검토하세요.",
        ))
    elif ratio >= 90:
        _append_unique(confirmed, _risk(
            "HIGH_DEPOSIT_RATIO", "보증금비율이 90% 이상입니다", "medium",
            f"계약 예정 보증금이 검증된 참고 주택가액의 {ratio}%입니다.",
            "가격 산정 근거와 보증금 조정 가능성을 확인하세요.",
        ))
    return reference_verified, comparable


def _rights_signals(property_data, confirmed, required):
    mortgage = _field_value(property_data, "mortgage_status")
    _validate_status("근저당", mortgage, MORTGAGE_STATUSES)
    if mortgage != "unknown" and not _signal_source_is_usable(property_data, "mortgage_status"):
        mortgage = "unknown"
    if mortgage == "exists":
        _append_unique(confirmed, _risk(
            "MORTGAGE_EXISTS", "선순위 근저당이 확인됐습니다", "high",
            "임차인보다 먼저 배당받을 수 있는 담보권이 존재합니다.",
            "등기부 을구에서 채권최고액과 순위를 확인하세요.",
        ))
    elif mortgage == "promised_removal":
        _append_unique(confirmed, _risk(
            "MORTGAGE_REMOVAL_PROMISED", "근저당 말소가 아직 완료되지 않았습니다", "high",
            "말소 약속은 등기부에서 권리가 실제 삭제된 상태와 다릅니다.",
            "잔금 지급 직전 최신 등기부에서 말소 완료를 확인하세요.",
        ))
    elif mortgage == "unknown":
        _append_unique(required, _check("MORTGAGE_UNKNOWN", "근저당 여부를 확인해야 합니다", "등기부 을구를 확인하세요."))

    seizure = _field_value(property_data, "seizure_status")
    _validate_status("압류·가압류", seizure, SEIZURE_STATUSES)
    if seizure != "unknown" and not _signal_source_is_usable(property_data, "seizure_status"):
        seizure = "unknown"
    if seizure == "exists":
        _append_unique(confirmed, _risk(
            "SEIZURE_EXISTS", "압류·가압류가 확인됐습니다", "high",
            "소유자의 채무 또는 처분 제한과 관련된 권리가 확인됐습니다.",
            "계약 진행 전 최신 등기부와 권리순위를 전문가와 확인하세요.",
        ))
    elif seizure == "unknown":
        _append_unique(required, _check("SEIZURE_UNKNOWN", "압류·가압류 여부를 확인해야 합니다", "최신 등기부를 확인하세요."))

    joint = _field_value(property_data, "joint_collateral")
    _validate_status("공동담보", joint, JOINT_COLLATERAL_STATUSES)
    if joint != "unknown" and not _signal_source_is_usable(property_data, "joint_collateral"):
        joint = "unknown"
    if joint == "exists":
        _append_unique(confirmed, _risk(
            "JOINT_COLLATERAL_EXISTS", "공동담보가 확인됐습니다", "medium",
            "여러 부동산이 함께 담보로 묶여 개별 매물만으로 회수순서를 판단하기 어렵습니다.",
            "공동담보 목록과 전체 채권최고액을 확인하세요.",
        ))
    elif joint == "unknown":
        _append_unique(required, _check("JOINT_COLLATERAL_UNKNOWN", "공동담보 여부를 확인해야 합니다", "등기부의 공동담보목록을 확인하세요."))


def _guarantee_signals(property_data, status, confirmed, required):
    _validate_status("반환보증", status, GUARANTEE_STATUSES)
    source_usable = _signal_source_is_usable(property_data, "guarantee_status")
    if status == "unknown":
        _append_unique(required, _check("GUARANTEE_UNKNOWN", "반환보증 상태를 확인해야 합니다", "공식 사전확인을 진행하세요."))
    elif status == "estimated_eligible":
        _append_unique(required, _check("GUARANTEE_ESTIMATED_ONLY", "반환보증 가입 가능성을 공식적으로 확인해야 합니다", "내부 추정을 가입 완료로 표현하지 말고 공식 사전확인을 받으세요."))
    elif not source_usable:
        _append_unique(required, _check("GUARANTEE_UNKNOWN", "반환보증 상태의 증빙을 확인해야 합니다", "공식 확인서나 보증서를 확인하세요."))
    elif status == "ineligible":
        _append_unique(confirmed, _risk(
            "GUARANTEE_INELIGIBLE", "반환보증 가입이 어렵습니다", "high",
            "반환보증이라는 보호장치를 이용하기 어려운 상태입니다.",
            "공식 불가 사유를 확인하고 계약조건을 재검토하세요.",
        ))
    elif status in {"officially_eligible", "applied"}:
        _append_unique(required, _check("GUARANTEE_ENROLLMENT_NOT_COMPLETED", "반환보증 가입 완료 여부를 확인해야 합니다", "보증서 발급 또는 가입 완료 증빙을 확인하세요."))


def _housing_checks(property_data, required):
    property_type = _field_value(property_data, "property_type")
    housing_info = _field(property_data, "housing_required_info")
    info_value = housing_info.get("value", {})
    if not isinstance(info_value, Mapping):
        info_value = {}
    info_source_usable = _signal_source_is_usable(property_data, "housing_required_info")

    if property_type == "unknown":
        _append_unique(required, _check("PROPERTY_TYPE_UNKNOWN", "주택유형을 확인해야 합니다", "건축물대장에서 주택유형을 확인하세요."))
        return
    if not _signal_source_is_usable(property_data, "property_type"):
        _append_unique(required, _check("PROPERTY_TYPE_UNKNOWN", "주택유형의 출처를 확인해야 합니다", "건축물대장에서 주택유형을 재확인하세요."))

    def info_confirmed(name: str) -> bool:
        return info_source_usable and info_value.get(name) is True

    if property_type == "multi_household" and not info_confirmed("senior_tenant_deposits_confirmed"):
        _append_unique(required, _check("SENIOR_TENANT_DEPOSITS_UNKNOWN", "다가구 선순위 임차보증금을 확인해야 합니다", "선순위 보증금·다른 임차인 순위·건물 전체 권리를 확인하세요."))
    elif property_type == "officetel" and not info_confirmed("residential_use_confirmed"):
        _append_unique(required, _check("OFFICETEL_USE_UNKNOWN", "오피스텔의 실제 용도를 확인해야 합니다", "건축물대장과 실제 주거용 사용 여부를 확인하세요."))
    elif property_type in {"multi_unit", "row_house", "detached"} and not info_confirmed("value_basis_confirmed"):
        _append_unique(required, _check("VALUE_BASIS_WEAK", "주택가액 산정 근거를 확인해야 합니다", "실거래가·공시가격·감정가의 종류와 기준일을 확인하세요."))


def _contract_term_signals(property_data, confirmed):
    value = property_data.get("down_contract_requested", False)
    if isinstance(value, Mapping):
        value = value.get("value", False)
    if value is True:
        _append_unique(confirmed, _risk(
            "DOWN_CONTRACT_REQUESTED", "다운계약을 요구받았습니다", "high",
            "실제 계약조건과 서류 내용이 다릅니다.",
            "실제 보증금과 다른 계약서 작성을 거절하고 전문가에게 상담하세요.",
        ))


def determine_risk_stage(confirmed_risks, required_checks):
    high_count = sum(risk["severity"] == "high" for risk in confirmed_risks)
    medium_count = sum(risk["severity"] == "medium" for risk in confirmed_risks)
    if high_count >= 2:
        return "계약 전 재검토"
    if high_count == 1 or medium_count >= 2:
        return "주의"
    if confirmed_risks or required_checks:
        return "추가 확인 필요"
    return "기본 확인"


def analyze_property(property_data, planned_deposit, *, location_context=None):
    """Build the data-analysis portion of the shared API response."""

    confirmed: list[dict[str, Any]] = []
    required: list[dict[str, Any]] = []
    reference_field = _field(property_data, "reference_value")
    reference_value = reference_field.get("amount")
    ratio = calculate_deposit_ratio(planned_deposit, reference_value)
    reference_verified, comparable = _deposit_signals(
        ratio, reference_field, confirmed, required
    )

    _rights_signals(property_data, confirmed, required)
    guarantee_status = _field_value(property_data, "guarantee_status")
    _guarantee_signals(property_data, guarantee_status, confirmed, required)
    _housing_checks(property_data, required)
    _contract_term_signals(property_data, confirmed)

    fields = {name: property_data.get(name) for name in (
        "property_type", "reference_value", "mortgage_status",
        "seizure_status", "joint_collateral", "guarantee_status",
        "housing_required_info",
    )}
    confidence = build_confidence_breakdown(fields)
    group, display_text = GUARANTEE_GROUPS[guarantee_status]
    context = deepcopy(location_context or {})
    context["included_in_risk_score"] = False

    high_count = sum(item["severity"] == "high" for item in confirmed)
    medium_count = sum(item["severity"] == "medium" for item in confirmed)
    ratio_status = (
        "unavailable" if ratio is None
        else "verified" if reference_verified and comparable
        else "provisional"
    )

    return {
        "property": {
            "property_id": property_data["property_id"],
            "display_address": property_data["display_address"],
            "is_mock": bool(property_data.get("is_mock", False)),
            "property_type": _field_value(property_data, "property_type"),
            "reference_value": reference_value,
            "deposit_ratio": ratio,
            "deposit_ratio_status": ratio_status,
            "deposit_ratio_notice": "90%·100%는 공식 HUG 기준이나 사고확률이 아닌 MVP 재검토 구간입니다.",
        },
        "guarantee": {"status": guarantee_status, "group": group, "display_text": display_text},
        "analysis": {
            "rule_version": RISK_RULES_VERSION,
            "risk_stage": determine_risk_stage(confirmed, required),
            "confirmed_risk_count": len(confirmed),
            "high_risk_count": high_count,
            "medium_risk_count": medium_count,
            "required_check_count": len(required),
            "analysis_confidence": confidence["score"],
            "analysis_confidence_detail": confidence,
            "confirmed_risks": confirmed,
            "required_checks": required,
            "notice": "위험단계는 사고확률이나 법률적 판단이 아닌 계약 전 의사결정 지원 신호입니다.",
            "basic_stage_notice": "기본 확인은 계약이 안전하다는 뜻이 아닙니다.",
        },
        "similar_cases": [], "checklist": [], "location_context": context,
    }
