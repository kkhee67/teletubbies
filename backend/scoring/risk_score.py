from typing import Any


HOUSING_TYPE_LABELS = {
    "apartment": "아파트",
    "officetel": "오피스텔",
    "multi_household": "다가구주택",
    "multi_unit": "다세대주택",
    "row_house": "연립주택",
    "detached": "단독주택",
    "unknown": "미상",
}

GUARANTEE_STATUSES = {
    "estimated_eligible",
    "officially_eligible",
    "applied",
    "enrolled",
    "ineligible",
    "unknown",
}


def calculate_risk_signals(property_data: dict[str, Any], planned_deposit: int) -> dict[str, Any]:
    reference_value = int(property_data.get("reference_value") or 0)
    if reference_value <= 0:
        raise ValueError("참고 주택가액을 확인할 수 없습니다.")

    deposit_ratio = round(planned_deposit / reference_value * 100, 1)
    deposit_score = _deposit_score(deposit_ratio)
    rights_score = _rights_score(property_data)
    guarantee_score = _guarantee_score(property_data.get("guarantee_status", "unknown"))
    information_score = _information_score(property_data)

    risk_score = min(100, deposit_score + rights_score + guarantee_score + information_score)
    signals = _build_signals(property_data, deposit_ratio)

    return {
        "risk_stage": _risk_stage(risk_score),
        "risk_score": risk_score,
        "deposit_ratio": deposit_ratio,
        "signal_count": len(signals),
        "unknown_count": _unknown_count(property_data),
        "category_scores": {
            "deposit_structure": {"score": deposit_score, "max_score": 35},
            "rights": {"score": rights_score, "max_score": 30},
            "guarantee": {"score": guarantee_score, "max_score": 20},
            "information": {"score": information_score, "max_score": 15},
        },
        "signals": signals,
    }


def _deposit_score(ratio: float) -> int:
    if ratio >= 100:
        return 35
    if ratio >= 90:
        return 27
    if ratio >= 80:
        return 20
    if ratio >= 70:
        return 12
    return 5


def _rights_score(property_data: dict[str, Any]) -> int:
    score = 0
    mortgage = property_data.get("mortgage_status", "unknown")
    seizure = property_data.get("seizure_status", "unknown")
    joint = property_data.get("joint_collateral", "unknown")

    if mortgage == "exists":
        score += 18
    elif mortgage == "promised_removal":
        score += 14
    elif mortgage == "unknown":
        score += 8

    if seizure == "exists":
        score += 7
    elif seizure == "unknown":
        score += 3

    if joint == "exists":
        score += 5
    elif joint == "unknown":
        score += 5

    return min(score, 30)


def _guarantee_score(status: str) -> int:
    if status not in GUARANTEE_STATUSES:
        raise ValueError(f"지원하지 않는 반환보증 상태입니다: {status}")
    if status == "ineligible":
        return 18
    if status == "unknown":
        return 12
    if status == "estimated_eligible":
        return 8
    if status in {"officially_eligible", "applied"}:
        return 4
    return 0


def _information_score(property_data: dict[str, Any]) -> int:
    return min(_unknown_count(property_data) * 5, 15)


def _unknown_count(property_data: dict[str, Any]) -> int:
    keys = ["mortgage_status", "seizure_status", "joint_collateral", "guarantee_status"]
    return sum(1 for key in keys if property_data.get(key) == "unknown")


def _risk_stage(score: int) -> str:
    if score >= 70:
        return "계약 전 재검토"
    if score >= 50:
        return "주의"
    if score >= 30:
        return "확인 필요"
    return "낮음"


