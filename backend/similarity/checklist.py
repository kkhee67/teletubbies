from typing import Any


def build_checklist(
    property_data: dict[str, Any],
    risk_result: dict[str, Any],
    guarantee: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    if property_data.get("mortgage_status") in {"exists", "promised_removal", "unknown"}:
        items.append(
            _item(
                "CHK_MORTGAGE",
                "근저당 채권최고액 확인",
                "등기부 을구에서 최대 담보한도와 말소 여부를 확인하세요.",
                "high",
            )
        )

    if property_data.get("mortgage_status") == "promised_removal":
        items.append(
            _item(
                "CHK_REMOVAL",
                "잔금 전 말소 완료 확인",
                "말소 예정 약속이 아니라 실제 등기부 말소 상태를 확인하세요.",
                "high",
            )
        )

    if property_data.get("joint_collateral") in {"exists", "unknown"}:
        items.append(
            _item(
                "CHK_JOINT_COLLATERAL",
                "공동담보 여부 확인",
                "여러 호실이나 다른 부동산과 함께 담보로 묶였는지 확인하세요.",
                "medium",
            )
        )

    if guarantee["branch"] == "deep_analysis":
        items.append(
            _item(
                "CHK_GUARANTEE",
                "반환보증 사전 확인",
                "공식 기관에서 가입 불가 사유와 대체 보호장치를 먼저 확인하세요.",
                "high",
            )
        )
    elif guarantee["branch"] == "check_required":
        items.append(
            _item(
                "CHK_GUARANTEE",
                "반환보증 공식 확인",
                "내부 추정이나 미확인 상태를 가입 가능 또는 가입 완료로 보지 말고 공식 사전확인을 진행하세요.",
                "high",
            )
        )
    elif guarantee["branch"] == "in_progress":
        items.append(
            _item(
                "CHK_GUARANTEE",
                "반환보증 가입 완료 확인",
                "사전확인 또는 신청 접수 상태이므로 보증서 발급과 가입 완료 증빙을 확인하세요.",
                "medium",
            )
        )

    if risk_result.get("deposit_ratio", 0) >= 80:
        items.append(
            _item(
                "CHK_VALUE",
                "주택가액 산정 근거 확인",
                "실거래가, 공시가격, 감정가 등 가격 근거가 충분한지 확인하세요.",
                "medium",
            )
        )

    items.append(
        _item(
            "CHK_EXPERT",
            "필요 시 전문가 상담",
            "권리관계가 복잡하거나 미확인 정보가 남아 있으면 공식 기관이나 전문가 확인을 권장합니다.",
            "low",
        )
    )

    return items


def _item(code: str, title: str, description: str, priority: str) -> dict[str, str]:
    return {
        "code": code,
        "title": title,
        "description": description,
        "priority": priority,
    }
