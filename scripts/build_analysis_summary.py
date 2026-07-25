"""Build compact HUG reference statistics from the supplied accident CSV.

Usage:
    python scripts/build_analysis_summary.py --data-dir <raw-data-directory>
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

HOUSING_MAP = {
    "아파트": "apartment",
    "오피스텔": "officetel",
    "기타(오피스텔)": "officetel",
    "오피스텔(주거용)": "officetel",
    "다가구": "multi_household",
    "다가구주택": "multi_household",
    "다세대": "multi_unit",
    "다세대주택": "multi_unit",
    "빌라": "multi_unit",
    "연립": "row_house",
    "연립주택": "row_house",
    "단독": "detached",
    "단독주택": "detached",
}


def find_ratio_file(data_dir: Path) -> Path:
    candidates = [
        path
        for path in data_dir.glob("*.csv")
        if "주택가액 대비" in path.name and ("보증금" in path.name or "임재보증금" in path.name)
    ]
    if len(candidates) != 1:
        raise FileNotFoundError(f"주택가액 대비 보증금 CSV를 하나만 찾을 수 있어야 합니다: {candidates}")
    return candidates[0]


def load_rows(path: Path):
    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            with path.open("r", encoding=encoding, newline="") as stream:
                return list(csv.DictReader(stream)), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"지원하는 인코딩으로 읽을 수 없습니다: {path}")


def build_summary(path: Path) -> dict:
    rows, encoding = load_rows(path)
    if not rows:
        raise ValueError("분석할 행이 없습니다.")
    columns = list(rows[0])
    housing_column = next((c for c in columns if "주택유형" in c or "주택형태" in c), None)
    ratio_column = next((c for c in columns if "주택가액 대비" in c and "비율" in c), None)
    if not housing_column or not ratio_column:
        raise KeyError(f"필수 컬럼을 찾지 못했습니다: {columns}")

    grouped: dict[str, list[float]] = defaultdict(list)
    invalid_ratio_rows = 0
    for row in rows:
        housing_type = HOUSING_MAP.get((row.get(housing_column) or "").strip(), "other_unknown")
        try:
            ratio = float((row.get(ratio_column) or "").replace(",", ""))
        except ValueError:
            invalid_ratio_rows += 1
            continue
        if ratio < 0 or ratio > 300:
            invalid_ratio_rows += 1
            continue
        grouped[housing_type].append(ratio)

    housing_stats = {}
    for housing_type, values in sorted(grouped.items()):
        housing_stats[housing_type] = {
            "count": len(values),
            "mean_ratio": round(statistics.fmean(values), 2),
            "median_ratio": round(statistics.median(values), 2),
            "over_90_rate": round(sum(v >= 90 for v in values) / len(values), 4),
            "over_100_rate": round(sum(v >= 100 for v in values) / len(values), 4),
        }

    return {
        "source_file": path.name,
        "source_encoding": encoding,
        "source_is_synthetic_accident_data": True,
        "row_count": len(rows),
        "valid_ratio_count": sum(len(v) for v in grouped.values()),
        "invalid_ratio_count": invalid_ratio_rows,
        "housing_stats": housing_stats,
        "interpretation_notice": (
            "정상계약 전체 분모가 없는 합성 사고자료의 분포입니다. "
            "개별 계약의 사고확률로 해석하지 않습니다."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backend/data/analysis_summary.json"),
    )
    args = parser.parse_args()
    summary = build_summary(find_ratio_file(args.data_dir))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {args.output}")
    print(f"rows: {summary['row_count']:,}")
    print(f"housing types: {len(summary['housing_stats'])}")


if __name__ == "__main__":
    main()
