from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any


SYSTEM_PROMPT = """역할: 임대차 상담사례를 고등학생도 이해하도록 설명한다.
사용 가능 정보: 제공된 일치요인, confirmed_risk_tags, required_check_tags,
분쟁유형, 진행단계만 사용한다.
금지: 원문에 없는 사실 추측, 전세사기 확정, 승소 가능성 판단,
반환보증 가입 가능 여부 확정, 사용자 매물에 같은 피해가 발생한다고 예측.
출력: JSON 객체로 easy_explanation 4문장 이하와 actions 2개를 작성한다."""

SITUATION_SENTENCES = {
    "근저당": "이 상담사례에서는 주택에 근저당이 설정된 사실이 확인되었습니다.",
    "공동담보": "이 상담사례에서는 여러 부동산이 하나의 담보로 묶여 있었습니다.",
    "말소 약속": "이 상담사례에서는 계약 상대방이 담보권을 나중에 없애겠다고 약속했습니다.",
    "압류·가압류": "이 상담사례에서는 주택에 압류 또는 가압류가 확인되었습니다.",
    "신탁": "이 상담사례에서는 주택의 신탁 관계가 확인되었습니다.",
    "후순위": "이 상담사례에서는 임차인의 권리 순서가 뒤에 놓인 상황이 확인되었습니다.",
    "선순위권리": "이 상담사례에서는 임차인보다 앞선 권리가 확인되었습니다.",
    "경매·공매": "이 상담사례에서는 주택의 경매 또는 공매 절차가 다뤄졌습니다.",
    "임차권등기": "이 상담사례에서는 임차권등기 절차가 진행되었습니다.",
}

REASON_SENTENCES = {
    "근저당": "다른 권리자가 임차인보다 먼저 돈을 받을 수 있어 채권최고액과 권리 순서를 확인해야 합니다.",
    "공동담보": "함께 묶인 다른 부동산의 상황도 보증금 회수에 영향을 줄 수 있어 담보목록 확인이 필요합니다.",
    "말소 약속": "말로 한 약속과 실제 등기 변경은 다를 수 있어 말소 완료 여부를 서류로 확인해야 합니다.",
    "압류·가압류": "재산 처분이 제한되거나 다른 채권자의 권리가 먼저 작용할 수 있어 등기 내용을 확인해야 합니다.",
    "신탁": "등기상 소유자와 임대 권한을 가진 사람이 다를 수 있어 계약 권한 확인이 필요합니다.",
    "후순위": "앞선 권리의 금액이 크면 보증금을 돌려받는 순서에 영향을 줄 수 있습니다.",
    "선순위권리": "먼저 돈을 받을 권리의 종류와 금액을 알아야 보증금 회수 가능성을 판단할 수 있습니다.",
    "경매·공매": "절차의 진행 단계와 배당 순서에 따라 보증금 회수 과정이 달라질 수 있습니다.",
    "임차권등기": "권리를 보전하기 위해 진행된 절차이므로 신청 배경과 현재 상태를 확인해야 합니다.",
}

TAG_ACTIONS = {
    "근저당": "잔금 지급 전에 최신 등기부에서 근저당과 채권최고액을 확인하세요.",
    "공동담보": "등기부의 공동담보목록에서 함께 묶인 부동산을 확인하세요.",
    "말소 약속": "잔금 지급 직전에 등기부를 다시 열어 실제 말소 완료 여부를 확인하세요.",
    "압류·가압류": "최신 등기부에서 압류·가압류의 권리자와 등기일자를 확인하세요.",
    "신탁": "등기부의 수탁자와 임대차계약 권한을 확인하세요.",
    "후순위": "본인의 권리 순서와 앞선 채권의 총액을 확인하세요.",
    "선순위권리": "등기부와 임대인 제공자료로 선순위 권리의 종류와 금액을 확인하세요.",
    "경매·공매": "경매·공매 사건의 현재 단계와 배당요구 기한을 확인하세요.",
    "임차권등기": "임차권등기의 신청 배경과 현재 등기 상태를 확인하세요.",
}

