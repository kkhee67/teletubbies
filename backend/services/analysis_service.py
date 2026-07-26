from copy import deepcopy
from datetime import datetime
import hashlib
import os
import re
from statistics import median
from typing import Any

from repositories import property_repository
from schemas import GUARANTEE_STATUS_VALUES, AnalyzeRequest
from scoring.risk_score import calculate_risk_signals
from services import market_reference
from services.ai_client import fetch_similar_cases
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

DEFAULT_ADDRESS_REFERENCE_VALUE = 300_000_000


def analyze_contract(request: AnalyzeRequest, *, include_ai: bool = True) -> dict[str, Any]:
    base = resolve_base_property(request)

    property_data = apply_user_corrections(base, request.user_corrections)
    guarantee = resolve_guarantee_branch(property_data)
    risk_result = calculate_risk_signals(
        property_data=property_data,
        planned_deposit=request.planned_deposit,
    )

    guarantee_product_type = (
        request.guarantee_product_type
        or property_data.get("guarantee_product_type")
        or "jeonse_return"
    )
    if include_ai:
        ai_result = fetch_similar_cases(
            property_data=property_data,
            risk_result=risk_result,
            planned_deposit=request.planned_deposit,
            user_note=request.user_note,
            guarantee_product_type=guarantee_product_type,
            limit=3,
        )
    else:
        ai_result = {
            "status": "disabled",
            "similar_cases": [],
            "easy_explanation": None,
            "message": "AI search was skipped for this request.",
        }
    similar_cases = ai_result["similar_cases"]
    easy_explanation = ai_result["easy_explanation"]
    ai_api_status = ai_result["status"]
    ai_api_message = ai_result.get("message")

    if include_ai and ai_result["status"] != "ok" and local_similar_cases_enabled():
        similar_cases = find_similar_cases(
            property_data=property_data,
            planned_deposit=request.planned_deposit,
            user_note=request.user_note,
            limit=3,
        )
        easy_explanation = explain_cases_safely(similar_cases, risk_result)
        ai_api_status = "local_mock"
        ai_api_message = "AI API 장애로 명시적인 로컬 모의사례를 반환했습니다."

    checklist = build_checklist(property_data, risk_result, guarantee)

    return {
        "ai_api_status": ai_api_status,
        "ai_api_message": ai_api_message,
        "guarantee": {
            "status": guarantee["status"],
            "group": guarantee["group"],
            "display_text": guarantee["display_text"],
            "message": guarantee["message"],
            "next_actions": guarantee["next_actions"],
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
        "generated_at": generated_at(),
        "disclaimer": "법률적 확정판정이나 보증 가입 승인이 아닙니다. 계약 전 공식 서류와 전문가 확인이 필요합니다.",
    }


def resolve_base_property(request: AnalyzeRequest) -> dict[str, Any]:
    if request.property_id:
        base = property_repository.get(request.property_id)
        if base is None:
            raise ValueError("PROPERTY_NOT_FOUND")
        return base

    if request.address_query:
        return build_address_only_property(request.address_query, request.planned_deposit)

    raise ValueError("PROPERTY_OR_ADDRESS_REQUIRED")


def build_address_only_property(address: str, planned_deposit: int) -> dict[str, Any]:
    normalized_address = " ".join(address.split())
    property_hash = hashlib.sha1(normalized_address.encode("utf-8")).hexdigest()[:10]
    official_data = market_reference.lookup_official_property_data(normalized_address)
    address_meta = official_data.get("address") or {}
    building_meta = official_data.get("building") or {}
    district = address_meta.get("district") or extract_district(normalized_address)
    legal_dong = address_meta.get("legal_dong") or extract_legal_dong(normalized_address)
    housing_type = official_data.get("housing_type") or "unknown"
    reference = official_data.get("market_reference")
    reference_value = (
        int(reference["reference_value"])
        if reference
        else estimate_provisional_reference_value(district)
    )
    value_source = (
        reference["source_name"]
        if reference
        else "Address-only provisional datastore median"
    )
    market_note = (
        reference["note"]
        if reference
        else (
            "Only an address was provided. Registry, building ledger, guarantee "
            "eligibility, and market reference data still need official checks."
        )
    )

    property_data = {
        "property_id": f"ADDR-{property_hash}",
        "address_display": address_meta.get("road_address") or normalized_address,
        "district": district,
        "legal_dong": legal_dong,
        "housing_type": housing_type,
        "reference_value": planned_deposit,
        "value_source": "주소 입력 기반 임시 기준값",
        "mortgage_status": "unknown",
        "seizure_status": "unknown",
        "joint_collateral": "unknown",
        "guarantee_status": "unknown",
        "guarantee_product_type": "jeonse_return",
        "market_note": "주소만 확인된 상태입니다. 등기부, 건축물대장, 보증 가능 여부는 공식 자료로 추가 확인해야 합니다.",
        "user_corrections_applied": {},
    }
    property_data["reference_value"] = reference_value
    property_data["value_source"] = value_source
    property_data["market_note"] = market_note
    if reference:
        property_data["market_reference"] = reference
    if address_meta:
        property_data["address_verified"] = True
        property_data["official_address"] = address_meta
    if building_meta:
        property_data["building_register"] = building_meta
        if building_meta.get("built_year"):
            property_data["built_year"] = building_meta["built_year"]
    return property_data


def estimate_provisional_reference_value(district: str) -> int:
    rows = property_repository.search(district) if district else []
    if not rows:
        rows = property_repository.search("")
    values = [
        int(row.get("reference_value") or 0)
        for row in rows
        if int(row.get("reference_value") or 0) > 0
    ]
    return int(round(median(values))) if values else DEFAULT_ADDRESS_REFERENCE_VALUE


def extract_district(address: str) -> str:
    match = re.search(r"([가-힣A-Za-z0-9]+(?:구|군))\b", address)
    if match:
        return match.group(1)
    match = re.search(r"([가-힣A-Za-z0-9]+시)\b", address)
    return match.group(1) if match else ""


def extract_legal_dong(address: str) -> str:
    match = re.search(r"([가-힣A-Za-z0-9]+(?:동|읍|면|리))\b", address)
    return match.group(1) if match else ""


def simulate_contract(request) -> dict[str, Any]:
    current = analyze_contract(request.current, include_ai=False)
    changed = analyze_contract(request.changed, include_ai=False)

    return {
        "current": simulation_snapshot(current),
        "changed": simulation_snapshot(changed),
        "delta": {
            "risk_score": changed["risk_score"] - current["risk_score"],
            "signal_count": changed["signal_count"] - current["signal_count"],
        },
        "disclaimer": "시뮬레이션은 법적 안전을 보장하지 않고 위험신호의 변화를 보여줍니다.",
        "generated_at": generated_at(),
    }


def simulation_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "risk_score": result["risk_score"],
        "risk_stage": result["risk_stage"],
        "signal_count": result["signal_count"],
        "property_summary": result["property_summary"],
    }


