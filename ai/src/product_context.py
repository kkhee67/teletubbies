from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from guarantee_products import PRODUCT_LABELS, canonical_product_type
from similar_cases import canonical_housing


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTEXT_PATH = PROJECT_ROOT / "data" / "processed" / "product_context.json"


class ProductContextRepository:
    def __init__(self, context_path: Path = DEFAULT_CONTEXT_PATH):
        self.context_path = Path(context_path)
        self.context = json.loads(self.context_path.read_text(encoding="utf-8"))

    @property
    def data_source_count(self) -> int:
        return int(self.context.get("data_source_count", 0))

    @staticmethod
    def _public_source(
        source: dict,
        housing_type: str | None,
        region_sido: str | None,
    ) -> dict[str, Any]:
        canonical_type = canonical_housing(housing_type)
        housing_detail = (
            source.get("housing_type_details", {}).get(canonical_type)
            if canonical_type
            else None
        )
        metrics = (
            housing_detail.get("metrics", {})
            if housing_detail
            else source.get("metrics", {})
        )
        region_count = None
        if region_sido:
            region_count = source.get("region_sido_counts", {}).get(region_sido, 0)
        return {
            "source_id": source["source_id"],
            "source_label": source["source_label"],
            "product_scope": source["product_scope"],
            "record_count": source["record_count"],
            "matching_housing_type_count": (
                housing_detail.get("record_count") if housing_detail else None
            ),
            "matching_region_sido_count": region_count,
            "metrics": metrics,
            "reference_period": source.get(
                "reference_period", {"from": None, "to": None}
            ),
            "reference_date": source.get("reference_date"),
            "future_date_count": source.get("future_date_count", 0),
            "data_quality_notes": source.get("data_quality_notes", []),
        }

    def get_context(
        self,
        product_type: Any,
        housing_type: str | None = None,
        region_sido: str | None = None,
    ) -> dict[str, Any]:
        selected_type = canonical_product_type(product_type)
        product = self.context.get("products", {}).get(selected_type)
        specific_sources = product.get("sources", []) if product else []
        shared_sources = self.context.get("shared_sources", [])
        sources = [
            self._public_source(source, housing_type, region_sido)
            for source in [*specific_sources, *shared_sources]
        ]
        return {
            "selected_product_type": selected_type,
            "selected_product_label": PRODUCT_LABELS[selected_type],
            "product_separation_applied": bool(product),
            "source_count": len(sources),
            "sources": sources,
            "notice": self.context["notice"],
        }

    def get_data_usage(self, product_type: Any) -> dict[str, Any]:
        selected_type = canonical_product_type(product_type)
        product = self.context.get("products", {}).get(selected_type, {})
        product_source_ids = {
            source["source_id"] for source in product.get("sources", [])
        }
        shared_source_ids = {
            source["source_id"]
            for source in self.context.get("shared_sources", [])
        }
        applied_source_ids = {
            "consultation_cases",
            *product_source_ids,
            *shared_source_ids,
        }
        usage_labels = {
            "similar_case_search": "유사사례 검색과 쉬운 설명",
            "product_statistics": "선택 보증상품의 사고·회수 참고 통계",
            "shared_statistics": "상품 구분 컬럼이 없는 공통 경매 참고 통계",
        }
        sources = []
        for source in self.context.get("data_sources", []):
            source_id = source["source_id"]
            sources.append(
                {
                    "source_id": source_id,
                    "source_label": source["source_label"],
                    "record_count": source["record_count"],
                    "role": source["role"],
                    "used_for": usage_labels[source["role"]],
                    "applied_to_request": source_id in applied_source_ids,
                    "product_mapping_basis": source["product_mapping_basis"],
                }
            )
        return {
            "total_source_count": len(sources),
            "applied_source_count": sum(
                source["applied_to_request"] for source in sources
            ),
            "selected_product_type": selected_type,
            "sources": sources,
            "notice": (
                "7개 제공 원천을 모두 데이터 파이프라인에 등록했습니다. 개별 요청에는 "
                "선택 상품과 공통 자료만 적용해 전세·임대 통계가 섞이지 않게 합니다."
            ),
        }