CHECK_ACTIONS = {
    "주택유형 확인": "건축물대장에서 주택유형과 실제 용도를 확인하세요.",
    "보증금 확인": "계약서와 확인자료에서 계약 예정 보증금이 정확한지 확인하세요.",
    "계약상태 확인": "계약기간과 종료 예정일을 계약서에서 확인하세요.",
    "선순위권리 확인": "최신 등기부와 임대인 제공자료로 선순위 권리를 확인하세요.",
    "반환보증 확인": "보증기관의 공식 사전확인 절차로 반환보증 가입 가능 여부를 확인하세요.",
    "보증상품 유형 확인": "보증기관 자료에서 전세보증금반환보증인지 임대보증금보증인지 확인하세요.",
    "공동담보 여부 확인": "등기부의 공동담보목록이 있는지 확인하세요.",
}

DEFAULT_ACTIONS = [
    "계약 직전 최신 등기부와 건축물대장을 다시 확인하세요.",
    "보증기관의 공식 절차로 반환보증 상태를 확인하세요.",
]

DISPLAY_DISPUTE_TYPES = {
    # This is a source-case category, not a determination about the user's property.
    "전세사기": "보증금 반환 분쟁",
}

FORBIDDEN_PATTERNS = {
    "fraud_determination": r"(?:전세)?사기(?:입니다|다|로\s*확정|가\s*확실)",
    "certainty": r"(?:반드시|무조건|100\s*%|확실히)",
    "safety_determination": r"(?:안전한\s*매물|안전합니다|문제없습니다)",
    "guarantee_determination": r"(?:반환보증|보증보험).{0,10}(?:가입\s*확정|가입\s*가능합니다)",
    "lawsuit_determination": r"(?:승소합니다|소송에서\s*이깁니다|이길\s*수\s*있습니다)",
    "same_outcome_prediction": r"(?:같은|동일한)\s*피해.{0,10}(?:발생|예상)",
}

SUPPORTED_FACT_TERMS = {
    "근저당": {"근저당", "말소 약속"},
    "공동담보": {"공동담보", "공동담보 여부 확인"},
    "압류": {"압류·가압류"},
    "가압류": {"압류·가압류"},
    "신탁": {"신탁"},
    "후순위": {"후순위"},
    "경매": {"경매·공매"},
    "공매": {"경매·공매"},
    "임차권등기": {"임차권등기"},
    "말소": {"말소 약속"},
}


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def template_explanation(case: dict) -> dict:
    tags = case.get("confirmed_risk_tags", [])
    checks = case.get("required_check_tags", [])

    situation_sentences = [SITUATION_SENTENCES[tag] for tag in tags if tag in SITUATION_SENTENCES][
        :2
    ]
    if not situation_sentences:
        if checks:
            situation_sentences = [
                "이 상담사례에는 아직 확인되지 않은 계약정보가 있었습니다.",
                "확인되지 않았다는 사실만으로 위험이 확정되는 것은 아닙니다.",
            ]
        else:
            situation_sentences = [
                "이 상담사례의 구조화된 정보에서는 강한 위험신호가 확인되지 않았습니다.",
                "이 결과만으로 계약 위험이 없다고 판단할 수는 없습니다.",
            ]
    elif len(situation_sentences) == 1:
        dispute_type = case.get("dispute_type")
        if dispute_type and dispute_type not in {"미상", "기타·일반문의"}:
            display_dispute_type = DISPLAY_DISPUTE_TYPES.get(dispute_type, dispute_type)
            situation_sentences.append(
                f"상담 분류상 {display_dispute_type}와 관련된 사례였습니다."
            )

    reason_sentences = [REASON_SENTENCES[tag] for tag in tags if tag in REASON_SENTENCES][
        :2
    ]
    if not reason_sentences:
        reason_sentences = [
            "필요한 정보를 확인해야 현재 매물과 어느 정도 비슷한지 정확히 비교할 수 있습니다.",
            "공식 서류와 반환보증 상태를 별도로 확인해야 합니다.",
        ]
    elif len(reason_sentences) == 1 and checks:
        reason_sentences.append(
            "아직 확인되지 않은 정보는 위험으로 단정하지 말고 공식 서류로 확인해야 합니다."
        )

    actions = _unique(
        [TAG_ACTIONS[tag] for tag in tags if tag in TAG_ACTIONS]
        + [CHECK_ACTIONS[check] for check in checks if check in CHECK_ACTIONS]
        + DEFAULT_ACTIONS
    )[:2]

    return {
        "easy_explanation": " ".join(situation_sentences + reason_sentences),
        "actions": actions,
        "explanation_source": "template",
        "safety_passed": True,
    }


