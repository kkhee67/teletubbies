from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from easy_explanation import enrich_similar_case
from guarantee_products import (
    PRODUCT_LABELS,
    UNKNOWN_PRODUCT,
    canonical_product_type,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES_PATH = PROJECT_ROOT / "data" / "processed" / "structured_cases.jsonl"

TEXT_WEIGHT = 0.45
HOUSING_WEIGHT = 0.25
RIGHTS_WEIGHT = 0.15
GUARANTEE_WEIGHT = 0.10
DEPOSIT_WEIGHT = 0.05
PRODUCT_WEIGHT = 0.10

UNKNOWN_VALUES = {"", "미상", "unknown", "none", "null"}

HOUSING_ALIASES = {
    "아파트": "아파트",
    "다가구": "다가구주택",
    "다가구주택": "다가구주택",
    "다세대": "다세대주택",
    "다세대주택": "다세대주택",
    "빌라": "다세대주택",
    "오피스텔": "오피스텔",
    "기타(오피스텔)": "오피스텔",
    "연립": "연립주택",
    "연립주택": "연립주택",
    "단독": "단독주택",
    "단독주택": "단독주택",
    "원룸": "원룸·도시형",
    "도시형생활주택": "원룸·도시형",
    "원룸·도시형": "원룸·도시형",
}

RIGHTS_ALIASES = {
    "근저당": "근저당",
    "근저당설정": "근저당",
    "압류": "압류·가압류",
    "가압류": "압류·가압류",
    "압류·가압류": "압류·가압류",
    "선순위존재": "선순위권리",
    "선순위권리": "선순위권리",
    "공동담보": "공동담보",
    "신탁": "신탁",
    "후순위": "후순위",
}

ANALYSIS_CODE_TAGS = {
    "MORTGAGE_EXISTS": "근저당",
    "JOINT_COLLATERAL_EXISTS": "공동담보",
    "SEIZURE_EXISTS": "압류·가압류",
    "TRUST_EXISTS": "신탁",
    "JUNIOR_PRIORITY": "후순위",
    "SENIOR_RIGHT_EXISTS": "선순위권리",
    "AUCTION_EXISTS": "경매·공매",
    "LEASEHOLD_REGISTRATION": "임차권등기",
}

GUARANTEE_GROUPS = {
    "estimated_eligible": "check_required",
    "unknown": "check_required",
    "officially_eligible": "in_progress",
    "applied": "in_progress",
    "enrolled": "protected",
    "ineligible": "deep_analysis",
}

GUARANTEE_STATUS_ALIASES = {
    "미상": "unknown",
    "미가입": "unknown",
    "가입": "enrolled",
    "가입 완료": "enrolled",
    "가입 불가": "ineligible",
}

GUARANTEE_MATCH_LABELS = {
    "check_required": "반환보증 확인 필요",
    "in_progress": "반환보증 가입 절차",
    "protected": "반환보증 가입 완료",
    "deep_analysis": "반환보증 가입 어려움",
}

PUBLIC_CASE_SOURCE_NAME = "발제사 제공 비식별 합성 상담사례"

CONTEXT_PATTERNS = {
    "공동담보": r"공동담보",
    "말소 약속": r"(?:말소.{0,12}(?:약속|하기로|한다고|예정)|약속.{0,12}말소)",
    "신탁": r"신탁",
    "후순위": r"후순위",
    "경매·공매": r"(?:경매|공매)",
    "임차권등기": r"임차권등기",
}


def known_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in UNKNOWN_VALUES:
        return None
    return text


def canonical_housing(value: Any) -> str | None:
    text = known_value(value)
    if text is None:
        return None
    return HOUSING_ALIASES.get(text, text)


def canonical_right(value: Any) -> str | None:
    text = known_value(value)
    if text is None:
        return None
    if text in RIGHTS_ALIASES:
        return RIGHTS_ALIASES[text]
    for keyword, canonical in RIGHTS_ALIASES.items():
        if keyword in text:
            return canonical
    return text


def deposit_to_range(amount: Any) -> str | None:
    if amount is None or amount == "":
        return None
    if isinstance(amount, str):
        normalized = amount.replace(",", "").replace("원", "").strip()
        if normalized in {"1억 미만", "1억~2억", "2억~3억", "3억 이상"}:
            return normalized
        try:
            amount = int(normalized)
        except ValueError:
            return None
    amount = int(amount)
    if amount < 100_000_000:
        return "1억 미만"
    if amount < 200_000_000:
        return "1억~2억"
    if amount < 300_000_000:
        return "2억~3억"
    return "3억 이상"


def guarantee_group(status: Any) -> str | None:
    if status is None:
        return None
    text = str(status).strip()
    if not text or text.lower() in {"none", "null"}:
        return None
    text = GUARANTEE_STATUS_ALIASES.get(text, text)
    return GUARANTEE_GROUPS.get(text)


def normalize_guarantee_status(status: Any) -> str | None:
    if status is None:
        return None
    text = str(status).strip()
    if not text or text.lower() in {"none", "null"}:
        return None
    return GUARANTEE_STATUS_ALIASES.get(text, text)


def calculate_final_score(
    text_similarity: float,
    housing_type_match: float,
    rights_match: float,
    guarantee_group_match: float,
    deposit_range_match: float,
    product_type_match: float | None = None,
) -> float:
    base_score = (
        TEXT_WEIGHT * text_similarity
        + HOUSING_WEIGHT * housing_type_match
        + RIGHTS_WEIGHT * rights_match
        + GUARANTEE_WEIGHT * guarantee_group_match
        + DEPOSIT_WEIGHT * deposit_range_match
    )
    if product_type_match is None:
        return base_score
    return (1 - PRODUCT_WEIGHT) * base_score + PRODUCT_WEIGHT * product_type_match


def analysis_terms(items: Any) -> set[str]:
    if not items:
        return set()
    if not isinstance(items, list):
        items = [items]

    terms: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            code = known_value(item.get("code"))
            title = known_value(item.get("title"))
            if code in ANALYSIS_CODE_TAGS:
                terms.add(ANALYSIS_CODE_TAGS[code])
            if title:
                terms.add(title)
        else:
            text = known_value(item)
            if text:
                terms.add(ANALYSIS_CODE_TAGS.get(text, text))
    return terms


def text_context_tags(text: str | None) -> set[str]:
    clean_text = known_value(text)
    if not clean_text:
        return set()
    return {
        tag
        for tag, pattern in CONTEXT_PATTERNS.items()
        if re.search(pattern, clean_text)
    }


def get_property_value(property_data: dict, *keys: str) -> Any:
    for key in keys:
        if key in property_data:
            return property_data[key]
    return None


@dataclass(frozen=True)
class QueryContext:
    product_type: str | None
    housing_type: str | None
    deposit_range: str | None
    rights_tags: frozenset[str]
    guarantee_status: str | None
    guarantee_group: str | None
    context_tags: frozenset[str]
    query_text: str

    @property
    def has_structured_condition(self) -> bool:
        return bool(
            self.product_type
            or self.housing_type
            or self.deposit_range
            or self.rights_tags
            or self.guarantee_group
        )


def build_query_context(
    property_data: dict, analysis: dict, user_text: str | None
) -> QueryContext:
    product_value = get_property_value(
        property_data,
        "guarantee_product_type",
        "product_type",
        "보증상품유형",
    )
    guarantee_data = get_property_value(property_data, "guarantee")
    if isinstance(guarantee_data, dict):
        product_value = guarantee_data.get("product_type", product_value)
    normalized_product = canonical_product_type(product_value)
    product_type = (
        normalized_product if normalized_product != UNKNOWN_PRODUCT else None
    )

    housing_type = canonical_housing(
        get_property_value(property_data, "housing_type", "주택유형")
    )
    deposit_range = deposit_to_range(
        get_property_value(
            property_data,
            "deposit_range",
            "planned_deposit",
            "deposit",
            "보증금",
        )
    )

    rights_tags = analysis_terms(analysis.get("confirmed_risks"))
    property_right = canonical_right(
        get_property_value(
            property_data, "senior_rights", "mortgage_status", "선순위권리"
        )
    )
    if property_right:
        rights_tags.add(property_right)

    guarantee_status = normalize_guarantee_status(
        get_property_value(
            property_data, "guarantee_status", "guarantee", "반환보증상태"
        )
    )
    if isinstance(get_property_value(property_data, "guarantee"), dict):
        guarantee_status = normalize_guarantee_status(
            property_data["guarantee"].get("status")
        )
    guarantee_group_value = guarantee_group(guarantee_status)

    text_parts = []
    if product_type:
        text_parts.append(f"보증상품 {PRODUCT_LABELS[product_type]}")
    if housing_type:
        text_parts.append(f"주택유형 {housing_type}")
    if deposit_range:
        text_parts.append(f"보증금구간 {deposit_range}")
    if rights_tags:
        text_parts.append("위험맥락 " + " ".join(sorted(rights_tags)))
    if guarantee_status:
        text_parts.append(f"반환보증 {guarantee_status}")

    required_checks = analysis_terms(analysis.get("required_checks"))
    if required_checks:
        text_parts.append("확인필요 " + " ".join(sorted(required_checks)))
    clean_user_text = known_value(user_text)
    context_tags = text_context_tags(clean_user_text)
    if context_tags:
        text_parts.append("사건맥락 " + " ".join(sorted(context_tags)))
    if clean_user_text:
        text_parts.append(f"사용자설명 {clean_user_text}")
    if not text_parts:
        text_parts.append("임대차 계약 확인")

    return QueryContext(
        product_type=product_type,
        housing_type=housing_type,
        deposit_range=deposit_range,
        rights_tags=frozenset(rights_tags),
        guarantee_status=guarantee_status,
        guarantee_group=guarantee_group_value,
        context_tags=frozenset(context_tags),
        query_text=" | ".join(text_parts),
    )


class SimilarCaseSearchEngine:
    def __init__(self, cases_path: Path = DEFAULT_CASES_PATH):
        self.cases_path = Path(cases_path)
        self.cases = self._load_cases(self.cases_path)
        if not self.cases:
            raise ValueError("검색할 상담사례가 없습니다.")
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2))
        self.case_matrix = self.vectorizer.fit_transform(
            [case["search_text"] for case in self.cases]
        )

    @staticmethod
    def _load_cases(path: Path) -> list[dict]:
        with path.open("r", encoding="utf-8") as stream:
            return [json.loads(line) for line in stream if line.strip()]

    @staticmethod
    def _case_housing(case: dict) -> str | None:
        return canonical_housing(case["facts"].get("housing_type"))

    @staticmethod
    def _case_deposit_range(case: dict) -> str | None:
        return known_value(case["facts"].get("deposit_range"))

    @staticmethod
    def _case_rights_tags(case: dict) -> set[str]:
        tags = {
            canonical_right(tag) or tag for tag in case.get("confirmed_risk_tags", [])
        }
        field_tag = canonical_right(case["facts"].get("senior_rights"))
        if field_tag:
            tags.add(field_tag)
        return tags

    @staticmethod
    def _case_guarantee_group(case: dict) -> str | None:
        return guarantee_group(case["facts"].get("guarantee_status"))

    @staticmethod
    def _case_product_type(case: dict) -> str:
        return canonical_product_type(
            case["facts"].get("guarantee_product_type")
        )

    def _product_match(self, case: dict, query: QueryContext) -> float | None:
        if not query.product_type:
            return None
        case_product = self._case_product_type(case)
        if case_product == query.product_type:
            return 1.0
        if case_product == UNKNOWN_PRODUCT:
            return 0.5
        return 0.0

    def _structured_components(
        self, case: dict, query: QueryContext
    ) -> tuple[float, float, float, float]:
        housing_match = float(
            bool(query.housing_type)
            and self._case_housing(case) == query.housing_type
        )
        rights_match = float(
            bool(query.rights_tags)
            and bool(self._case_rights_tags(case) & set(query.rights_tags))
        )
        guarantee_match = float(
            bool(query.guarantee_group)
            and self._case_guarantee_group(case) == query.guarantee_group
        )
        deposit_match = float(
            bool(query.deposit_range)
            and self._case_deposit_range(case) == query.deposit_range
        )
        return housing_match, rights_match, guarantee_match, deposit_match

    def _candidate_indices(
        self, query: QueryContext, top_k: int, candidate_limit: int = 300
    ) -> list[int]:
        if not query.has_structured_condition:
            return list(range(len(self.cases)))

        ranked = []
        for index, case in enumerate(self.cases):
            case_product = self._case_product_type(case)
            if query.product_type and case_product != query.product_type:
                continue
            housing, rights, guarantee, deposit = self._structured_components(case, query)
            product_match = self._product_match(case, query) or 0.0
            structured_score = (
                HOUSING_WEIGHT * housing
                + RIGHTS_WEIGHT * rights
                + GUARANTEE_WEIGHT * guarantee
                + DEPOSIT_WEIGHT * deposit
                + PRODUCT_WEIGHT * product_match
            )
            ranked.append((structured_score, index))
        ranked.sort(key=lambda item: (-item[0], item[1]))

        minimum_candidates = min(len(ranked), max(100, top_k * 20))
        positive = [index for score, index in ranked if score > 0]
        if len(positive) < minimum_candidates:
            selected = [index for _, index in ranked[:minimum_candidates]]
        else:
            selected = positive[:candidate_limit]
        return selected[:candidate_limit]

    def search(
        self,
        property_data: dict,
        analysis: dict,
        user_text: str | None = None,
        top_k: int = 3,
    ) -> list[dict]:
        if top_k < 1:
            raise ValueError("top_k는 1 이상이어야 합니다.")

        query = build_query_context(property_data, analysis, user_text)
        candidate_indices = self._candidate_indices(query, top_k)
        if not candidate_indices:
            return []
        query_vector = self.vectorizer.transform([query.query_text])
        text_scores = cosine_similarity(
            query_vector, self.case_matrix[candidate_indices]
        )[0]

        ranked_results = []
        for candidate_position, case_index in enumerate(candidate_indices):
            case = self.cases[case_index]
            housing, rights, guarantee, deposit = self._structured_components(case, query)
            product_match = self._product_match(case, query)
            text_similarity = float(text_scores[candidate_position])
            final_score = calculate_final_score(
                text_similarity,
                housing,
                rights,
                guarantee,
                deposit,
                product_match,
            )
            matched_factors = self._matched_factors(
                case, query, housing, rights, guarantee, deposit
            )
            ranked_results.append(
                (
                    final_score,
                    text_similarity,
                    case["case_id"],
                    {
                        "case_id": case["case_id"],
                        "case_product_type": self._case_product_type(case),
                        "case_product_label": PRODUCT_LABELS[
                            self._case_product_type(case)
                        ],
                        "similarity": round(final_score, 4),
                        "similarity_label": "상담사례 유사도",
                        "matched_factors": matched_factors,
                        "confirmed_risk_tags": case["confirmed_risk_tags"],
                        "required_check_tags": case["required_check_tags"],
                        "dispute_type": case["dispute_type"],
                        "progress_stage": case["progress_stage"],
                        "source_summary": case["source_summary"],
                        "source": {
                            "source_type": case.get("source", {}).get(
                                "type", "provided_synthetic_consultations"
                            ),
                            "source_name": PUBLIC_CASE_SOURCE_NAME,
                            "is_synthetic": bool(
                                case.get("source", {}).get("is_synthetic", True)
                            ),
                        },
                        "disclaimer": (
                            "유사도는 위험 확률이나 사고 확률이 아닙니다. "
                            "비슷한 조건의 참고사례이며 동일한 피해를 예측하지 않습니다."
                        ),
                    },
                )
            )
        ranked_results.sort(key=lambda item: (-item[0], -item[1], item[2]))
        return [item[3] for item in ranked_results[:top_k]]

    def _matched_factors(
        self,
        case: dict,
        query: QueryContext,
        housing: float,
        rights: float,
        guarantee: float,
        deposit: float,
    ) -> list[str]:
        factors = []
        if (
            query.product_type
            and self._case_product_type(case) == query.product_type
        ):
            factors.append(PRODUCT_LABELS[query.product_type])
        if housing:
            factors.append(query.housing_type or "")
        if rights:
            common_tags = self._case_rights_tags(case) & set(query.rights_tags)
            factors.extend(sorted(common_tags))
        if guarantee and query.guarantee_group:
            factors.append(GUARANTEE_MATCH_LABELS[query.guarantee_group])
        if deposit:
            factors.append(query.deposit_range or "")
        if query.context_tags:
            factors.extend(
                sorted(set(case.get("confirmed_risk_tags", [])) & set(query.context_tags))
            )
        return list(dict.fromkeys(factor for factor in factors if factor))


@lru_cache(maxsize=1)
def default_engine() -> SimilarCaseSearchEngine:
    return SimilarCaseSearchEngine(DEFAULT_CASES_PATH)


def find_similar_cases(
    property_data: dict,
    analysis: dict,
    user_text: str | None,
    top_k: int = 3,
) -> list[dict]:
    results = default_engine().search(property_data, analysis, user_text, top_k)
    return [enrich_similar_case(result) for result in results]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="유사 상담사례 검색")
    parser.add_argument("--guarantee-product-type")
    parser.add_argument("--housing-type")
    parser.add_argument("--deposit", type=int)
    parser.add_argument("--senior-rights")
    parser.add_argument("--guarantee-status")
    parser.add_argument("--user-text")
    parser.add_argument("--top-k", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    property_data = {
        "guarantee_product_type": args.guarantee_product_type,
        "housing_type": args.housing_type,
        "deposit": args.deposit,
        "senior_rights": args.senior_rights,
        "guarantee_status": args.guarantee_status,
    }
    results = find_similar_cases(property_data, {}, args.user_text, args.top_k)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