def _build_signals(property_data: dict[str, Any], deposit_ratio: float) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    housing_type = property_data.get("housing_type", "unknown")
    housing_label = HOUSING_TYPE_LABELS.get(housing_type, housing_type)

    if deposit_ratio >= 90:
        signals.append(
            {
                "code": "HIGH_DEPOSIT_RATIO",
                "title": "보증금비율이 높습니다",
                "severity": "high" if deposit_ratio < 100 else "critical",
                "explanation": f"보증금이 참고 주택가액의 {deposit_ratio}%입니다.",
                "action": "가격 산정 근거와 보증금 조정 가능성을 확인하세요.",
                "included_in_risk_score": True,
            }
        )
    elif deposit_ratio >= 80:
        signals.append(
            {
                "code": "ELEVATED_DEPOSIT_RATIO",
                "title": "보증금비율 확인이 필요합니다",
                "severity": "medium",
                "explanation": f"보증금이 참고 주택가액의 {deposit_ratio}%입니다.",
                "action": "주변 실거래가와 참고 주택가액의 출처를 확인하세요.",
                "included_in_risk_score": True,
            }
        )

    mortgage = property_data.get("mortgage_status", "unknown")
    if mortgage == "exists":
        signals.append(
            {
                "code": "MORTGAGE_EXISTS",
                "title": "선순위 근저당이 확인됐습니다",
                "severity": "high",
                "explanation": "등기부상 임차인보다 먼저 배당받을 수 있는 권리가 있을 수 있습니다.",
                "action": "등기부 을구의 채권최고액과 말소 조건을 확인하세요.",
                "included_in_risk_score": True,
            }
        )
    elif mortgage == "promised_removal":
        signals.append(
            {
                "code": "MORTGAGE_PROMISED_REMOVAL",
                "title": "근저당 말소 약속은 확인이 필요합니다",
                "severity": "high",
                "explanation": "말소 예정이라는 설명만으로는 실제 권리관계가 정리됐다고 볼 수 없습니다.",
                "action": "잔금 지급 전 등기부에서 말소 완료를 확인하세요.",
                "included_in_risk_score": True,
            }
        )
    elif mortgage == "unknown":
        signals.append(_unknown_signal("MORTGAGE_UNKNOWN", "근저당 여부"))

    joint = property_data.get("joint_collateral", "unknown")
    if joint == "exists":
        signals.append(
            {
                "code": "JOINT_COLLATERAL_EXISTS",
                "title": "공동담보가 확인됐습니다",
                "severity": "medium",
                "explanation": "다른 호실이나 부동산과 함께 담보로 묶여 있을 수 있습니다.",
                "action": "공동담보 목록과 선순위 채권 범위를 확인하세요.",
                "included_in_risk_score": True,
            }
        )
    elif joint == "unknown":
        signals.append(_unknown_signal("JOINT_COLLATERAL_UNKNOWN", "공동담보 여부"))

    guarantee = property_data.get("guarantee_status", "unknown")
    if guarantee == "ineligible":
        signals.append(
            {
                "code": "GUARANTEE_INELIGIBLE",
                "title": "반환보증 가입이 어려울 수 있습니다",
                "severity": "high",
                "explanation": "보호장치가 약한 계약일 가능성이 있어 심층 확인이 필요합니다.",
                "action": "공식 보증기관을 통해 불가 사유를 먼저 확인하세요.",
                "included_in_risk_score": True,
            }
        )
    elif guarantee == "estimated_eligible":
        signals.append(
            {
                "code": "GUARANTEE_ESTIMATED_ONLY",
                "title": "반환보증 가능성은 공식 확인이 필요합니다",
                "severity": "medium",
                "explanation": "내부 조건상 가능성이 있어 보여도 공식 사전확인이나 보증서 발급 상태는 아닙니다.",
                "action": "보증기관의 공식 사전확인 결과를 확인하세요.",
                "included_in_risk_score": True,
            }
        )
    elif guarantee in {"officially_eligible", "applied"}:
        signals.append(
            {
                "code": "GUARANTEE_ENROLLMENT_NOT_COMPLETED",
                "title": "반환보증 가입 완료 여부를 확인해야 합니다",
                "severity": "medium",
                "explanation": "사전확인 또는 신청 접수는 가입 완료와 다릅니다.",
                "action": "보증서 발급 또는 가입 완료 증빙을 확인하세요.",
                "included_in_risk_score": True,
            }
        )
    elif guarantee == "unknown":
        signals.append(_unknown_signal("GUARANTEE_UNKNOWN", "반환보증 가입 가능 여부"))

    if housing_type in {"multi_unit", "officetel", "multi_household"}:
        signals.append(
            {
                "code": "HOUSING_TYPE_PATTERN",
                "title": f"{housing_label} 유형의 반복 위험패턴을 확인하세요",
                "severity": "medium",
                "explanation": "제공된 사고·상담 데이터에서 주택유형별로 반복되는 위험맥락이 다르게 나타납니다.",
                "action": "같은 주택유형의 유사 상담사례와 보증 조건을 함께 확인하세요.",
                "included_in_risk_score": False,
            }
        )

    return signals


def _unknown_signal(code: str, label: str) -> dict[str, Any]:
    return {
        "code": code,
        "title": f"{label}가 확인되지 않았습니다",
        "severity": "medium",
        "explanation": "모르는 정보 자체를 위험 확정으로 보지 않고, 계약 전 확인해야 할 항목으로 분류합니다.",
        "action": f"계약 전 공식 서류에서 {label}를 확인하세요.",
        "included_in_risk_score": True,
    }
