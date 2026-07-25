from copy import deepcopy
from datetime import datetime
from typing import Any

from repositories import property_repository
from schemas import GUARANTEE_STATUS_VALUES, AnalyzeRequest
from scoring.risk_score import calculate_risk_signals
from services.guarantee_service import resolve_guarantee_branch
from similarity.checklist import build_checklist
from similarity.search_cases import explain_cases_safely, find_similar_cases


ALLOWED_CORRECTIONS = {
    "housing_type",
    "reference_value",
    "mortgage_status",
    "seizure_status",
    "joint_collateral",
    "guarantee_status",
}

STATUS_VALUES = {
    "mortgage_status": {"none", "exists", "promised_removal", "removed", "unknown"},
    "seizure_status": {"none", "exists", "unknown"},
    "joint_collateral": {"none", "exists", "unknown"},
    "guarantee_status": GUARANTEE_STATUS_VALUES,
}


def analyze_contract(request: AnalyzeRequest) -> dict[str, Any]:
    base = property_repository.get(request.property_id)
    if base is None:
        raise ValueError("PROPERTY_NOT_FOUND")

    property_data = apply_user_corrections(base, request.user_corrections)
    guarantee = resolve_guarantee_branch(property_data)
    risk_result = calculate_risk_signals(
        property_data=property_data,
        planned_deposit=request.planned_deposit,
    )

    similar_cases = find_similar_cases(
        property_data=property_data,
        planned_deposit=request.planned_deposit,
        user_note=request.user_note,
        limit=3,
    )
    easy_explanation = explain_cases_safely(similar_cases, risk_result)
    checklist = build_checklist(property_data, risk_result, guarantee)

    return {
        "guarantee": {
            "status": guarantee["status"],
            "group": guarantee["group"],
            "group_display_text": guarantee["group_display_text"],
            "display_text": guarantee["message"],
            "is_enrolled": guarantee["is_enrolled"],
        },
        "guarantee_branch": guarantee["branch"],
        "guarantee_message": guarantee["message"],
        "guarantee_disclaimer": "공식 보증 가입 승인 결과가 아니며, HUG 등 공식 절차로 재확인이 필요합니다.",
        **risk_result,
        "property_summary": build_property_summary(property_data, request),
        "similar_cases": similar_cases,
        "easy_explanation": easy_explanation,
        "checklist": checklist,
        "recommended_action": build_recommended_action(risk_result, guarantee),
        "market_context": build_market_context(property_data),
        "data_sources": build_data_sources(property_data),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "disclaimer": "법률적 확정판정이나 보증 가입 승인이 아닙니다. 계약 전 공식 서류와 전문가 확인이 필요합니다.",
    }


def apply_user_corrections(
    base: dict[str, Any],
    corrections: dict[str, str | int | bool],
) -> dict[str, Any]:
    data = deepcopy(base)
    applied: dict[str, Any] = {}

    for key, value in corrections.items():
        if key not in ALLOWED_CORRECTIONS:
            raise ValueError(f"수정할 수 없는 항목입니다: {key}")
        if key in STATUS_VALUES and value not in STATUS_VALUES[key]:
            allowed = ", ".join(sorted(STATUS_VALUES[key]))
            raise ValueError(f"{key} 허용값은 {allowed} 입니다.")
        if key == "reference_value":
            value = int(value)
            if value <= 0:
                raise ValueError("reference_value는 0보다 커야 합니다.")
        data[key] = value
        applied[key] = value

    data["user_corrections_applied"] = applied
    data["value_source"] = (
        f"{data.get('value_source', '모의데이터')} + 사용자 확인값"
        if applied
        else data.get("value_source", "모의데이터")
    )
    return data


def build_property_summary(property_data: dict[str, Any], request: AnalyzeRequest) -> dict[str, Any]:
    reference_value = int(property_data.get("reference_value") or 0)
    deposit_ratio = round(request.planned_deposit / reference_value * 100, 1) if reference_value else None
    return {
        "property_id": property_data.get("property_id"),
        "address_display": property_data.get("address_display"),
        "district": property_data.get("district"),
        "housing_type": property_data.get("housing_type"),
        "reference_value": reference_value,
        "planned_deposit": request.planned_deposit,
        "monthly_rent": request.monthly_rent,
        "deposit_ratio": deposit_ratio,
        "mortgage_status": property_data.get("mortgage_status"),
        "seizure_status": property_data.get("seizure_status"),
        "joint_collateral": property_data.get("joint_collateral"),
        "guarantee_status": property_data.get("guarantee_status"),
        "value_source": property_data.get("value_source"),
        "user_corrections_applied": property_data.get("user_corrections_applied", {}),
    }


def build_recommended_action(risk_result: dict[str, Any], guarantee: dict[str, Any]) -> dict[str, str]:
    score = risk_result["risk_score"]
    branch = guarantee["branch"]

    if score >= 70 or branch == "deep_analysis":
        label = "계약 전 재검토"
        description = "계약을 즉시 진행하기보다 핵심 서류와 보증 가능 여부를 먼저 확인하세요."
    elif score >= 45 or branch == "check_required":
        label = "확인 후 판단"
        description = "미확인 항목을 줄인 뒤 같은 조건으로 다시 분석하세요."
    elif branch == "in_progress":
        label = "가입 완료 확인"
        description = "보증 신청이나 사전확인을 가입 완료로 보지 말고 보증서 발급 여부를 확인하세요."
    else:
        label = "잔여 위험 확인"
        description = "보호장치가 있어도 계약서와 공식 서류 확인은 필요합니다."

    return {"label": label, "description": description}


def build_market_context(property_data: dict[str, Any]) -> list[dict[str, Any]]:
    note = property_data.get("market_note") or "공식 자료 연동 전"
    return [
        {
            "title": "지역·개발 참고정보",
            "status": note,
            "source": "샘플 데이터",
            "included_in_risk_score": False,
        }
    ]


def build_data_sources(property_data: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "name": "샘플 매물 데이터",
            "type": "demo",
            "note": "해커톤 MVP 시연을 위한 가상 주소 및 매물정보입니다.",
        },
        {
            "name": "HUG 합성 사고·대위변제 데이터",
            "type": "provided",
            "note": "지역·주택유형별 반복 위험신호 설명에 활용합니다.",
        },
        {
            "name": "아이엔 비식별 상담데이터",
            "type": "provided",
            "note": "유사 상담사례와 쉬운 설명 생성에 활용합니다.",
        },
        {
            "name": property_data.get("value_source", "모의데이터"),
            "type": "reference",
            "note": "참고 주택가액은 공식 감정 또는 보증심사 결과가 아닙니다.",
        },
    ]
