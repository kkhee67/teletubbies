from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from guarantee_products import (
    JEONSE_RETURN,
    PRODUCT_LABELS,
    UNKNOWN_PRODUCT,
    canonical_product_type,
    infer_case_product_type,
)
from similar_cases import canonical_housing


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "product_context.json"

SOURCE_LABELS = {
    "consultation_cases": "비식별 임대차 상담사례",
    "rental_guarantee_accidents": "임대보증 사고현황",
    "debtor_auction_status": "전세·임대 채무자 경매현황",
    "auction_distributions": "전세·임대 채무자 배당내역",
    "guarantee_subrogation": "전세·임대 대위변제·회수현황",
    "jeonse_accident_status": "전세보증 사고현황",
    "jeonse_housing_value_ratio": "전세사고 주택유형·보증금비율",
}


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(RAW_DIR / name, encoding="utf-8-sig", low_memory=False)


def to_number(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )


def numeric_stats(frame: pd.DataFrame, metric_columns: dict[str, str]) -> dict:
    result = {}
    for metric_name, column in metric_columns.items():
        values = to_number(frame[column]).dropna()
        if values.empty:
            continue
        result[metric_name] = {
            "count": int(values.count()),
            "median": round(float(values.median()), 2),
            "p25": round(float(values.quantile(0.25)), 2),
            "p75": round(float(values.quantile(0.75)), 2),
        }
    return result


def value_counts(series: pd.Series, limit: int | None = None) -> dict[str, int]:
    values = series.fillna("미상").astype(str).str.strip().replace("", "미상")
    counts = values.value_counts()
    if limit is not None:
        counts = counts.head(limit)
    return {str(key): int(value) for key, value in counts.items()}


def date_metadata(frame: pd.DataFrame, column: str | None) -> dict[str, Any]:
    if not column or column not in frame.columns:
        return {
            "reference_period": {"from": None, "to": None},
            "reference_date": None,
            "future_date_count": 0,
            "data_quality_notes": [],
        }
    values = pd.to_datetime(frame[column], errors="coerce").dropna()
    if values.empty:
        return {
            "reference_period": {"from": None, "to": None},
            "reference_date": None,
            "future_date_count": 0,
            "data_quality_notes": [],
        }
    today = pd.Timestamp(date.today())
    usable_values = values[values <= today]
    future_date_count = int((values > today).sum())
    notes = []
    if future_date_count:
        notes.append(
            "합성데이터에 현재 기준일보다 뒤인 날짜가 있어 최신 기준일 계산에서 제외했습니다."
        )
    return {
        "reference_period": {
            "from": values.min().date().isoformat(),
            "to": values.max().date().isoformat(),
        },
        "reference_date": (
            usable_values.max().date().isoformat()
            if not usable_values.empty
            else None
        ),
        "future_date_count": future_date_count,
        "data_quality_notes": notes,
    }


def region_sido(value: Any) -> str:
    text = "" if pd.isna(value) else str(value).strip()
    return text.split()[0] if text else "미상"


def summarize_source(
    frame: pd.DataFrame,
    source_id: str,
    product_scope: str,
    metric_columns: dict[str, str],
    housing_column: str | None = None,
    region_column: str | None = None,
    category_columns: dict[str, str] | None = None,
    date_column: str | None = None,
) -> dict:
    working = frame.copy()
    if housing_column:
        working["_housing_type"] = working[housing_column].map(
            lambda value: canonical_housing(value) or "미상"
        )
    if region_column:
        working["_region_sido"] = working[region_column].map(region_sido)

    housing_details = {}
    if housing_column:
        for housing_type, group in working.groupby("_housing_type", dropna=False):
            housing_details[str(housing_type)] = {
                "record_count": int(len(group)),
                "metrics": numeric_stats(group, metric_columns),
            }

    categories = {}
    for category_name, column in (category_columns or {}).items():
        categories[category_name] = value_counts(working[column], limit=20)

    date_info = date_metadata(working, date_column)
    return {
        "source_id": source_id,
        "source_label": SOURCE_LABELS[source_id],
        "product_scope": product_scope,
        "record_count": int(len(working)),
        "housing_type_counts": (
            value_counts(working["_housing_type"]) if housing_column else {}
        ),
        "housing_type_details": housing_details,
        "region_sido_counts": (
            value_counts(working["_region_sido"], limit=20) if region_column else {}
        ),
        "categories": categories,
        "metrics": numeric_stats(working, metric_columns),
        **date_info,
    }


