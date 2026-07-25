from __future__ import annotations

import hashlib
import os
import re
from datetime import date
from typing import Any

from easy_explanation import enrich_similar_case
from guarantee_products import PRODUCT_LABELS, canonical_product_type
from similar_cases import SimilarCaseSearchEngine, canonical_housing


DEMO_REFERENCE_DATE = "2026-07-25"
CONFIRMED_SOURCE_TYPES = {"official", "user_confirmed"}
KNOWN_RIGHT_STATUSES = {"exists", "none"}
DEPOSIT_RATIO_CHECK_THRESHOLD = 0.90

SIDO_ALIASES = {
    "서울시": "서울특별시",
    "부산시": "부산광역시",
    "대구시": "대구광역시",
    "인천시": "인천광역시",
    "광주시": "광주광역시",
    "대전시": "대전광역시",
    "울산시": "울산광역시",
    "세종시": "세종특별자치시",
    "경기": "경기도",
    "강원": "강원특별자치도",
    "충북": "충청북도",
    "충남": "충청남도",
    "전북": "전북특별자치도",
    "전남": "전라남도",
    "경북": "경상북도",
    "경남": "경상남도",
    "제주": "제주특별자치도",
}

GUARANTEE_GROUPS = {
    "check_required": {
        "order": 1,
        "display_text": "확인 필요",
    },
    "in_progress": {
        "order": 2,
        "display_text": "가입 절차 진행",
    },
    "protected": {
        "order": 3,
        "display_text": "보호장치 확보",
    },
    "deep_analysis": {
        "order": 4,
        "display_text": "심층분석 필요",
    },
}

GUARANTEE_STATUSES = {
    "estimated_eligible": {
        "display_text": "내부 추정상 가입 가능",
        "group": "check_required",
        "summary": "내부 조건상 가능성이 있어 보이지만 공식 확인 전에는 확정할 수 없습니다.",
        "warning": "현재 상태는 가입 완료가 아닙니다.",
        "actions": [
            "공식 사전확인으로 가입 가능 여부 확인",
            "주택가액과 선순위채권 자료 준비",
            "확인 전에는 보호장치가 있다고 가정하지 않기",
        ],
    },
    "officially_eligible": {
        "display_text": "공식 가입 가능 확인",
        "group": "in_progress",
        "summary": "공식 사전확인은 마쳤지만 아직 가입 신청과 보증서 발급이 남아 있습니다.",
        "warning": "가입 가능 확인은 실제 가입 완료와 다릅니다.",
        "actions": [
            "반환보증 가입 신청 진행",
            "신청 접수번호와 심사 일정을 보관",
            "보증서 발급 전에는 가입 완료로 표시하지 않기",
        ],
    },
    "applied": {
        "display_text": "가입 신청 완료",
        "group": "in_progress",
        "summary": "가입 신청은 접수됐지만 보증서가 발급됐는지 확인해야 합니다.",
        "warning": "신청 완료는 실제 가입 완료와 다릅니다.",
        "actions": [
            "심사 진행상태 확인",
            "추가 요청서류 제출",
            "보증서 발급 여부와 보증기간 확인",
        ],
    },
    "enrolled": {
        "display_text": "실제 가입 완료",
        "group": "protected",
        "summary": "보증서 발급까지 확인된 상태입니다.",
        "warning": "보증 대상, 보증금액, 보증기간을 보증서에서 다시 확인해야 합니다.",
        "actions": [
            "보증서 원본 또는 전자문서 보관",
            "보증 대상과 보증금액 확인",
            "보증기간과 갱신 필요 여부 확인",
        ],
    },
    "ineligible": {
        "display_text": "가입이 어렵거나 불가",
        "group": "deep_analysis",
        "summary": "공식 확인에서 가입이 어렵거나 불가한 사유가 확인된 상태입니다.",
        "warning": "불가 사유를 확인하지 않은 채 계약을 진행하지 마세요.",
        "actions": [
            "공식 불가 사유 확인",
            "보증금 또는 선순위채권 조건 변경 검토",
            "계약 진행 전 전문가 상담",
        ],
    },
    "unknown": {
        "display_text": "상태 미확인",
        "group": "check_required",
        "summary": "가입 가능성 또는 현재 진행상태를 아직 확정할 수 없습니다.",
        "warning": "현재 상태는 가입 완료가 아닙니다.",
        "actions": [
            "계약 전 가입 가능 여부 확인",
            "주택가액과 선순위채권 정보 준비",
            "확인 전에는 보호장치가 있다고 가정하지 않기",
        ],
    },
}

