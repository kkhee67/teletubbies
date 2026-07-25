from schemas import GUARANTEE_STATUS_VALUES


GUARANTEE_GROUPS = {
    "estimated_eligible": "check_required",
    "officially_eligible": "in_progress",
    "applied": "in_progress",
    "enrolled": "protected",
    "ineligible": "deep_analysis",
    "unknown": "check_required",
}

GUARANTEE_MESSAGES = {
    "estimated_eligible": "내부 조건상 반환보증 가입 가능성이 있어 보이나 공식 확인이 필요합니다.",
    "officially_eligible": "공식 사전확인이 완료됐지만 가입 완료 상태는 아닙니다.",
    "applied": "반환보증 가입 신청이 접수됐지만 보증서 발급 확인이 필요합니다.",
    "enrolled": "반환보증 가입 완료가 확인되었습니다.",
    "ineligible": "반환보증 가입이 어렵거나 불가한 상태입니다.",
    "unknown": "반환보증 상태를 확인하지 못했습니다.",
}

GROUP_DISPLAY_TEXT = {
    "check_required": "확인 필요",
    "in_progress": "가입 절차 진행",
    "protected": "보호장치 확보",
    "deep_analysis": "심층분석 필요",
}


def resolve_guarantee_branch(property_data: dict) -> dict[str, str | bool]:
    status = property_data.get("guarantee_status") or "unknown"
    if status not in GUARANTEE_STATUS_VALUES:
        raise ValueError(f"지원하지 않는 반환보증 상태입니다: {status}")

    group = GUARANTEE_GROUPS[status]
    return {
        "status": status,
        "branch": group,
        "group": group,
        "group_display_text": GROUP_DISPLAY_TEXT[group],
        "message": GUARANTEE_MESSAGES[status],
        "needs_deep_analysis": group in {"check_required", "deep_analysis"},
        "is_enrolled": status == "enrolled",
    }