def local_similar_cases_enabled() -> bool:
    return os.getenv("LOCAL_SIMILAR_CASES_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def generated_at() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


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
    guarantee_product_type = (
        request.guarantee_product_type
        or property_data.get("guarantee_product_type")
        or "jeonse_return"
    )
    return {
        "property_id": property_data.get("property_id"),
        "address_display": property_data.get("address_display"),
        "district": property_data.get("district"),
        "legal_dong": property_data.get("legal_dong"),
        "housing_type": property_data.get("housing_type"),
        "built_year": property_data.get("built_year"),
        "address_verified": bool(property_data.get("address_verified")),
        "reference_value": reference_value,
        "planned_deposit": request.planned_deposit,
        "monthly_rent": request.monthly_rent,
        "deposit_ratio": deposit_ratio,
        "mortgage_status": property_data.get("mortgage_status"),
        "seizure_status": property_data.get("seizure_status"),
        "joint_collateral": property_data.get("joint_collateral"),
        "guarantee_status": property_data.get("guarantee_status"),
        "guarantee_product_type": guarantee_product_type,
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
    contexts: list[dict[str, Any]] = []
    official_address = property_data.get("official_address")
    if isinstance(official_address, dict):
        contexts.append(
            {
                "title": "Official address",
                "status": official_address.get("road_address")
                or property_data.get("address_display"),
                "source": "Juso road-name address API",
                "included_in_risk_score": False,
            }
        )

    building = property_data.get("building_register")
    if isinstance(building, dict):
        contexts.append(
            {
                "title": "Building register",
                "status": building.get("main_purpose") or "Building metadata found",
                "source": building.get("source_name") or "MOLIT building register API",
                "included_in_risk_score": False,
            }
        )

    reference = property_data.get("market_reference")
    if isinstance(reference, dict):
        contexts.append(
            {
                "title": "Market reference",
                "status": reference.get("note") or property_data.get("market_note"),
                "source": reference.get("source_name") or "MOLIT public data API",
                "included_in_risk_score": True,
            }
        )

    if contexts:
        return contexts

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
            "name": "매물 데이터 저장소",
            "type": "datastore",
            "note": "PROPERTY_DATA_PATH로 지정한 매물 데이터 저장소의 현재 스냅샷입니다.",
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
