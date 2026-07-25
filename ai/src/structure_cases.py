from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "consultations_clean.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "structured_cases.jsonl"
DEFAULT_REPORT = PROJECT_ROOT / "data" / "processed" / "structure_report.json"

REQUIRED_COLUMNS = {
    "case_id",
    "source_group",
    "region_sido",
    "region_sigungu",
    "deposit_range",
    "contract_status",
    "housing_type",
    "senior_rights",
    "guarantee_raw",
    "guarantee_product_type",
    "dispute_type",
    "progress_stage",
    "situation_summary_safe",
    "special_notes_safe",
    "search_text",
    "source_type",
}

GUARANTEE_STATUSES = {
    "estimated_eligible",
    "officially_eligible",
    "applied",
    "enrolled",
    "ineligible",
    "unknown",
}

RIGHTS_TAGS = {
    "근저당설정": "근저당",
    "압류·가압류": "압류·가압류",
    "선순위존재": "선순위권리",
}

TAG_ORDER = [
    "근저당",
    "공동담보",
    "말소 약속",
    "압류·가압류",
    "신탁",
    "후순위",
    "선순위권리",
    "경매·공매",
    "임차권등기",
]


def combined_case_text(row: Mapping[str, str]) -> str:
    return " ".join(
        part
        for part in [
            row.get("situation_summary_safe", ""),
            row.get("special_notes_safe", ""),
        ]
        if part
    )


def map_guarantee_status(raw_value: str, text: str) -> tuple[str, str]:
    raw_value = raw_value.strip()
    if raw_value == "가입":
        return "enrolled", "structured_field:가입"

    patterns = [
        (
            "ineligible",
            r"(?:(?:보증보험|반환보증).{0,12}(?:가입\s*)?(?:거절|불가)|가입(?:이|은|는)?\s*(?:거절|불가))",
        ),
        ("applied", r"(?:가입\s*신청|신청\s*접수|보증\s*심사\s*중)"),
        (
            "officially_eligible",
            r"(?:공식\s*)?사전\s*확인.{0,10}(?:가능|완료|적격)",
        ),
        (
            "estimated_eligible",
            r"(?:조건상.{0,8}가능|가입\s*가능성이\s*있|가입이?\s*가능해\s*보)",
        ),
        ("enrolled", r"(?:가입\s*완료|보증서\s*발급|보증보험에?\s*가입되어)"),
    ]
    for status, pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return status, f"summary:{match.group(0)}"
    return "unknown", f"structured_field:{raw_value or '미상'}"


def extract_confirmed_risk_tags(row: Mapping[str, str]) -> list[str]:
    tags: set[str] = set()
    rights_tag = RIGHTS_TAGS.get(row.get("senior_rights", ""))
    if rights_tag:
        tags.add(rights_tag)

    text = combined_case_text(row)
    if re.search(r"공동담보.{0,10}(?:설정|묶여|잡혀)|공동담보로", text):
        tags.add("공동담보")
    if re.search(
        r"말소.{0,12}(?:약속|하기로|예정|조건)|(?:약속|조건).{0,12}말소",
        text,
    ):
        tags.add("말소 약속")
    if re.search(r"(?:신탁등기|신탁회사|신탁된|신탁으로)", text):
        tags.add("신탁")
    if re.search(r"후순위(?:임차인|권리|채권|로)", text):
        tags.add("후순위")
    if row.get("dispute_type") == "경매·공매" or re.search(
        r"(?:(?:강제|임의)?경매|공매)(?:개시|신청|진행|낙찰)", text
    ):
        tags.add("경매·공매")
    if row.get("progress_stage") == "임차권등기" or re.search(
        r"임차권등기(?:명령|설정|신청|완료)", text
    ):
        tags.add("임차권등기")

    return [tag for tag in TAG_ORDER if tag in tags]


