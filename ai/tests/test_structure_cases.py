import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from structure_cases import (  # noqa: E402
    extract_confirmed_risk_tags,
    extract_required_check_tags,
    make_source_summary,
    map_guarantee_status,
)


class StructureCasesTest(unittest.TestCase):
    def test_guarantee_mapping_uses_six_stage_rules(self):
        self.assertEqual(map_guarantee_status("가입", "")[0], "enrolled")
        self.assertEqual(
            map_guarantee_status("미가입", "반환보증 가입 불가 안내")[0],
            "ineligible",
        )
        self.assertEqual(
            map_guarantee_status("미상", "가입 신청 후 보증 심사 중")[0],
            "applied",
        )
        self.assertEqual(
            map_guarantee_status("미상", "공식 사전 확인 결과 가입 가능")[0],
            "officially_eligible",
        )
        self.assertEqual(
            map_guarantee_status("미상", "내부 조건상 가입 가능성이 있음")[0],
            "estimated_eligible",
        )
        self.assertEqual(map_guarantee_status("미가입", "")[0], "unknown")

    def test_risk_tags_only_use_explicit_context(self):
        row = {
            "senior_rights": "근저당설정",
            "dispute_type": "경매·공매",
            "progress_stage": "임차권등기",
            "situation_summary_safe": "공동담보로 설정되었고 잔금일 말소하기로 약속함",
            "special_notes_safe": "",
        }

        self.assertEqual(
            extract_confirmed_risk_tags(row),
            ["근저당", "공동담보", "말소 약속", "경매·공매", "임차권등기"],
        )

    def test_unknown_fields_become_required_checks(self):
        row = {
            "housing_type": "미상",
            "deposit_range": "1억~2억",
            "contract_status": "계약종료",
            "senior_rights": "미상",
            "guarantee_product_type": "unknown",
            "situation_summary_safe": "",
            "special_notes_safe": "",
        }

        self.assertEqual(
            extract_required_check_tags(row, "unknown"),
            [
                "주택유형 확인",
                "선순위권리 확인",
                "반환보증 확인",
                "보증상품 유형 확인",
            ],
        )

    def test_source_summary_is_bounded(self):
        summary = make_source_summary("가" * 400, max_length=100)
        self.assertLessEqual(len(summary), 103)
        self.assertTrue(summary.endswith("..."))


if __name__ == "__main__":
    unittest.main()
