def resolve_guarantee_branch(property_data: dict) -> dict[str, str | bool]:
    status = property_data.get("guarantee_status", "unknown")

    if status == "eligible":
        return {
            "branch": "eligible",
            "message": "반환보증 가입 가능성이 확인되었습니다.",
            "needs_deep_analysis": False,
        }

    if status == "ineligible":
        return {
            "branch": "ineligible",
            "message": "반환보증 가입이 어려울 가능성이 있습니다.",
            "needs_deep_analysis": True,
        }

    return {
        "branch": "unknown",
        "message": "반환보증 가입 가능 여부를 확인하지 못했습니다.",
        "needs_deep_analysis": True,
    }
