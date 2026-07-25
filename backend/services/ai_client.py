import os
from typing import Any

import httpx


DEFAULT_AI_API_BASE_URL = "http://127.0.0.1:8001"
DEFAULT_TIMEOUT_SECONDS = 0.5

HOUSING_TYPE_LABELS = {
    "apartment": "아파트",
    "officetel": "오피스텔",
    "multi_household": "다가구주택",
    "multi_unit": "다세대주택",
    "row_house": "연립주택",
    "detached": "단독주택",
    "unknown": "미상",
}

REQUIRED_CHECK_CODES = {
    "GUARANTEE_ESTIMATED_ONLY",
    "GUARANTEE_ENROLLMENT_NOT_COMPLETED",
}


def fetch_similar_cases(
    *,
    property_data: dict[str, Any],
    risk_result: dict[str, Any],
    planned_deposit: int,
    user_note: str,
    guarantee_product_type: str,
    limit: int = 3,
) -> dict[str, Any]:
    payload = build_similar_cases_payload(
        property_data=property_data,
        risk_result=risk_result,
        planned_deposit=planned_deposit,
        user_note=user_note,
        guarantee_product_type=guarantee_product_type,
        limit=limit,
    )
    url = f"{ai_api_base_url()}/api/similar-cases"
    try:
        response = httpx.post(url, json=payload, timeout=ai_api_timeout())
        response.raise_for_status()
        body = response.json()
        similar_cases = [
            normalize_ai_case(case)
            for case in body.get("similar_cases", [])
        ]
        return {
            "status": "ok",
            "similar_cases": similar_cases,
            "easy_explanation": build_easy_explanation(similar_cases, risk_result),
            "raw_result_count": body.get("meta", {}).get("result_count", len(similar_cases)),
        }
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        return {
            "status": "fallback",
            "similar_cases": [],
            "easy_explanation": None,
            "error": exc.__class__.__name__,
        }


def ai_api_base_url() -> str:
    return os.getenv("AI_API_BASE_URL", DEFAULT_AI_API_BASE_URL).rstrip("/")


def ai_api_timeout() -> float:
    raw_value = os.getenv("AI_API_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    try:
        return max(0.1, float(raw_value))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def build_similar_cases_payload(
    *,
    property_data: dict[str, Any],
    risk_result: dict[str, Any],
    planned_deposit: int,
    user_note: str,
    guarantee_product_type: str,
    limit: int,
) -> dict[str, Any]:
    confirmed_risks, required_checks = split_analysis_items(
        risk_result.get("signals", [])
    )
    return {
        "property_data": {
            "property_id": property_data.get("property_id"),
            "guarantee_product_type": guarantee_product_type,
            "housing_type": HOUSING_TYPE_LABELS.get(
                property_data.get("housing_type", "unknown"),
                property_data.get("housing_type", "미상"),
            ),
            "deposit": planned_deposit,
            "planned_deposit": planned_deposit,
            "deposit_range": deposit_range(planned_deposit),
            "mortgage_status": senior_right_label(property_data),
            "senior_rights": senior_right_label(property_data),
            "guarantee_status": property_data.get("guarantee_status", "unknown"),
        },
        "analysis": {
            "confirmed_risks": confirmed_risks,
            "required_checks": required_checks,
        },
        "user_text": user_note or None,
        "top_k": limit,
    }


def split_analysis_items(signals: list[dict[str, Any]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    confirmed: list[dict[str, str]] = []
    required: list[dict[str, str]] = []
    for signal in signals:
        item = {
            "code": str(signal.get("code", "")),
            "title": str(signal.get("title", "")),
            "severity": str(signal.get("severity", "")),
        }
        if is_required_check(signal):
            required.append(item)
        else:
            confirmed.append(item)
    return confirmed, required


def is_required_check(signal: dict[str, Any]) -> bool:
    code = str(signal.get("code", ""))
    return code.endswith("_UNKNOWN") or code in REQUIRED_CHECK_CODES


def senior_right_label(property_data: dict[str, Any]) -> str:
    rights = []
    if property_data.get("mortgage_status") in {"exists", "promised_removal"}:
        rights.append("근저당")
    if property_data.get("seizure_status") == "exists":
        rights.append("압류·가압류")
    if property_data.get("joint_collateral") == "exists":
        rights.append("공동담보")
    return " ".join(rights) if rights else "미상"


def deposit_range(amount: int) -> str:
    if amount < 100_000_000:
        return "1억 미만"
    if amount < 200_000_000:
        return "1억~2억"
    if amount < 300_000_000:
        return "2억~3억"
    return "3억 이상"


def normalize_ai_case(case: dict[str, Any]) -> dict[str, Any]:
    similarity = case.get("similarity", 0)
    if isinstance(similarity, (int, float)) and similarity <= 1:
        similarity = round(similarity * 100, 1)

    tags = list(dict.fromkeys(
        list(case.get("matched_factors", []))
        + list(case.get("confirmed_risk_tags", []))
        + list(case.get("required_check_tags", []))
    ))
    return {
        **case,
        "similarity": similarity,
        "tags": tags,
        "summary": case.get("easy_explanation") or case.get("dispute_type", "유사 상담사례"),
        "missed_checks": case.get("actions", []),
        "source": "AI API 유사 상담사례",
    }


def build_easy_explanation(
    similar_cases: list[dict[str, Any]],
    risk_result: dict[str, Any],
) -> dict[str, str]:
    if not similar_cases:
        return {
            "title": "비슷한 상담사례를 찾지 못했습니다",
            "what_happened": "AI API에서 현재 조건과 직접적으로 유사한 사례를 받지 못했습니다.",
            "plain_explanation": "위험 확정은 아니지만, 미확인 정보는 계약 전에 줄이는 것이 좋습니다.",
        }

    selected = similar_cases[0]
    return {
        "title": "고등학생도 이해하기 쉽게",
        "selected_case_id": selected["case_id"],
        "what_happened": selected.get("dispute_type", selected.get("summary", "")),
        "plain_explanation": selected.get("easy_explanation", selected.get("summary", "")),
        "risk_context": f"현재 분석에서는 위험신호 {risk_result['signal_count']}개와 미확인 정보 {risk_result['unknown_count']}개가 확인됐습니다.",
    }
