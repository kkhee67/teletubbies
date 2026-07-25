from typing import Any


CASE_BANK = [
    {
        "case_id": "C001",
        "tags": ["다세대주택", "근저당", "말소 약속", "보증 미확인"],
        "summary": "잔금일 근저당 말소 약속 후 실제 말소 여부가 확인되지 않은 사례",
        "missed_checks": ["말소 완료 등기부 재열람", "특약 문구", "보증 가입 가능 여부"],
        "base_similarity": 74,
    },
    {
        "case_id": "C002",
        "tags": ["높은 보증금비율", "경매 문의", "보증금 미반환"],
        "summary": "계약 종료 후 보증금 반환 문제로 경매 절차를 문의한 사례",
        "missed_checks": ["보증금비율", "주택가액 산정 근거", "선순위 권리"],
        "base_similarity": 68,
    },
    {
        "case_id": "C003",
        "tags": ["반환보증 가입 어려움", "확인 부족", "계약 전 상담"],
        "summary": "반환보증 가입 불가 사유를 확인하지 않고 계약을 진행하려던 사례",
        "missed_checks": ["보증기관 사전 확인", "불가 사유", "대체 보호장치"],
        "base_similarity": 64,
    },
    {
        "case_id": "C004",
        "tags": ["공동담보", "다세대주택", "후순위 구조"],
        "summary": "여러 호실이 공동담보로 묶여 후순위 회수 위험을 상담한 사례",
        "missed_checks": ["공동담보 목록", "채권최고액", "다른 임차인 현황"],
        "base_similarity": 62,
    },
]


def find_similar_cases(
    property_data: dict[str, Any],
    planned_deposit: int,
    user_note: str = "",
    limit: int = 3,
) -> list[dict[str, Any]]:
    scored = []
    for case in CASE_BANK:
        score = case["base_similarity"]
        text = " ".join(case["tags"]) + " " + case["summary"] + " " + user_note

        if property_data.get("housing_type") in {"multi_unit", "multi_household"} and "다세대주택" in text:
            score += 10
        if property_data.get("mortgage_status") in {"exists", "promised_removal"} and "근저당" in text:
            score += 8
        if property_data.get("joint_collateral") in {"exists", "unknown"} and "공동담보" in text:
            score += 8
        if property_data.get("guarantee_status") in {"ineligible", "unknown"} and "보증" in text:
            score += 6

        scored.append(
            {
                "case_id": case["case_id"],
                "similarity": min(score, 99),
                "tags": case["tags"],
                "summary": case["summary"],
                "missed_checks": case["missed_checks"],
                "source": "아이엔 비식별 상담데이터 패턴 기반 모의사례",
            }
        )

    return sorted(scored, key=lambda item: item["similarity"], reverse=True)[:limit]


def explain_cases_safely(
    similar_cases: list[dict[str, Any]],
    risk_result: dict[str, Any],
) -> dict[str, str]:
    if not similar_cases:
        return {
            "title": "비슷한 상담사례를 찾지 못했습니다",
            "what_happened": "현재 조건과 직접적으로 유사한 모의사례가 없습니다.",
            "plain_explanation": "위험 확정은 아니지만, 미확인 정보는 계약 전에 줄이는 것이 좋습니다.",
        }

    selected = similar_cases[0]
    return {
        "title": "고등학생도 이해하기 쉽게",
        "selected_case_id": selected["case_id"],
        "what_happened": selected["summary"],
        "plain_explanation": "은행이나 기존 권리가 세입자보다 먼저일 수 있습니다. 말로만 약속받지 말고 잔금 전에 공식 서류에서 실제 상태를 확인해야 합니다.",
        "risk_context": f"현재 분석에서는 위험신호 {risk_result['signal_count']}개와 미확인 정보 {risk_result['unknown_count']}개가 확인됐습니다.",
    }
