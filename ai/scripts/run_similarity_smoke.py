import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from similar_cases import find_similar_cases  # noqa: E402


SCENARIOS = [
    {
        "name": "다세대_근저당_말소",
        "property_data": {
            "guarantee_product_type": "jeonse_return",
            "housing_type": "다세대주택",
            "deposit": 180_000_000,
            "senior_rights": "근저당",
            "guarantee_status": "unknown",
        },
        "analysis": {
            "confirmed_risks": [
                {"code": "MORTGAGE_EXISTS", "title": "선순위 근저당 확인"}
            ]
        },
        "user_text": "잔금일에 근저당을 말소한다고 약속했습니다.",
    },
    {
        "name": "다가구_선순위미확인",
        "property_data": {
            "guarantee_product_type": "rental_deposit",
            "housing_type": "다가구주택",
            "deposit": 150_000_000,
            "senior_rights": "미상",
            "guarantee_status": "unknown",
        },
        "analysis": {
            "required_checks": [
                {
                    "code": "SENIOR_DEPOSIT_UNKNOWN",
                    "title": "선순위 임차보증금 확인 필요",
                }
            ]
        },
        "user_text": "선순위 임차인의 보증금을 확인하지 못했습니다.",
    },
    {
        "name": "오피스텔_용도보증미상",
        "property_data": {
            "guarantee_product_type": "rental_deposit",
            "housing_type": "오피스텔",
            "deposit": 90_000_000,
            "guarantee_status": "unknown",
        },
        "analysis": {
            "required_checks": [
                {"code": "USAGE_UNKNOWN", "title": "주거용도 확인 필요"}
            ]
        },
        "user_text": "주거용인지 확인하지 못했고 반환보증 상태도 모릅니다.",
    },
    {
        "name": "아파트_보증가입",
        "property_data": {
            "guarantee_product_type": "jeonse_return",
            "housing_type": "아파트",
            "deposit": 250_000_000,
            "guarantee_status": "enrolled",
        },
        "analysis": {},
        "user_text": None,
    },
    {
        "name": "사용자메모없음",
        "property_data": {
            "guarantee_product_type": "jeonse_return",
            "housing_type": "다세대주택",
            "deposit": 160_000_000,
            "senior_rights": "근저당",
            "guarantee_status": "unknown",
        },
        "analysis": {"confirmed_risks": [{"code": "MORTGAGE_EXISTS"}]},
        "user_text": None,
    },
]


def main() -> None:
    output = []
    for scenario in SCENARIOS:
        results = find_similar_cases(
            scenario["property_data"],
            scenario["analysis"],
            scenario["user_text"],
            top_k=3,
        )
        output.append(
            {
                "scenario": scenario["name"],
                "results": [
                    {
                        "case_id": result["case_id"],
                        "similarity": result["similarity"],
                        "matched_factors": result["matched_factors"],
                        "risk_tags": result["confirmed_risk_tags"],
                    }
                    for result in results
                ],
            }
        )
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