FIELD_WEIGHTS = {
    "housing_type": 1,
    "reference_value": 2,
    "mortgage": 2,
    "seizure": 2,
    "joint_collateral": 1,
    "guarantee": 2,
}


def normalize_address(address: str) -> str:
    return re.sub(r"\s+", " ", address.strip())


def address_identity(address: str) -> tuple[str, str | None, str | None]:
    tokens = normalize_address(address).split()
    raw_sido = tokens[0] if tokens else "지역 미확인"
    sido = SIDO_ALIASES.get(raw_sido, raw_sido)
    sigungu = next(
        (
            token
            for token in tokens[1:3]
            if token.endswith(("시", "군", "구"))
        ),
        None,
    )
    display_parts = [sido]
    if sigungu and sigungu != sido:
        display_parts.append(sigungu)
    return " ".join(display_parts) + " 일대", sido, sigungu


def make_property_id(address: str) -> str:
    secret = os.getenv("PROPERTY_ID_SALT", "hackathon-local-only")
    digest = hashlib.sha256(
        f"{secret}:{normalize_address(address)}".encode("utf-8")
    ).hexdigest()[:16]
    return f"PROPERTY-{digest.upper()}"


def unavailable_source() -> dict[str, Any]:
    return {
        "source_type": "unknown",
        "source_name": "연동 또는 확인자료 없음",
        "reference_date": None,
    }


def user_source() -> dict[str, Any]:
    return {
        "source_type": "user_confirmed",
        "source_name": "사용자 상황 설명",
        "reference_date": date.today().isoformat(),
    }


def demo_source(name: str) -> dict[str, Any]:
    return {
        "source_type": "mock",
        "source_name": name,
        "reference_date": DEMO_REFERENCE_DATE,
    }


