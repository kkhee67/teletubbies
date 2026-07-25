from __future__ import annotations

import copy
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROPERTIES_PATH = PROJECT_ROOT / "data" / "mock_properties.json"
DEFAULT_LOCATION_PATH = PROJECT_ROOT / "data" / "location_context.json"


class MockPropertyRepository:
    def __init__(
        self,
        properties_path: Path = DEFAULT_PROPERTIES_PATH,
        location_path: Path = DEFAULT_LOCATION_PATH,
    ):
        properties = json.loads(Path(properties_path).read_text(encoding="utf-8"))
        self.locations = json.loads(Path(location_path).read_text(encoding="utf-8"))
        self.properties = {item["property_id"]: item for item in properties}
        if len(self.properties) != len(properties):
            raise ValueError("모의 매물 property_id가 중복되었습니다.")
        if len(self.properties) < 5:
            raise ValueError("시연용 모의 매물은 5개 이상이어야 합니다.")

    @property
    def count(self) -> int:
        return len(self.properties)

    def search(self, query: str) -> list[dict]:
        keyword = " ".join(query.lower().split())
        results = []
        for item in self.properties.values():
            searchable = " ".join(
                [
                    item["property_id"],
                    item["search_address"],
                    item["display_address"],
                ]
            ).lower()
            if keyword and keyword not in searchable:
                continue
            results.append(
                {
                    "property_id": item["property_id"],
                    "display_address": item["display_address"],
                    "is_mock": True,
                    "guarantee_product_type": item["guarantee_product_type"],
                }
            )
        return results

    def get(self, property_id: str) -> dict:
        item = self.properties.get(property_id)
        if item is None:
            raise KeyError(property_id)
        result = copy.deepcopy(item)
        result["location_context"] = copy.deepcopy(
            self.locations.get(
                property_id,
                {
                    "included_in_risk_score": False,
                    "items": [],
                    "source_type": "unknown",
                    "source_name": "연동된 입지자료 없음",
                    "reference_date": None,
                    "notice": "입지정보는 확인된 출처가 있을 때만 표시합니다.",
                },
            )
        )
        return result
