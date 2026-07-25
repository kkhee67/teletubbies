"""3단계: 경매·배당·대위변제 데이터의 회수 특성을 분석한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

HOUSING_MAP = {
    "아파트": ("apartment", "아파트"),
    "아파트(임대)": ("apartment", "아파트"),
    "오피스텔": ("officetel", "오피스텔"),
    "기타(오피스텔)": ("officetel", "오피스텔"),
    "오피스텔(주거용)": ("officetel", "오피스텔"),
    "주거용오피스텔": ("officetel", "오피스텔"),
    "다가구주택": ("multi_household", "다가구주택"),
    "다세대주택": ("multi_unit", "다세대주택"),
    "연립주택": ("row_house", "연립주택"),
    "단독주택": ("detached", "단독주택"),
}


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def find_one(data_dir: Path, text: str, *, startswith: str | None = None) -> Path:
    candidates = [
        path for path in data_dir.glob("*.csv")
        if text in path.name and (startswith is None or path.name.startswith(startswith))
    ]
    if len(candidates) != 1:
        raise FileNotFoundError(f"'{text}' 파일을 하나만 찾을 수 있어야 합니다: {candidates}")
    return candidates[0]


def normalize_housing(value):
    return HOUSING_MAP.get(str(value).strip(), ("other", "기타"))


def money(value):
    return int(round(float(value)))


def auction_stats(frame: pd.DataFrame) -> dict:
    normalized = frame["물건종류"].map(normalize_housing)
    work = frame.assign(
        housing_type=normalized.map(lambda item: item[0]),
        housing_type_display=normalized.map(lambda item: item[1]),
        dividend=pd.to_numeric(frame["배당금액"], errors="coerce"),
        subrogation=pd.to_numeric(frame["대위변제금액"], errors="coerce"),
    )
    rows = []
    for (code, display), group in work.groupby(["housing_type", "housing_type_display"]):
        rows.append({
            "housing_type": code,
            "housing_type_display": display,
            "count": int(len(group)),
            "share": round(float(len(group) / len(work)), 4),
            "zero_dividend_count": int((group["dividend"] == 0).sum()),
            "zero_dividend_rate": round(float((group["dividend"] == 0).mean()), 4),
            "median_dividend": money(group["dividend"].median()),
            "p90_dividend": money(group["dividend"].quantile(0.9)),
            "median_subrogation": money(group["subrogation"].median()),
        })
    rows.sort(key=lambda row: row["count"], reverse=True)
    return {
        "rows": int(len(frame)),
        "duplicate_rows": int(frame.duplicated().sum()),
        "missing_location": int(frame["물건 소재지"].isna().sum()),
        "zero_dividend_count": int((work["dividend"] == 0).sum()),
        "zero_dividend_rate": round(float((work["dividend"] == 0).mean()), 4),
        "median_dividend": money(work["dividend"].median()),
        "median_subrogation": money(work["subrogation"].median()),
        "by_housing_type": rows,
        "ratio_warning": (
            "배당금액/대위변제금액 비율은 100% 초과가 2,884건이고 최댓값이 매우 커서 "
            "개별 회수율로 사용하지 않습니다. 두 금액의 집계 단위가 같은지 확인이 필요합니다."
        ),
    }


def distribution_stats(frame: pd.DataFrame) -> dict:
    work = frame.assign(
        recovery_rate=pd.to_numeric(frame["발생금액대비 총회수금액(%)"], errors="coerce"),
        days=pd.to_numeric(frame["신청일자대비 배당 소요일"], errors="coerce"),
    )
    rows = []
    for claim_type, group in work.groupby("채권구분"):
        valid_days = group.loc[group["days"] >= 0, "days"]
        rows.append({
            "claim_type": claim_type,
            "count": int(len(group)),
            "median_recovery_rate": round(float(group["recovery_rate"].median()), 2),
            "mean_recovery_rate": round(float(group["recovery_rate"].mean()), 2),
            "zero_recovery_rate": round(float((group["recovery_rate"] == 0).mean()), 4),
            "full_recovery_rate": round(float((group["recovery_rate"] >= 100).mean()), 4),
            "median_distribution_days_nonnegative": round(float(valid_days.median()), 1),
            "negative_days_count": int((group["days"] < 0).sum()),
        })
    rows.sort(key=lambda row: row["count"], reverse=True)
    valid_days = work.loc[work["days"] >= 0, "days"]
    return {
        "rows": int(len(work)),
        "duplicate_rows": int(frame.duplicated().sum()),
        "median_recovery_rate": round(float(work["recovery_rate"].median()), 2),
        "zero_recovery_count": int((work["recovery_rate"] == 0).sum()),
        "zero_recovery_rate": round(float((work["recovery_rate"] == 0).mean()), 4),
        "full_recovery_rate": round(float((work["recovery_rate"] >= 100).mean()), 4),
        "median_distribution_days_nonnegative": round(float(valid_days.median()), 1),
        "p90_distribution_days_nonnegative": round(float(valid_days.quantile(0.9)), 1),
        "negative_days_count": int((work["days"] < 0).sum()),
        "by_claim_type": rows,
    }


def jeonse_subrogation_stats(frame: pd.DataFrame) -> dict:
    amount = pd.to_numeric(frame["대위변제금액"], errors="coerce")
    return {
        "rows": int(len(frame)),
        "duplicate_rows": int(frame.duplicated().sum()),
        "missing_region": int(frame["시도구"].isna().sum()),
        "total_amount": money(amount.sum()),
        "median_amount": money(amount.median()),
        "p90_amount": money(amount.quantile(0.9)),
        "status_counts": {str(k): int(v) for k, v in frame["보증상태"].value_counts().items()},
    }


def rental_subrogation_stats(frame: pd.DataFrame) -> dict:
    amount_col = "대위변제금액(보증이행)"
    unnamed = [column for column in frame.columns if str(column).startswith("Unnamed")]
    unexpected_values = {}
    for column in unnamed:
        non_null = frame[column].dropna()
        unexpected_values[column] = {
            "non_null_count": int(non_null.size),
            "unique_count": int(non_null.nunique()),
            "values_redacted": True,
        }

    def summarize(work: pd.DataFrame):
        amount = pd.to_numeric(work[amount_col], errors="coerce")
        normalized = work["주택형태"].map(normalize_housing)
        temp = work.assign(
            amount=amount,
            housing_type=normalized.map(lambda item: item[0]),
            housing_type_display=normalized.map(lambda item: item[1]),
        )
        groups = []
        for (code, display), group in temp.groupby(["housing_type", "housing_type_display"]):
            groups.append({
                "housing_type": code,
                "housing_type_display": display,
                "count": int(len(group)),
                "total_amount": money(group["amount"].sum()),
                "median_amount": money(group["amount"].median()),
            })
        groups.sort(key=lambda row: row["count"], reverse=True)
        return {
            "rows": int(len(work)),
            "total_amount": money(amount.sum()),
            "median_amount": money(amount.median()),
            "by_housing_type": groups,
        }

    deduplicated = frame.drop_duplicates()
    raw = summarize(frame)
    dedup = summarize(deduplicated)
    return {
        "duplicate_rows": int(frame.duplicated().sum()),
        "unnamed_values": unexpected_values,
        "raw": raw,
        "deduplicated_sensitivity": dedup,
        "total_amount_difference_rate": round(
            float((raw["total_amount"] - dedup["total_amount"]) / raw["total_amount"]), 4
        ),
        "deduplication_notice": (
            "식별키가 없어 동일 행이 실제 중복인지 별도 계약인지 확정할 수 없습니다. "
            "기본 결과는 원본 기준이며 중복 제거 결과는 민감도 확인용입니다."
        ),
    }


def won(value):
    return f"{value / 100_000_000:,.1f}억 원"


def build_report(result: dict) -> str:
    auction = result["auction"]
    distribution = result["distribution"]
    rental = result["rental_subrogation"]
    lines = [
        "# 3단계 경매·배당·대위변제 분석",
        "",
        "> 합성 사고자료의 사고 이후 결과입니다. 계약 전 개인별 회수금액 예측에 직접 사용하지 않습니다.",
        "",
        "## 경매현황",
        "",
        f"- 전체 {auction['rows']:,}건 중 배당금 0원은 **{auction['zero_dividend_count']:,}건({auction['zero_dividend_rate']:.1%})**입니다.",
        f"- 배당금 중앙값은 {won(auction['median_dividend'])}, 대위변제금액 중앙값은 {won(auction['median_subrogation'])}입니다.",
        "",
        "| 주택유형 | 건수 | 배당 0원 비율 | 배당금 중앙값 | 대위변제 중앙값 |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in auction["by_housing_type"]:
        lines.append(
            f"| {row['housing_type_display']} | {row['count']:,} | {row['zero_dividend_rate']:.1%} | "
            f"{won(row['median_dividend'])} | {won(row['median_subrogation'])} |"
        )
    lines.extend([
        "",
        f"- 주의: {auction['ratio_warning']}",
        "",
        "## 배당내역",
        "",
        f"- 전체 회수율 중앙값은 **{distribution['median_recovery_rate']:.1f}%**입니다.",
        f"- 회수율 0%는 {distribution['zero_recovery_count']:,}건({distribution['zero_recovery_rate']:.2%})입니다.",
        f"- 음수 소요일 {distribution['negative_days_count']:,}건을 제외한 배당 소요일 중앙값은 **{distribution['median_distribution_days_nonnegative']:.0f}일**, 상위 10% 경계는 {distribution['p90_distribution_days_nonnegative']:.0f}일입니다.",
        "",
        "| 채권구분 | 건수 | 회수율 중앙값 | 100% 회수 비율 | 배당 소요일 중앙값 |",
        "|---|---:|---:|---:|---:|",
    ])
    for row in distribution["by_claim_type"]:
        lines.append(
            f"| {row['claim_type']} | {row['count']:,} | {row['median_recovery_rate']:.1f}% | "
            f"{row['full_recovery_rate']:.1%} | {row['median_distribution_days_nonnegative']:.0f}일 |"
        )
    unexpected_count = sum(
        values["non_null_count"] for values in rental["unnamed_values"].values()
    )
    lines.extend([
        "",
        "- 전체 회수율 중앙값 100%는 소송대지급금 17,609건의 영향을 크게 받습니다. 경매현황의 배당금 0원 비율과 같은 지표로 비교하면 안 됩니다.",
        "- 경매현황과 배당내역을 연결할 공통 식별키가 없어 사건별 결합은 하지 않았습니다.",
        "",
        "## 임대보증 대위변제 중복 민감도",
        "",
        f"- 원본 {rental['raw']['rows']:,}건, 완전 중복행 {rental['duplicate_rows']:,}건입니다.",
        f"- 원본 대위변제 합계는 {won(rental['raw']['total_amount'])}, 중복 제거 시 {won(rental['deduplicated_sensitivity']['total_amount'])}입니다.",
        f"- 합계 차이는 원본 대비 {rental['total_amount_difference_rate']:.1%}이므로 중복 처리 기준이 결과에 영향을 줍니다.",
        f"- `Unnamed: 5`에는 주소 형태의 값 {unexpected_count:,}건이 있어 단순 빈 컬럼으로 바로 삭제하지 않고 원본 구조를 확인해야 합니다.",
        f"- {rental['deduplication_notice']}",
        "",
        "## 위험규칙에 사용할 수 있는 부분",
        "",
        "- 경매·배당 데이터는 계약 전 위험점수를 직접 결정하기보다 사고 이후 회수 불확실성을 설명하는 근거로 사용합니다.",
        "- 배당금 0원 비율과 배당 소요일은 스트레스 시나리오 또는 유사사례 설명에 사용할 수 있습니다.",
        "- `배당금액 ÷ 대위변제금액`은 집계 단위 불일치 가능성이 있어 회수율로 사용하지 않습니다.",
        "- 주택유형별 건수는 정상계약 분모가 없으므로 유형별 사고확률로 표현하지 않습니다.",
    ])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("analysis/03_auction_recovery"))
    args = parser.parse_args()

    paths = {
        "auction": find_one(args.data_dir, "경매현황"),
        "distribution": find_one(args.data_dir, "배당내역"),
        "jeonse_subrogation": find_one(args.data_dir, "대위변제", startswith="전세보증"),
        "rental_subrogation": find_one(args.data_dir, "대위변제", startswith="임대보증"),
    }
    result = {
        "sources": {name: path.name for name, path in paths.items()},
        "source_is_synthetic_accident_data": True,
        "auction": auction_stats(read_csv(paths["auction"])),
        "distribution": distribution_stats(read_csv(paths["distribution"])),
        "jeonse_subrogation": jeonse_subrogation_stats(read_csv(paths["jeonse_subrogation"])),
        "rental_subrogation": rental_subrogation_stats(read_csv(paths["rental_subrogation"])),
        "interpretation_notice": (
            "사고 이후 합성자료의 결과이며 계약 전 개인별 회수금액이나 사고확률 예측값이 아닙니다."
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "auction_recovery.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "report.md").write_text(build_report(result), encoding="utf-8")
    print(f"auction rows: {result['auction']['rows']:,}")
    print(f"distribution rows: {result['distribution']['rows']:,}")
    print(f"saved: {args.output_dir}")


if __name__ == "__main__":
    main()
