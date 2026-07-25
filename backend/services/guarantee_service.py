from typing import Any

from schemas import GUARANTEE_STATUS_VALUES


GUARANTEE_GROUPS = {
    "estimated_eligible": "check_required",
    "officially_eligible": "in_progress",
    "applied": "in_progress",
    "enrolled": "protected",
    "ineligible": "deep_analysis",
    "unknown": "check_required",
}

GROUP_DISPLAY_TEXT = {
    "check_required": "확인 필요",
    "in_progress": "가입 절차 진행",
    "protected": "보호장치 확보",
    "deep_analysis": "심층분석 필요",
}

STATUS_DISPLAY_TEXT = {
    "estimated_eligible": "가입 가능성 있음",
    "officially_eligible": "사전 확인 완료",
    "applied": "가입 신청 중",
    "enrolled": "가입 완료",
    "ineligible": "가입 어려움",
    "unknown": "확인 필요",
}

GUARANTEE_MESSAGES = {
    "estimated_eligible": "내부 조건상 가입 가능성이 있어 보이지만 공식 확인이 필요합니다.",
    "officially_eligible": "공식 사전확인은 완료됐지만 보증서 발급 전입니다.",
    "applied": "신청은 접수됐지만 보증서 발급 확인이 필요합니다.",
    "enrolled": "보증서 발급과 가입 완료가 확인됐습니다.",
    "ineligible": "현재 조건에서는 가입이 어렵거나 불가능한 상태입니다.",
    "unknown": "반환보증 상태를 확인하지 못했습니다.",
}

NEXT_ACTIONS = {
    "estimated_eligible": ["공식 사전확인 진행", "가입 가능 조건 재확인"],
    "officially_eligible": ["보증 신청 진행", "보증서 발급 조건 확인"],
    "applied": ["보증서 발급 여부 확인"],
    "enrolled": ["보증서 번호와 보증기간 확인"],
    "ineligible": ["불가 사유 확인", "보증금 조정 또는 대체 보호수단 검토"],
    "unknown": ["공식 반환보증 가능 여부 확인"],
}


def resolve_guarantee_branch(property_data: dict[str, Any]) -> dict[str, Any]:
    status = property_data.get("guarantee_status") or "unknown"
    if status not in GUARANTEE_STATUS_VALUES:
        raise ValueError(f"지원하지 않는 반환보증 상태입니다: {status}")

    group = GUARANTEE_GROUPS[status]
    return {
        "status": status,
        "branch": group,
        "group": group,
        "group_display_text": GROUP_DISPLAY_TEXT[group],
        "display_text": STATUS_DISPLAY_TEXT[status],
        "message": GUARANTEE_MESSAGES[status],
        "next_actions": NEXT_ACTIONS[status],
        "needs_deep_analysis": group in {"check_required", "deep_analysis"},
        "is_enrolled": status == "enrolled",
    }
