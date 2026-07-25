import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from similar_cases import (  # noqa: E402
    SimilarCaseSearchEngine,
    calculate_final_score,
    deposit_to_range,
    guarantee_group,
    text_context_tags,
)


def make_case(
    case_id,
    housing_type,
    deposit_range,
    senior_rights,
    guarantee_status,
    risk_tags,
    text,
    product_type="unknown",
):
    return {
        "case_id": case_id,
        "facts": {
            "housing_type": housing_type,
            "deposit_range": deposit_range,
            "senior_rights": senior_rights,
            "guarantee_status": guarantee_status,
            "guarantee_product_type": product_type,
        },
        "confirmed_risk_tags": risk_tags,
        "required_check_tags": [],
        "dispute_type": "보증금미반환",
        "progress_stage": "상담·검토",
        "source_summary": text,
        "search_text": text,
    }


class SimilarCasesTest(unittest.TestCase):
    def test_deposit_ranges(self):
        self.assertEqual(deposit_to_range(99_000_000), "1억 미만")
        self.assertEqual(deposit_to_range(100_000_000), "1억~2억")
        self.assertEqual(deposit_to_range(200_000_000), "2억~3억")
        self.assertEqual(deposit_to_range(300_000_000), "3억 이상")

    def test_guarantee_groups(self):
        self.assertEqual(guarantee_group("unknown"), "check_required")
        self.assertEqual(guarantee_group("미상"), "check_required")
        self.assertEqual(guarantee_group("estimated_eligible"), "check_required")
        self.assertEqual(guarantee_group("applied"), "in_progress")
        self.assertEqual(guarantee_group("enrolled"), "protected")
        self.assertEqual(guarantee_group("ineligible"), "deep_analysis")

    def test_final_score_uses_document_weights(self):
        self.assertEqual(calculate_final_score(1, 1, 1, 1, 1), 1.0)
        self.assertEqual(calculate_final_score(1, 0, 0, 0, 0), 0.45)
        self.assertEqual(calculate_final_score(1, 1, 1, 1, 1, 1), 1.0)

    def test_known_opposite_product_is_excluded(self):
        cases = [
            make_case(
                "CASE-0001",
                "다세대주택",
                "1억~2억",
                "근저당설정",
                "unknown",
                ["근저당"],
                "전세보증금반환보증 근저당 상담",
                "jeonse_return",
            ),
            make_case(
                "CASE-0002",
                "다세대주택",
                "1억~2억",
                "근저당설정",
                "unknown",
                ["근저당"],
                "임대보증금보증 근저당 상담",
                "rental_deposit",
            ),
            make_case(
                "CASE-0003",
                "다세대주택",
                "1억~2억",
                "근저당설정",
                "unknown",
                ["근저당"],
                "상품 유형 미확인 근저당 상담",
            ),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "cases.jsonl"
            path.write_text(
                "\n".join(json.dumps(case, ensure_ascii=False) for case in cases),
                encoding="utf-8",
            )
            engine = SimilarCaseSearchEngine(path)
            results = engine.search(
                {
                    "guarantee_product_type": "rental_deposit",
                    "housing_type": "다세대주택",
                    "deposit": 150_000_000,
                    "senior_rights": "근저당",
                },
                {},
                "근저당 상담",
                top_k=3,
            )

        self.assertEqual(results[0]["case_id"], "CASE-0002")
        self.assertNotIn("CASE-0001", {result["case_id"] for result in results})

    def test_user_text_context_is_normalized(self):
        self.assertEqual(
            text_context_tags("잔금일에 근저당을 말소한다고 약속했습니다."),
            {"말소 약속"},
        )

    def test_exact_context_ranks_first_without_user_text(self):
        cases = [
            make_case(
                "CASE-0001",
                "다세대주택",
                "1억~2억",
                "근저당설정",
                "unknown",
                ["근저당", "말소 약속"],
                "다세대주택 근저당 잔금일 말소 약속 반환보증 확인",
            ),
            make_case(
                "CASE-0002",
                "아파트",
                "3억 이상",
                "미상",
                "enrolled",
                [],
                "아파트 반환보증 가입 완료 일반 상담",
            ),
            make_case(
                "CASE-0003",
                "오피스텔",
                "1억 미만",
                "압류·가압류",
                "ineligible",
                ["압류·가압류"],
                "오피스텔 압류 반환보증 가입 불가",
            ),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "cases.jsonl"
            path.write_text(
                "\n".join(json.dumps(case, ensure_ascii=False) for case in cases),
                encoding="utf-8",
            )
            engine = SimilarCaseSearchEngine(path)
            results = engine.search(
                {
                    "housing_type": "빌라",
                    "deposit": 150_000_000,
                    "senior_rights": "근저당",
                    "guarantee_status": "unknown",
                },
                {},
                None,
                top_k=2,
            )

        self.assertEqual(results[0]["case_id"], "CASE-0001")
        self.assertGreaterEqual(results[0]["similarity"], results[1]["similarity"])
        self.assertEqual(results[0]["similarity_label"], "상담사례 유사도")
        self.assertIn("동일한 피해를 예측하지 않습니다", results[0]["disclaimer"])


if __name__ == "__main__":
    unittest.main()