def build_llm_input(case: dict) -> tuple[str, str]:
    allowed_data = {
        "case_id": case.get("case_id"),
        "matched_factors": case.get("matched_factors", []),
        "confirmed_risk_tags": case.get("confirmed_risk_tags", []),
        "required_check_tags": case.get("required_check_tags", []),
        "dispute_type": case.get("dispute_type"),
        "progress_stage": case.get("progress_stage"),
        "case_product_type": case.get("case_product_type"),
        "case_product_label": case.get("case_product_label"),
    }
    return SYSTEM_PROMPT, json.dumps(allowed_data, ensure_ascii=False)


def validate_explanation(case: dict, explanation: str, actions: list[str]) -> list[str]:
    errors = []
    combined = " ".join([explanation, *actions])
    if not explanation.strip():
        errors.append("empty_explanation")
    if len(explanation) > 600:
        errors.append("explanation_too_long")
    sentence_count = len(re.findall(r"[.!?](?:\s|$)", explanation))
    if sentence_count > 4:
        errors.append("too_many_sentences")
    if len(actions) != 2 or any(not str(action).strip() for action in actions):
        errors.append("actions_must_have_two_items")

    for name, pattern in FORBIDDEN_PATTERNS.items():
        if re.search(pattern, combined):
            errors.append(name)

    context = set(case.get("confirmed_risk_tags", []))
    context.update(case.get("required_check_tags", []))
    context.update(case.get("matched_factors", []))
    for term, required_context in SUPPORTED_FACT_TERMS.items():
        if term in combined and not (context & required_context):
            errors.append(f"unsupported_fact:{term}")
    return _unique(errors)


def _normalize_generated_result(value: Any) -> tuple[str, list[str]]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("생성 결과는 JSON 객체여야 합니다.")
    explanation = str(value.get("easy_explanation", "")).strip()
    actions = value.get("actions", [])
    if not isinstance(actions, list):
        raise ValueError("actions는 목록이어야 합니다.")
    return explanation, [str(action).strip() for action in actions]


def generate_easy_explanation(
    case: dict,
    llm_generate: Callable[[str, str], Any] | None = None,
) -> dict:
    fallback = template_explanation(case)
    if llm_generate is None:
        return fallback

    try:
        system_prompt, user_prompt = build_llm_input(case)
        explanation, actions = _normalize_generated_result(
            llm_generate(system_prompt, user_prompt)
        )
        errors = validate_explanation(case, explanation, actions)
        if errors:
            return {**fallback, "explanation_source": "template_fallback"}
        return {
            "easy_explanation": explanation,
            "actions": actions,
            "explanation_source": "llm",
            "safety_passed": True,
        }
    except (TypeError, ValueError, json.JSONDecodeError):
        return {**fallback, "explanation_source": "template_fallback"}


def enrich_similar_case(
    case: dict,
    llm_generate: Callable[[str, str], Any] | None = None,
) -> dict:
    return {**case, **generate_easy_explanation(case, llm_generate)}