def extract_required_check_tags(
    row: Mapping[str, str], guarantee_status: str
) -> list[str]:
    checks: list[str] = []
    field_checks = [
        ("housing_type", "주택유형 확인"),
        ("deposit_range", "보증금 확인"),
        ("contract_status", "계약상태 확인"),
        ("senior_rights", "선순위권리 확인"),
    ]
    for field, title in field_checks:
        if row.get(field, "미상") == "미상":
            checks.append(title)
    if guarantee_status == "unknown":
        checks.append("반환보증 확인")
    if row.get("guarantee_product_type", "unknown") == "unknown":
        checks.append("보증상품 유형 확인")

    text = combined_case_text(row)
    if re.search(r"공동담보.{0,12}(?:모름|미상|미확인|확인\s*필요)", text):
        checks.append("공동담보 여부 확인")
    return checks


def make_source_summary(text: str, max_length: int = 300) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_length:
        return text

    prefix = text[: max_length + 1]
    sentence_end = max(prefix.rfind(mark) for mark in [".", "?", "!"])
    if sentence_end >= max_length // 2:
        return prefix[: sentence_end + 1].strip()
    return prefix[:max_length].rstrip() + "..."


def structure_case(row: Mapping[str, str]) -> dict:
    text = combined_case_text(row)
    guarantee_status, guarantee_basis = map_guarantee_status(
        row.get("guarantee_raw", "미상"), text
    )
    if guarantee_status not in GUARANTEE_STATUSES:
        raise ValueError(f"지원하지 않는 반환보증 상태: {guarantee_status}")

    return {
        "case_id": row["case_id"],
        "facts": {
            "region_sido": row["region_sido"],
            "region_sigungu": row["region_sigungu"],
            "housing_type": row["housing_type"],
            "deposit_range": row["deposit_range"],
            "contract_status": row["contract_status"],
            "senior_rights": row["senior_rights"],
            "guarantee_status": guarantee_status,
            "guarantee_status_basis": guarantee_basis,
            "guarantee_product_type": row["guarantee_product_type"],
        },
        "confirmed_risk_tags": extract_confirmed_risk_tags(row),
        "required_check_tags": extract_required_check_tags(row, guarantee_status),
        "dispute_type": row["dispute_type"],
        "progress_stage": row["progress_stage"],
        "source_summary": make_source_summary(row["situation_summary_safe"]),
        "search_text": row["search_text"],
        "source": {
            "type": row["source_type"],
            "group": row["source_group"],
            "is_synthetic": True,
        },
    }


def structure_cases(input_path: Path, output_path: Path, report_path: Path) -> dict:
    dataframe = pd.read_csv(input_path, encoding="utf-8-sig", keep_default_na=False)
    missing_columns = sorted(REQUIRED_COLUMNS - set(dataframe.columns))
    if missing_columns:
        raise ValueError(f"필수 열이 없습니다: {', '.join(missing_columns)}")

    records = [structure_case(row) for row in dataframe.to_dict(orient="records")]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    guarantee_counts = Counter(
        record["facts"]["guarantee_status"] for record in records
    )
    product_counts = Counter(
        record["facts"]["guarantee_product_type"] for record in records
    )
    risk_tag_counts = Counter(
        tag for record in records for tag in record["confirmed_risk_tags"]
    )
    check_tag_counts = Counter(
        tag for record in records for tag in record["required_check_tags"]
    )
    case_ids = [record["case_id"] for record in records]
    report = {
        "input_file": input_path.name,
        "output_file": output_path.name,
        "case_count": len(records),
        "duplicate_case_ids": len(case_ids) - len(set(case_ids)),
        "empty_search_texts": sum(not record["search_text"] for record in records),
        "guarantee_status_counts": dict(sorted(guarantee_counts.items())),
        "guarantee_product_type_counts": dict(sorted(product_counts.items())),
        "cases_with_confirmed_risks": sum(
            bool(record["confirmed_risk_tags"]) for record in records
        ),
        "cases_with_required_checks": sum(
            bool(record["required_check_tags"]) for record in records
        ),
        "confirmed_risk_tag_counts": dict(risk_tag_counts),
        "required_check_tag_counts": dict(check_tag_counts),
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="상담사례 구조화")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = structure_cases(args.input, args.output, args.report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
