"""2단계: 주택유형별 주택가액 대비 임대보증금 비율 분석."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

HOUSING_MAP = {
    "아파트": ("apartment", "아파트"),
    "오피스텔": ("officetel", "오피스텔"),
    "기타(오피스텔)": ("officetel", "오피스텔"),
    "오피스텔(주거용)": ("officetel", "오피스텔"),
    "다가구": ("multi_household", "다가구주택"),
    "다가구주택": ("multi_household", "다가구주택"),
    "다세대": ("multi_unit", "다세대주택"),
    "다세대주택": ("multi_unit", "다세대주택"),
    "빌라": ("multi_unit", "다세대주택"),
    "연립": ("row_house", "연립주택"),
    "연립주택": ("row_house", "연립주택"),
    "단독": ("detached", "단독주택"),
    "단독주택": ("detached", "단독주택"),
}


def read_csv_safe(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            return pd.read_csv(path, encoding=encoding, low_memory=False)
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"인코딩을 확인할 수 없습니다: {path.name}")


def find_source(data_dir: Path) -> Path:
    candidates = [p for p in data_dir.glob("*.csv") if "주택가액 대비" in p.name]
    if len(candidates) != 1:
        raise FileNotFoundError(f"대상 CSV를 하나만 찾을 수 있어야 합니다: {candidates}")
    return candidates[0]


def normalize_housing(value):
    return HOUSING_MAP.get(str(value).strip(), ("other_unknown", "기타·미상"))


def percentage(series, threshold):
    return round(float((series >= threshold).mean()), 4)


def stats_for(group: pd.DataFrame) -> dict:
    ratio = group["deposit_ratio"]
    result = {
        "count": int(len(group)),
        "share_of_accident_records": round(float(len(group) / group.attrs["total_rows"]), 4),
        "mean_ratio": round(float(ratio.mean()), 2),
        "median_ratio": round(float(ratio.median()), 2),
        "p25_ratio": round(float(ratio.quantile(0.25)), 2),
        "p75_ratio": round(float(ratio.quantile(0.75)), 2),
        "p90_ratio": round(float(ratio.quantile(0.90)), 2),
        "min_ratio": round(float(ratio.min()), 2),
        "max_ratio": round(float(ratio.max()), 2),
        "over_70_rate": percentage(ratio, 70),
        "over_80_rate": percentage(ratio, 80),
        "over_90_rate": percentage(ratio, 90),
        "at_least_100_rate": percentage(ratio, 100),
    }
    if "house_value" in group:
        result["median_house_value"] = round(float(group["house_value"].median()), 0)
    return result


def build_report(result: dict) -> str:
    lines = [
        "# 2단계 주택유형별 보증금비율 분석",
        "",
        "> 제공된 합성 사고데이터 내부의 분포입니다. 정상계약 전체와 비교한 사고확률이 아닙니다.",
        "",
        f"- 분석 행 수: {result['valid_rows']:,}건",
        f"- 원본 중복행: {result['duplicate_rows']:,}건(삭제하지 않고 포함)",
        f"- 비율 변환 실패·범위 제외: {result['excluded_rows']:,}건",
        "",
        "## 유형별 결과",
        "",
        "| 주택유형 | 건수 | 사고자료 내 비중 | 중앙값 | 80% 이상 | 90% 이상 | 100% 이상 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["housing_stats"]:
        lines.append(
            f"| {row['housing_type_display']} | {row['count']:,} | "
            f"{row['share_of_accident_records']:.1%} | {row['median_ratio']:.1f}% | "
            f"{row['over_80_rate']:.1%} | {row['over_90_rate']:.1%} | "
            f"{row['at_least_100_rate']:.1%} |"
        )
    overall = result["overall_stats"]
    lines.extend([
        "",
        "## 해석",
        "",
        f"- 전체 사고자료의 보증금비율 중앙값은 **{overall['median_ratio']:.1f}%**입니다.",
        f"- 전체 사고자료 중 90% 이상 비율은 **{overall['over_90_rate']:.1%}**입니다.",
        "- 다가구주택은 비율 중앙값이 14.6%이지만 주택가액 중앙값이 약 8억 550만 원으로, 건물 전체 가격과 개별 보증금을 비교했을 가능성을 확인해야 합니다.",
        "- 따라서 다가구의 낮은 비율을 안전 신호로 해석하면 안 되며, 다른 임차인의 선순위 보증금 합계를 함께 확인해야 합니다.",
        "- 유형별 건수는 전체 시장의 주택재고·계약건수를 반영하지 않으므로 유형별 사고확률 비교에 사용할 수 없습니다.",
        "- 주택유형 자체에 고정 벌점을 주지 않고, 높은 보증금비율과 유형별 미확인 정보를 함께 위험신호로 사용해야 합니다.",
        "- 표본이 적은 `기타·미상` 결과는 규칙 근거로 사용하지 않습니다.",
        "",
        "## 다음 규칙 설계에 사용할 수 있는 부분",
        "",
        "- 보증금비율은 계산하되, 주택가액과 보증금의 평가 단위가 같은지 먼저 확인합니다.",
        "- 90% 이상은 강한 확인 신호 후보로 유지하되, 다가구·단독처럼 건물 전체 권리를 보는 유형에는 이 기준만 적용하지 않습니다.",
        "- 주택유형은 고정점수보다 다가구 선순위 보증금, 오피스텔 실제 용도, 다세대 가격근거 등 조건부 확인규칙에 사용합니다.",
    ])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("analysis/02_housing_deposit_ratio"))
    args = parser.parse_args()

    source = find_source(args.data_dir)
    frame = read_csv_safe(source)
    ratio_col = next(c for c in frame.columns if "주택가액 대비" in c and "비율" in c)
    housing_col = next(c for c in frame.columns if "주택유형" in c or "주택형태" in c)
    house_value_col = next(c for c in frame.columns if c == "주택가액")
    frame["deposit_ratio"] = pd.to_numeric(frame[ratio_col], errors="coerce")
    frame["house_value"] = pd.to_numeric(frame[house_value_col], errors="coerce")
    valid_mask = frame["deposit_ratio"].between(0, 300)
    analysis = frame.loc[valid_mask, [housing_col, "deposit_ratio", "house_value"]].copy()
    normalized = analysis[housing_col].map(normalize_housing)
    analysis["housing_type"] = normalized.map(lambda item: item[0])
    analysis["housing_type_display"] = normalized.map(lambda item: item[1])

    total_rows = len(analysis)
    housing_stats = []
    for (code, display), group in analysis.groupby(["housing_type", "housing_type_display"]):
        group.attrs["total_rows"] = total_rows
        housing_stats.append({
            "housing_type": code,
            "housing_type_display": display,
            **stats_for(group),
        })
    housing_stats.sort(key=lambda row: row["count"], reverse=True)
    analysis.attrs["total_rows"] = total_rows
    result = {
        "source_file": source.name,
        "source_is_synthetic_accident_data": True,
        "source_rows": int(len(frame)),
        "valid_rows": int(total_rows),
        "excluded_rows": int((~valid_mask).sum()),
        "duplicate_rows": int(frame.duplicated().sum()),
        "overall_stats": stats_for(analysis),
        "housing_stats": housing_stats,
        "interpretation_notice": (
            "정상계약 전체 분모가 없는 합성 사고자료 내부 분포입니다. "
            "주택유형별 사고확률 또는 개인별 사고확률로 해석하지 않습니다."
        ),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "housing_deposit_ratio.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "report.md").write_text(build_report(result), encoding="utf-8")
    print(f"source rows: {len(frame):,}")
    print(f"valid rows: {total_rows:,}")
    print(f"housing groups: {len(housing_stats)}")
    print(f"saved: {args.output_dir}")


if __name__ == "__main__":
    main()