def normalize_source(source: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(source or unavailable_source())
    if normalized.get("source_type") == "unavailable":
        normalized["source_type"] = "unknown"
    normalized.setdefault("source_type", "unknown")
    normalized.setdefault("source_name", "연동 또는 확인자료 없음")
    normalized.setdefault("reference_date", None)
    reference_date = normalized.get("reference_date")
    if reference_date is not None:
        normalized["reference_date"] = str(reference_date)
    return normalized


def default_facts() -> dict[str, dict[str, Any]]:
    return {
        "housing_type": {"value": None, "source": unavailable_source()},
        "reference_value": {
            "amount": None,
            "value_type": "unknown",
            "source": unavailable_source(),
        },
        "mortgage": {
            "status": "unknown",
            "amount": None,
            "source": unavailable_source(),
        },
        "seizure": {
            "status": "unknown",
            "amount": None,
            "source": unavailable_source(),
        },
        "joint_collateral": {
            "status": "unknown",
            "amount": None,
            "source": unavailable_source(),
        },
        "officetel_use": {
            "status": "unknown",
            "value": None,
            "source": unavailable_source(),
        },
        "senior_tenant_deposits": {
            "status": "unknown",
            "amount": None,
            "source": unavailable_source(),
        },
    }


def demo_facts() -> dict[str, dict[str, Any]]:
    return {
        "housing_type": {
            "value": "다세대주택",
            "source": demo_source("해커톤 모의 매물 데이터"),
        },
        "reference_value": {
            "amount": 220_000_000,
            "value_type": "sample_estimated_value",
            "source": demo_source("해커톤 모의 매물 데이터"),
        },
        "mortgage": {
            "status": "exists",
            "amount": None,
            "source": demo_source("해커톤 모의 권리분석 데이터"),
        },
        "seizure": {
            "status": "none",
            "amount": None,
            "source": demo_source("해커톤 모의 권리분석 데이터"),
        },
        "joint_collateral": {
            "status": "unknown",
            "amount": None,
            "source": demo_source("해커톤 모의 권리분석 데이터"),
        },
        "officetel_use": {
            "status": "unknown",
            "value": None,
            "source": demo_source("해커톤 모의 매물 데이터"),
        },
        "senior_tenant_deposits": {
            "status": "unknown",
            "amount": None,
            "source": demo_source("해커톤 모의 권리분석 데이터"),
        },
    }


def merge_facts(
    facts: dict[str, dict[str, Any]], supplied: dict[str, Any] | None
) -> dict[str, dict[str, Any]]:
    if not supplied:
        return facts
    merged = {key: dict(value) for key, value in facts.items()}
    for key in merged:
        supplied_fact = supplied.get(key)
        if not supplied_fact:
            continue
        merged[key].update(supplied_fact)
        merged[key]["source"] = normalize_source(supplied_fact.get("source"))
    return merged


def has_negative_context(text: str, keyword_pattern: str) -> bool:
    return bool(
        re.search(
            rf"(?:{keyword_pattern}).{{0,12}}(?:없(?:음|다)?|말소\s*(?:완료|됨|되었)|해제\s*(?:완료|됨|되었))",
            text,
        )
        or re.search(
            rf"(?:없(?:음|다)?|말소\s*(?:완료|됨|되었)|해제\s*(?:완료|됨|되었)).{{0,12}}(?:{keyword_pattern})",
            text,
        )
    )


def fill_from_situation(
    facts: dict[str, dict[str, Any]], situation_text: str | None
) -> dict[str, dict[str, Any]]:
    if not situation_text:
        return facts
    text = re.sub(r"\s+", " ", situation_text.strip())
    source = user_source()

    if facts["housing_type"].get("value") is None:
        for keyword in (
            "아파트",
            "다가구주택",
            "다가구",
            "다세대주택",
            "다세대",
            "빌라",
            "오피스텔",
            "연립주택",
            "연립",
            "단독주택",
        ):
            if keyword in text:
                facts["housing_type"] = {
                    "value": canonical_housing(keyword),
                    "source": source,
                }
                break

    right_patterns = {
        "mortgage": r"근저당",
        "seizure": r"(?:압류|가압류)",
        "joint_collateral": r"공동담보",
    }
    for key, pattern in right_patterns.items():
        if facts[key].get("status") != "unknown" or not re.search(pattern, text):
            continue
        facts[key] = {
            "status": "none" if has_negative_context(text, pattern) else "exists",
            "amount": None,
            "source": source,
        }
    return facts


def guarantee_from_input(
    guarantee_fact: dict[str, Any] | None, demo_mode: bool
) -> dict[str, Any]:
    if guarantee_fact:
        return {
            "status": guarantee_fact["status"],
            "source": normalize_source(guarantee_fact.get("source")),
        }
    if demo_mode:
        return {
            "status": "unknown",
            "source": demo_source("반환보증 API 연동 전 샘플"),
        }
    return {"status": "unknown", "source": unavailable_source()}


def money_display(amount: int | float | None) -> str:
    if amount is None:
        return "확인 필요"
    return f"{int(amount):,}원"


def source_public(source: dict[str, Any], known: bool) -> dict[str, Any]:
    normalized = normalize_source(source)
    return {
        **normalized,
        "is_verified": bool(
            known and normalized["source_type"] in CONFIRMED_SOURCE_TYPES
        ),
    }


def right_card(
    key: str,
    label: str,
    fact: dict[str, Any],
) -> dict[str, Any]:
    status = fact.get("status", "unknown")
    amount = fact.get("amount")
    labels = {
        "mortgage": {
            "exists": "선순위 근저당 있음",
            "none": "확인된 내역 없음",
            "unknown": "확인 필요",
        },
        "seizure": {
            "exists": "압류·가압류 있음",
            "none": "확인된 내역 없음",
            "unknown": "확인 필요",
        },
        "joint_collateral": {
            "exists": "공동담보 설정 있음",
            "none": "공동담보 설정 없음",
            "unknown": "확인 필요",
        },
    }
    descriptions = {
        "mortgage": {
            "exists": "채권최고액과 잔금 전 실제 말소 여부를 추가로 확인해야 합니다.",
            "none": "최신 등기사항증명서에서 다시 확인해야 합니다.",
            "unknown": "최신 등기사항증명서에서 근저당과 채권최고액을 확인해야 합니다.",
        },
        "seizure": {
            "exists": "권리 해제 여부와 계약 진행 가능성을 전문가와 확인해야 합니다.",
            "none": "최신 공식 서류에서 다시 확인해야 합니다.",
            "unknown": "압류·가압류 내역을 최신 공식 서류에서 확인해야 합니다.",
        },
        "joint_collateral": {
            "exists": "다른 부동산과 함께 담보로 설정된 범위와 순위를 확인해야 합니다.",
            "none": "최신 공식 서류에서 다시 확인해야 합니다.",
            "unknown": "다른 부동산과 함께 담보로 설정됐는지 확인해야 합니다.",
        },
    }
    state = "warning" if status == "exists" else "confirmed"
    if status == "unknown":
        state = "check_required"
    return {
        "key": key,
        "label": label,
        "value": status,
        "display_value": labels[key][status],
        "state": state,
        "description": descriptions[key][status],
        "details": {"amount": amount},
        "source": source_public(fact["source"], status in KNOWN_RIGHT_STATUSES),
    }


def build_property_cards(facts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    housing_value = facts["housing_type"].get("value")
    reference_amount = facts["reference_value"].get("amount")
    cards = [
        {
            "key": "housing_type",
            "label": "주택유형",
            "value": housing_value,
            "display_value": housing_value or "확인 필요",
            "state": "info" if housing_value else "check_required",
            "description": (
                "건축물대장상 주택유형입니다."
                if housing_value
                else "건축물대장 등 공식 자료에서 주택유형을 확인해야 합니다."
            ),
            "details": {},
            "source": source_public(facts["housing_type"]["source"], bool(housing_value)),
        },
        {
            "key": "reference_value",
            "label": "참고 주택가액",
            "value": reference_amount,
            "display_value": money_display(reference_amount),
            "state": "info" if reference_amount is not None else "check_required",
            "description": (
                "위험분석에 사용하는 참고값이며 실제 시세나 공식 가입판정과 다를 수 있습니다."
                if reference_amount is not None
                else "공시가격·감정평가 등 산정 근거와 기준일을 확인해야 합니다."
            ),
            "details": {
                "value_type": facts["reference_value"].get("value_type", "unknown")
            },
            "source": source_public(
                facts["reference_value"]["source"], reference_amount is not None
            ),
        },
        right_card("mortgage", "근저당", facts["mortgage"]),
        right_card("seizure", "압류·가압류", facts["seizure"]),
        right_card("joint_collateral", "공동담보", facts["joint_collateral"]),
    ]
    return cards


def build_guarantee(
    product_type: str, guarantee_fact: dict[str, Any]
) -> dict[str, Any]:
    status = guarantee_fact.get("status", "unknown")
    config = GUARANTEE_STATUSES[status]
    group_key = config["group"]
    group = GUARANTEE_GROUPS[group_key]
    source = source_public(guarantee_fact["source"], status != "unknown")
    return {
        "product_type": product_type,
        "product_label": PRODUCT_LABELS[product_type],
        "status": status,
        "display_text": config["display_text"],
        "headline": f"반환보증 {config['display_text']}",
        "group": group_key,
        "group_order": group["order"],
        "group_display_text": group["display_text"],
        "summary": config["summary"],
        "warning": config["warning"],
        "is_enrolled": status == "enrolled",
        "actions": list(config["actions"]),
        "source": source,
    }


def analysis_item(
    code: str,
    title: str,
    severity: str,
    fact_key: str,
    source: dict[str, Any],
    description: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "title": title,
        "severity": severity,
        "fact_key": fact_key,
        "source_type": source.get("source_type", "unknown"),
        "source_name": source.get("source_name", "연동 또는 확인자료 없음"),
        "description": description or title,
    }


def determine_risk_stage(
    confirmed_risks: list[dict[str, Any]], required_checks: list[dict[str, Any]]
) -> str:
    high_count = sum(item["severity"] == "high" for item in confirmed_risks)
    medium_count = sum(item["severity"] == "medium" for item in confirmed_risks)
    if high_count >= 2:
        return "계약 전 재검토"
    if high_count == 1 or medium_count >= 2:
        return "주의"
    if confirmed_risks or required_checks:
        return "추가 확인 필요"
    return "기본 확인"


def type_specific_field_key(facts: dict[str, Any]) -> str | None:
    housing_type = canonical_housing(facts["housing_type"].get("value"))
    if housing_type == "다가구주택":
        return "senior_tenant_deposits"
    if housing_type and "오피스텔" in housing_type:
        return "officetel_use"
    return None


def reference_value_is_verified(fact: dict[str, Any]) -> bool:
    source = normalize_source(fact.get("source"))
    return bool(
        fact.get("amount") is not None
        and fact.get("value_type") not in {None, "", "unknown"}
        and source["source_type"] in CONFIRMED_SOURCE_TYPES
        and source.get("source_name")
        and source.get("reference_date")
    )


def known_field(field_key: str, facts: dict[str, Any], guarantee: dict[str, Any]) -> bool:
    if field_key == "guarantee":
        return guarantee["status"] in {
            "officially_eligible",
            "applied",
            "enrolled",
            "ineligible",
        }
    fact = facts[field_key]
    if field_key == "housing_type":
        return bool(fact.get("value"))
    if field_key == "reference_value":
        return reference_value_is_verified(fact)
    if field_key == "officetel_use":
        return fact.get("status") in {"residential", "business"}
    if field_key == "senior_tenant_deposits":
        return fact.get("status") == "confirmed"
    return fact.get("status") in KNOWN_RIGHT_STATUSES


def calculate_analysis_confidence(
    facts: dict[str, Any], guarantee: dict[str, Any]
) -> int:
    total = sum(FIELD_WEIGHTS.values())
    confirmed = 0
    for field_key, weight in FIELD_WEIGHTS.items():
        field = guarantee if field_key == "guarantee" else facts[field_key]
        source_type = field["source"].get("source_type")
        if source_type in CONFIRMED_SOURCE_TYPES and known_field(
            field_key, facts, guarantee
        ):
            confirmed += weight
    type_field_key = type_specific_field_key(facts)
    if type_field_key:
        total += 1
        field = facts[type_field_key]
        if (
            field["source"].get("source_type") in CONFIRMED_SOURCE_TYPES
            and known_field(type_field_key, facts, guarantee)
        ):
            confirmed += 1
    return round(confirmed / total * 100) if total else 0


def build_analysis(
    planned_deposit: int,
    facts: dict[str, dict[str, Any]],
    guarantee: dict[str, Any],
    situation_text: str | None = None,
) -> dict[str, Any]:
    confirmed: list[dict[str, Any]] = []
    required: list[dict[str, Any]] = []

    rights_rules = {
        "mortgage": (
            "MORTGAGE_EXISTS",
            "선순위 근저당 확인",
            "MORTGAGE_UNKNOWN",
            "근저당과 채권최고액 확인 필요",
            "high",
        ),
        "seizure": (
            "SEIZURE_EXISTS",
            "압류·가압류 확인",
            "SEIZURE_UNKNOWN",
            "압류·가압류 여부 확인 필요",
            "high",
        ),
        "joint_collateral": (
            "JOINT_COLLATERAL_EXISTS",
            "공동담보 설정 확인",
            "JOINT_COLLATERAL_UNKNOWN",
            "공동담보 여부 확인 필요",
            "medium",
        ),
    }
    for key, (risk_code, risk_title, check_code, check_title, severity) in rights_rules.items():
        fact = facts[key]
        if fact["status"] == "exists":
            confirmed.append(
                analysis_item(
                    risk_code, risk_title, severity, key, normalize_source(fact["source"])
                )
            )
        elif fact["status"] == "unknown":
            required.append(
                analysis_item(
                    check_code,
                    check_title,
                    "check",
                    key,
                    normalize_source(fact["source"]),
                )
            )

    housing_fact = facts["housing_type"]
    if not housing_fact.get("value"):
        required.append(
            analysis_item(
                "HOUSING_TYPE_UNKNOWN",
                "주택유형 확인 필요",
                "check",
                "housing_type",
                normalize_source(housing_fact["source"]),
            )
        )

    housing_type = canonical_housing(housing_fact.get("value"))
    if housing_type == "다가구주택":
        senior_fact = facts["senior_tenant_deposits"]
        if senior_fact.get("status") != "confirmed":
            required.append(
                analysis_item(
                    "SENIOR_TENANT_DEPOSITS_UNKNOWN",
                    "다가구 선순위 임차보증금 확인 필요",
                    "check",
                    "senior_tenant_deposits",
                    normalize_source(senior_fact["source"]),
                )
            )
    if housing_type and "오피스텔" in housing_type:
        use_fact = facts["officetel_use"]
        if use_fact.get("status") not in {"residential", "business"}:
            required.append(
                analysis_item(
                    "OFFICETEL_USE_UNKNOWN",
                    "오피스텔의 실제 용도 확인 필요",
                    "check",
                    "officetel_use",
                    normalize_source(use_fact["source"]),
                )
            )

    reference_fact = facts["reference_value"]
    reference_amount = reference_fact.get("amount")
    reference_source = normalize_source(reference_fact["source"])
    ratio_pct = None
    if reference_amount and reference_amount > 0:
        ratio = planned_deposit / reference_amount
        ratio_pct = round(ratio * 100, 1)
        if ratio >= DEPOSIT_RATIO_CHECK_THRESHOLD:
            confirmed.append(
                analysis_item(
                    "HIGH_DEPOSIT_RATIO",
                    "참고가액 대비 높은 보증금 비율",
                    "medium",
                    "reference_value",
                    reference_source,
                )
            )
        if not reference_value_is_verified(reference_fact):
            required.append(
                analysis_item(
                    "REFERENCE_VALUE_UNVERIFIED",
                    "주택가액 산정 근거 확인 필요",
                    "check",
                    "reference_value",
                    reference_source,
                )
            )
    else:
        required.append(
            analysis_item(
                "REFERENCE_VALUE_UNKNOWN",
                "참고 주택가액 확인 필요",
                "check",
                "reference_value",
                reference_source,
            )
        )

    guarantee_status = guarantee["status"]
    guarantee_source = normalize_source(guarantee["source"])
    if guarantee_status == "ineligible":
        confirmed.append(
            analysis_item(
                "GUARANTEE_INELIGIBLE",
                "반환보증 가입 어려움 또는 불가",
                "high",
                "guarantee",
                guarantee_source,
            )
        )
    elif guarantee_status == "unknown":
        required.append(
            analysis_item(
                "GUARANTEE_UNKNOWN",
                "반환보증 상태 확인 필요",
                "check",
                "guarantee",
                guarantee_source,
            )
        )
    elif guarantee_status == "estimated_eligible":
        required.append(
            analysis_item(
                "GUARANTEE_ESTIMATED_ONLY",
                "반환보증 공식 사전확인 필요",
                "check",
                "guarantee",
                guarantee_source,
            )
        )
    elif guarantee_status in {"officially_eligible", "applied"}:
        required.append(
            analysis_item(
                "GUARANTEE_ENROLLMENT_NOT_COMPLETE",
                "반환보증 실제 가입 완료 여부 확인 필요",
                "check",
                "guarantee",
                guarantee_source,
            )
        )

    clean_situation = situation_text or ""
    if re.search(
        r"(?:다운\s*계약|계약서.{0,15}(?:낮게|낮춰|줄여).{0,12}(?:작성|기재)|"
        r"(?:실제|보증금|금액).{0,20}(?:낮게|낮춰|줄여).{0,20}계약서.{0,12}(?:작성|기재))",
        clean_situation,
    ):
        confirmed.append(
            analysis_item(
                "DOWN_CONTRACT_REQUESTED",
                "다운계약 요구 확인",
                "high",
                "situation_text",
                user_source(),
                "사용자 설명에 실제 금액보다 낮은 금액으로 계약서를 작성하라는 요구가 명시됐습니다.",
            )
        )

    confidence = calculate_analysis_confidence(facts, guarantee)
    risk_stage = determine_risk_stage(confirmed, required)
    return {
        "risk_stage": risk_stage,
        "risk_stage_notice": (
            "기본 확인은 계약이 안전하다는 뜻이 아닙니다. 현재 확인된 자료에서 "
            "강한 위험신호가 발견되지 않았다는 의미이며 공식 서류와 반환보증을 다시 확인해야 합니다."
            if risk_stage == "기본 확인"
            else "위험단계는 현재 확인된 사실과 미확인 정보에 따른 계약 전 점검 단계입니다."
        ),
        "confirmed_risk_count": len(confirmed),
        "required_check_count": len(required),
        "analysis_confidence": confidence,
        "analysis_confidence_notice": (
            "분석 신뢰도는 필수정보가 공식자료 또는 사용자 확인으로 채워진 정도이며 "
            "안전도나 사고확률이 아닙니다."
        ),
        "deposit_to_reference_ratio_pct": ratio_pct,
        "deposit_ratio_rule_notice": (
            "90% 기준은 MVP의 추가확인 신호이며 반환보증 공식 가입판정 기준이 아닙니다."
            if ratio_pct is not None
            else None
        ),
        "confirmed_risks": confirmed,
        "required_checks": required,
    }


def build_checklist(
    guarantee_public: dict[str, Any], analysis: dict[str, Any]
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for action in guarantee_public["actions"]:
        items.append(
            {
                "id": f"CHECK-{len(items) + 1:02d}",
                "title": action,
                "reason": "반환보증 상태 확인",
                "priority": "high" if len(items) == 0 else "medium",
                "completed": False,
            }
        )
    for risk in analysis["confirmed_risks"]:
        title = {
            "MORTGAGE_EXISTS": "잔금 전 근저당 말소 여부와 채권최고액 확인",
            "SEIZURE_EXISTS": "압류·가압류 해제 여부 확인",
            "JOINT_COLLATERAL_EXISTS": "공동담보 범위와 권리순위 확인",
            "HIGH_DEPOSIT_RATIO": "주택가액 산정 근거와 보증금 조정 가능성 확인",
            "GUARANTEE_INELIGIBLE": "반환보증 불가 사유와 계약조건 변경 검토",
        }.get(risk["code"])
        if title and title not in {item["title"] for item in items}:
            items.append(
                {
                    "id": f"CHECK-{len(items) + 1:02d}",
                    "title": title,
                    "reason": risk["title"],
                    "priority": risk["severity"],
                    "completed": False,
                }
            )
    return items[:8]


def senior_rights_for_search(facts: dict[str, dict[str, Any]]) -> str | None:
    if facts["mortgage"]["status"] == "exists":
        return "근저당"
    if facts["seizure"]["status"] == "exists":
        return "압류·가압류"
    if facts["joint_collateral"]["status"] == "exists":
        return "공동담보"
    return None


def public_similar_case(case: dict[str, Any]) -> dict[str, Any]:
    enriched = enrich_similar_case(case)
    enriched.pop("source_summary", None)
    return enriched


def build_contract_response(
    *,
    address: str,
    planned_deposit: int,
    situation_text: str | None,
    product_type: str,
    property_facts: dict[str, Any] | None,
    guarantee_fact: dict[str, Any] | None,
    demo_mode: bool,
    top_k: int,
    search_engine: SimilarCaseSearchEngine,
    context_repository: Any,
    property_identity: dict[str, Any] | None = None,
    location_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected_product = canonical_product_type(product_type)
    if property_identity:
        display_address = property_identity["display_address"]
        region_sido = property_identity.get("region_sido")
        region_sigungu = property_identity.get("region_sigungu")
        property_id = property_identity["property_id"]
        is_mock = bool(property_identity.get("is_mock"))
    else:
        display_address, region_sido, region_sigungu = address_identity(address)
        if demo_mode:
            display_address += " (모의 매물·실제 주소 아님)"
        property_id = make_property_id(address)
        is_mock = demo_mode

    facts = demo_facts() if demo_mode else default_facts()
    facts = merge_facts(facts, property_facts)
    facts = fill_from_situation(facts, situation_text)
    guarantee_internal = guarantee_from_input(guarantee_fact, demo_mode)
    property_cards = build_property_cards(facts)
    guarantee_public = build_guarantee(selected_product, guarantee_internal)
    analysis = build_analysis(
        planned_deposit, facts, guarantee_internal, situation_text
    )

    search_property = {
        "property_id": property_id,
        "region_sido": region_sido,
        "region_sigungu": region_sigungu,
        "guarantee_product_type": selected_product,
        "housing_type": facts["housing_type"].get("value"),
        "deposit": planned_deposit,
        "senior_rights": senior_rights_for_search(facts),
        "guarantee_status": guarantee_internal["status"],
    }
    ai_search_status = "ok"
    warnings: list[str] = []
    try:
        raw_cases = search_engine.search(
            {key: value for key, value in search_property.items() if value is not None},
            {
                "confirmed_risks": analysis["confirmed_risks"],
                "required_checks": analysis["required_checks"],
            },
            situation_text,
            top_k,
        )
        similar_cases = [public_similar_case(case) for case in raw_cases]
    except Exception:
        similar_cases = []
        ai_search_status = "unavailable"
        warnings.append(
            "유사사례 검색을 일시적으로 사용할 수 없어 위험분석 결과만 제공합니다."
        )
    product_context = context_repository.get_context(
        selected_product,
        facts["housing_type"].get("value"),
        region_sido,
    )
    data_usage = context_repository.get_data_usage(selected_product)

    return {
        "property": {
            "property_id": search_property["property_id"],
            "display_address": display_address,
            "region_sido": region_sido,
            "region_sigungu": region_sigungu,
            "is_mock": is_mock,
            "planned_deposit": planned_deposit,
            "planned_deposit_display": money_display(planned_deposit),
            "privacy_notice": (
                "상세주소는 응답·분석 로그에 포함하지 않고 축약 주소와 property_id만 사용합니다."
            ),
        },
        "property_snapshot": {
            "cards": property_cards,
            "notice": (
                "주택유형·가액·권리정보는 서로 출처가 다를 수 있어 각 카드에 출처와 기준일을 표시합니다."
            ),
        },
        "guarantee": guarantee_public,
        "analysis": analysis,
        "similar_cases": similar_cases,
        "checklist": build_checklist(guarantee_public, analysis),
        "historical_context": product_context,
        "data_usage": data_usage,
        "location_context": location_context
        or {
            "included_in_risk_score": False,
            "items": [],
            "source_type": "unknown",
            "source_name": "연동된 공식 입지자료 없음",
            "reference_date": None,
            "notice": "철도계획·재개발·고도제한 정보는 공식 출처 연동 전에는 생성하지 않습니다.",
        },
        "meta": {
            "schema_version": "3.0",
            "analysis_version": "v0.3",
            "selected_product_type": selected_product,
            "selected_product_label": PRODUCT_LABELS[selected_product],
            "data_source_count": context_repository.data_source_count,
            "is_accident_probability": False,
            "ai_search_status": ai_search_status,
            "warnings": warnings,
            "notice": (
                "이 결과는 계약 전 확인을 돕는 참고정보이며 전세사기 여부, 법률 결론, "
                "반환보증 공식 가입 가능 여부를 확정하지 않습니다."
            ),
        },
    }


def contract_options() -> dict[str, Any]:
    return {
        "guarantee_products": [
            {"value": "jeonse_return", "label": PRODUCT_LABELS["jeonse_return"]},
            {"value": "rental_deposit", "label": PRODUCT_LABELS["rental_deposit"]},
        ],
        "guarantee_statuses": [
            {
                "value": status,
                "label": config["display_text"],
                "group": config["group"],
            }
            for status, config in GUARANTEE_STATUSES.items()
        ],
        "guarantee_groups": [
            {
                "value": group,
                "label": config["display_text"],
                "order": config["order"],
            }
            for group, config in GUARANTEE_GROUPS.items()
        ],
        "source_types": [
            {"value": "official", "label": "공식 자료"},
            {"value": "user_confirmed", "label": "사용자 확인"},
            {"value": "mock", "label": "모의 자료"},
            {"value": "unknown", "label": "자료 없음"},
        ],
    }