def append_product_sources(
    products: dict[str, dict],
    frame: pd.DataFrame,
    source_id: str,
    product_column: str,
    metric_columns: dict[str, str],
    housing_column: str | None = None,
    region_column: str | None = None,
    category_columns: dict[str, str] | None = None,
    date_column: str | None = None,
) -> None:
    working = frame.copy()
    working["_product_type"] = working[product_column].map(canonical_product_type)
    for product_type, group in working.groupby("_product_type"):
        if product_type == UNKNOWN_PRODUCT:
            continue
        products.setdefault(
            product_type,
            {"label": PRODUCT_LABELS[product_type], "sources": []},
        )["sources"].append(
            summarize_source(
                group,
                source_id,
                product_type,
                metric_columns,
                housing_column,
                region_column,
                category_columns,
                date_column,
            )
        )


def build_product_context(output_path: Path = DEFAULT_OUTPUT) -> dict:
    consultations = pd.read_excel(RAW_DIR / "consultations.xlsx").fillna("")
    consultation_text = (
        consultations["상황요약"].astype(str)
        + " "
        + consultations["특이사항"].astype(str)
        + " "
        + consultations["보증보험"].astype(str)
    )
    inferred_products = consultation_text.map(infer_case_product_type)

    data_sources = [
        {
            "source_id": "consultation_cases",
            "source_label": SOURCE_LABELS["consultation_cases"],
            "record_count": int(len(consultations)),
            "role": "similar_case_search",
            "product_mapping_basis": "explicit_case_text_only",
            "known_product_counts": value_counts(inferred_products),
        }
    ]
    products: dict[str, dict] = {}
    shared_sources = []

    rental_accidents = read_csv("rental_guarantee_accidents.csv")
    append_product_sources(
        products,
        rental_accidents,
        "rental_guarantee_accidents",
        "상품명",
        {"subrogation_amount": "대위변제금액(보증이행)"},
        housing_column="주택형태",
        category_columns={"business_type": "개인사업자/법인사업자"},
        date_column="최초 발급일자",
    )
    data_sources.append(
        {
            "source_id": "rental_guarantee_accidents",
            "source_label": SOURCE_LABELS["rental_guarantee_accidents"],
            "record_count": int(len(rental_accidents)),
            "role": "product_statistics",
            "product_mapping_basis": "상품명",
        }
    )

    auction_status = read_csv("debtor_auction_status.csv")
    shared_sources.append(
        summarize_source(
            auction_status,
            "debtor_auction_status",
            "combined",
            {
                "deposit_amount": "임대보증금 금액",
                "accident_to_deposit_ratio_pct": "임대보증금 금액 대비 사고금액 (%)",
                "days_from_guarantee_end_to_accident": "보증종료일자 기준 사고발생일자 소요일",
            },
            housing_column="주택형태",
            region_column="사업장지역상세",
            category_columns={
                "debtor_business_type": "채무자 법인/개인사업자 구분",
                "accident_reason": "사고사유",
            },
            date_column="보증종료일자",
        )
    )
    data_sources.append(
        {
            "source_id": "debtor_auction_status",
            "source_label": SOURCE_LABELS["debtor_auction_status"],
            "record_count": int(len(auction_status)),
            "role": "shared_statistics",
            "product_mapping_basis": "mixed_file_without_product_column",
        }
    )

    distributions = read_csv("auction_distributions.csv")
    distributions["_distribution_ratio_pct"] = (
        to_number(distributions["배당금액"])
        / to_number(distributions["대위변제금액"]).replace(0, pd.NA)
        * 100
    )
    append_product_sources(
        products,
        distributions,
        "auction_distributions",
        "상품명",
        {
            "distribution_amount": "배당금액",
            "subrogation_amount": "대위변제금액",
            "distribution_to_subrogation_ratio_pct": "_distribution_ratio_pct",
        },
        housing_column="물건종류",
        region_column="물건 소재지",
        category_columns={"auction_type": "경공매구분"},
        date_column="경매신청일자",
    )
    data_sources.append(
        {
            "source_id": "auction_distributions",
            "source_label": SOURCE_LABELS["auction_distributions"],
            "record_count": int(len(distributions)),
            "role": "product_statistics",
            "product_mapping_basis": "상품명",
        }
    )

    subrogation = read_csv("guarantee_subrogation.csv")
    append_product_sources(
        products,
        subrogation,
        "guarantee_subrogation",
        "상품명",
        {
            "claim_amount": "신청청구금액",
            "occurrence_amount": "발생금액",
            "total_recovery_ratio_pct": "발생금액대비 총회수금액(%)",
            "days_from_application_to_distribution": "신청일자대비 배당 소요일",
        },
        category_columns={"claim_type": "채권구분"},
        date_column="발생일자",
    )
    data_sources.append(
        {
            "source_id": "guarantee_subrogation",
            "source_label": SOURCE_LABELS["guarantee_subrogation"],
            "record_count": int(len(subrogation)),
            "role": "product_statistics",
            "product_mapping_basis": "상품명",
        }
    )

    accident_status = read_csv("jeonse_accident_status.csv")
    append_product_sources(
        products,
        accident_status,
        "jeonse_accident_status",
        "상품명",
        {"subrogation_amount": "대위변제금액"},
        region_column="시도구",
        category_columns={"guarantee_status": "보증상태"},
        date_column="사고접수일자",
    )
    data_sources.append(
        {
            "source_id": "jeonse_accident_status",
            "source_label": SOURCE_LABELS["jeonse_accident_status"],
            "record_count": int(len(accident_status)),
            "role": "product_statistics",
            "product_mapping_basis": "상품명",
        }
    )

    value_ratio = read_csv("jeonse_housing_value_ratio.csv")
    products.setdefault(
        JEONSE_RETURN,
        {"label": PRODUCT_LABELS[JEONSE_RETURN], "sources": []},
    )["sources"].append(
        summarize_source(
            value_ratio,
            "jeonse_housing_value_ratio",
            JEONSE_RETURN,
            {
                "deposit_amount": "임대보증금액",
                "accident_amount_ratio_pct": "임대보증금액 대비 사고금액 비율(%)",
            },
            housing_column="주택유형",
            region_column="시도명",
            date_column="보증종료일자",
        )
    )
    data_sources.append(
        {
            "source_id": "jeonse_housing_value_ratio",
            "source_label": SOURCE_LABELS["jeonse_housing_value_ratio"],
            "record_count": int(len(value_ratio)),
            "role": "product_statistics",
            "product_mapping_basis": "file_scope:전세사고",
        }
    )

    context = {
        "schema_version": 1,
        "is_synthetic": True,
        "data_source_count": len(data_sources),
        "data_sources": data_sources,
        "products": products,
        "shared_sources": shared_sources,
        "notice": (
            "발제사 제공 합성데이터를 상품별·주택유형별로 집계한 참고정보이며 "
            "위험도나 사고확률을 의미하지 않습니다."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return context


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="보증상품별 합성데이터 컨텍스트 생성")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    context = build_product_context(args.output)
    summary = {
        "data_source_count": context["data_source_count"],
        "products": {
            key: {
                "label": value["label"],
                "source_count": len(value["sources"]),
                "record_count_by_source": {
                    source["source_id"]: source["record_count"]
                    for source in value["sources"]
                },
            }
            for key, value in context["products"].items()
        },
        "shared_source_count": len(context["shared_sources"]),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
