from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from guarantee_products import PRODUCT_LABELS, infer_case_product_type


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "raw" / "consultations.xlsx"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "consultations_clean.csv"
DEFAULT_REPORT = PROJECT_ROOT / "data" / "processed" / "preprocessing_report.json"

REQUIRED_COLUMNS = [
    "일련번호",
    "자료군",
    "지역(시도)",
    "지역(시군구)",
    "보증금구간",
    "계약상태",
    "주택유형",
    "선순위권리",
    "보증보험",
    "분쟁유형",
    "진행단계",
    "상황요약",
    "특이사항",
]

CATEGORY_COLUMNS = [
    "자료군",
    "지역(시도)",
    "지역(시군구)",
    "보증금구간",
    "계약상태",
    "주택유형",
    "선순위권리",
    "보증보험",
    "분쟁유형",
    "진행단계",
]

COLUMN_NAMES = {
    "자료군": "source_group",
    "지역(시도)": "region_sido",
    "지역(시군구)": "region_sigungu",
    "보증금구간": "deposit_range",
    "계약상태": "contract_status",
    "주택유형": "housing_type",
    "선순위권리": "senior_rights",
    "보증보험": "guarantee_raw",
    "분쟁유형": "dispute_type",
    "진행단계": "progress_stage",
    "상황요약": "situation_summary_safe",
    "특이사항": "special_notes_safe",
}

PII_PATTERNS = {
    "resident_id": (
        re.compile(r"(?<!\d)\d{6}[- ]?[1-4]\d{6}(?!\d)"),
        "[주민번호]",
    ),
    "email": (
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        "[이메일]",
    ),
    "phone": (
        re.compile(r"(?<!\d)(?:01[016789]|0\d{1,2})[- .]?\d{3,4}[- .]?\d{4}(?!\d)"),
        "[전화번호]",
    ),
    "road_address": (
        re.compile(r"[가-힣0-9]+(?:로|길)\s*\d+(?:-\d+)?"),
        "[상세주소]",
    ),
}


def normalize_text(value: object, empty_value: str = "") -> str:
    if pd.isna(value):
        return empty_value
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or empty_value


def deidentify(text: str, hit_counts: dict[str, int]) -> str:
    safe_text = text
    for name, (pattern, replacement) in PII_PATTERNS.items():
        safe_text, count = pattern.subn(replacement, safe_text)
        hit_counts[name] += count
    return safe_text


def build_search_text(row: pd.Series) -> str:
    parts = [
        f"보증상품 {PRODUCT_LABELS[row['guarantee_product_type']]}",
        f"주택유형 {row['housing_type']}",
        f"보증금구간 {row['deposit_range']}",
        f"계약상태 {row['contract_status']}",
        f"선순위권리 {row['senior_rights']}",
        f"반환보증 {row['guarantee_raw']}",
        f"분쟁유형 {row['dispute_type']}",
        f"진행단계 {row['progress_stage']}",
    ]
    if row["situation_summary_safe"]:
        parts.append(f"상황 {row['situation_summary_safe']}")
    if row["special_notes_safe"]:
        parts.append(f"특이사항 {row['special_notes_safe']}")
    return " | ".join(parts)


def preprocess(input_path: Path, output_path: Path, report_path: Path) -> dict:
    source = pd.read_excel(input_path)
    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(source.columns))
    if missing_columns:
        raise ValueError(f"필수 열이 없습니다: {', '.join(missing_columns)}")

    cleaned = source[REQUIRED_COLUMNS].copy()
    for column in CATEGORY_COLUMNS:
        cleaned[column] = cleaned[column].map(lambda value: normalize_text(value, "미상"))

    hit_counts = {name: 0 for name in PII_PATTERNS}
    for column in ["상황요약", "특이사항"]:
        cleaned[column] = cleaned[column].map(normalize_text)
        cleaned[column] = cleaned[column].map(lambda text: deidentify(text, hit_counts))

    cleaned.insert(
        0,
        "case_id",
        cleaned["일련번호"].map(lambda value: f"CASE-{int(value):04d}"),
    )
    cleaned = cleaned.drop(columns=["일련번호"]).rename(columns=COLUMN_NAMES)
    cleaned["guarantee_product_type"] = cleaned.apply(
        lambda row: infer_case_product_type(
            " ".join(
                [
                    row["situation_summary_safe"],
                    row["special_notes_safe"],
                    row["guarantee_raw"],
                ]
            )
        ),
        axis=1,
    )
    cleaned["search_text"] = cleaned.apply(build_search_text, axis=1)
    cleaned["source_type"] = "provided_synthetic_consultations"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(output_path, index=False, encoding="utf-8-sig")

    report = {
        "input_file": input_path.name,
        "output_file": output_path.name,
        "input_rows": int(len(source)),
        "output_rows": int(len(cleaned)),
        "output_columns": list(cleaned.columns),
        "duplicate_case_ids": int(cleaned["case_id"].duplicated().sum()),
        "empty_situation_summaries": int((cleaned["situation_summary_safe"] == "").sum()),
        "unknown_counts": {
            column: int((cleaned[column] == "미상").sum())
            for column in [
                "housing_type",
                "senior_rights",
                "guarantee_raw",
                "deposit_range",
            ]
        },
        "guarantee_product_type_counts": {
            str(key): int(value)
            for key, value in cleaned["guarantee_product_type"].value_counts().items()
        },
        "deidentification_hits": hit_counts,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="상담데이터 전처리")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = preprocess(args.input, args.output, args.report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
