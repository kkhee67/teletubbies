import os
from typing import Any

import httpx


DEFAULT_AI_API_BASE_URL = "http://127.0.0.1:8001"
DEFAULT_TIMEOUT_SECONDS = 3.0
SUPPORTED_AI_PRODUCT_TYPES = {"jeonse_return", "rental_deposit"}
AI_RESPONSE_STATUSES = {"ok", "fallback", "unavailable"}
DEFAULT_CASE_SOURCE = {
    "source_type": "ai_api",
    "source_name": "AI API similar consultation cases",
    "is_synthetic": True,
}

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
    if not ai_api_enabled():
        return {
            "status": "disabled",
            "similar_cases": [],
            "easy_explanation": None,
            "message": "AI API is disabled.",
        }

    if guarantee_product_type not in SUPPORTED_AI_PRODUCT_TYPES:
        return {
            "status": "unsupported_product_type",
            "similar_cases": [],
            "easy_explanation": None,
            "message": (
                "AI search was skipped because guarantee_product_type is not "
                "supported by the AI API."
            ),
        }

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
        if not isinstance(body, dict):
            raise TypeError("AI API response must be a JSON object.")
        status = ai_response_status(body)
        similar_cases = [
            normalize_ai_case(case)
            for case in body.get("similar_cases", [])
        ]
        easy_explanation = (
            build_easy_explanation(similar_cases, risk_result)
            if status != "unavailable"
            else None
        )
        return {
            "status": status,
            "similar_cases": similar_cases,
            "easy_explanation": easy_explanation,
            "message": ai_response_message(status, body),
            "raw_result_count": body.get("meta", {}).get("result_count", len(similar_cases)),
        }
    except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.PoolTimeout) as exc:
        return {
            "status": "timeout",
            "similar_cases": [],
            "easy_explanation": None,
            "error": exc.__class__.__name__,
            "message": "AI API request timed out.",
        }
    except httpx.ConnectError as exc:
        return {
            "status": "unavailable",
            "similar_cases": [],
            "easy_explanation": None,
            "error": exc.__class__.__name__,
            "message": "AI API is unavailable.",
        }
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        return {
            "status": "error",
            "similar_cases": [],
            "easy_explanation": None,
            "error": exc.__class__.__name__,
            "message": "AI API returned an invalid response.",
        }


def ai_api_base_url() -> str:
    return os.getenv("AI_API_BASE_URL", DEFAULT_AI_API_BASE_URL).rstrip("/")


def ai_api_enabled() -> bool:
    return os.getenv("AI_API_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def ai_api_timeout() -> float:
    raw_value = os.getenv("AI_API_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    try:
        return max(0.1, float(raw_value))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def ai_response_status(body: dict[str, Any]) -> str:
    meta = body.get("meta", {})
    candidates = [
        body.get("status"),
        body.get("ai_api_status"),
        meta.get("ai_search_status") if isinstance(meta, dict) else None,
    ]
    for candidate in candidates:
        if candidate in AI_RESPONSE_STATUSES:
            return str(candidate)
    return "error"


def ai_response_message(status: str, body: dict[str, Any]) -> str | None:
    if isinstance(body.get("message"), str):
        return body["message"]
    if status == "fallback":
        return "AI API returned fallback results."
    if status == "unavailable":
        return "AI API reported unavailable."
    if status == "error":
        return "AI API returned an unsupported status."
    return None


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
    source = normalize_case_source(case.get("source"))
    return {
        **case,
        "similarity": similarity,
        "tags": tags,
        "summary": case.get("easy_explanation") or case.get("dispute_type", "유사 상담사례"),
        "missed_checks": case.get("actions", []),
        "source": source,
        "source_type": case_source_type(source),
        "source_name": case_source_name(source),
        "reference_date": case_reference_date(source),
    }


def normalize_case_source(source: Any) -> dict[str, Any] | str:
    if isinstance(source, dict) and source:
        return source
    if isinstance(source, str) and source.strip():
        return source
    return dict(DEFAULT_CASE_SOURCE)


def case_source_type(source: dict[str, Any] | str) -> str | None:
    if isinstance(source, dict):
        return (
            source.get("source_type")
            or source.get("type")
            or source.get("source_id")
        )
    return None


def case_source_name(source: dict[str, Any] | str) -> str:
    if isinstance(source, dict):
        return str(
            source.get("source_name")
            or source.get("name")
            or source.get("label")
            or source.get("type")
            or DEFAULT_CASE_SOURCE["source_name"]
        )
    return source


def case_reference_date(source: dict[str, Any] | str) -> str | None:
    if isinstance(source, dict):
        value = source.get("reference_date") or source.get("retrieved_at")
        return str(value) if value else None
    return None


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
