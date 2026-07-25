import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from easy_explanation import (  # noqa: E402
    generate_easy_explanation,
    template_explanation,
    validate_explanation,
)


def sample_case(tags=None, checks=None):
    return {
        "case_id": "CASE-0001",
        "matched_factors": ["다세대주택"],
        "confirmed_risk_tags": tags or [],
        "required_check_tags": checks or [],
        "dispute_type": "보증금미반환",
        "progress_stage": "상담·검토",
    }


class EasyExplanationTest(unittest.TestCase):
    def test_template_uses_confirmed_context_and_two_actions(self):
        case = sample_case(["근저당", "말소 약속"], ["반환보증 확인"])
        result = template_explanation(case)

        self.assertIn("근저당", result["easy_explanation"])
        self.assertIn("말소", result["easy_explanation"])
        self.assertEqual(len(result["actions"]), 2)
        self.assertEqual(validate_explanation(case, result["easy_explanation"], result["actions"]), [])

    def test_unknown_information_is_not_called_a_confirmed_risk(self):
        result = template_explanation(sample_case([], ["반환보증 확인"]))

        self.assertIn("위험이 확정되는 것은 아닙니다", result["easy_explanation"])

    def test_source_fraud_category_is_shown_as_neutral_dispute_label(self):
        case = sample_case(["근저당"], [])
        case["dispute_type"] = "전세사기"

        result = template_explanation(case)

        self.assertIn("보증금 반환 분쟁", result["easy_explanation"])
        self.assertNotIn("전세사기", result["easy_explanation"])

    def test_safety_check_rejects_determination_and_new_fact(self):
        case = sample_case(["근저당"], [])
        errors = validate_explanation(
            case,
            "이 매물은 전세사기입니다. 신탁 관계도 확인되었습니다.",
            ["확인하세요.", "상담하세요."],
        )

        self.assertIn("fraud_determination", errors)
        self.assertIn("unsupported_fact:신탁", errors)

    def test_invalid_llm_result_uses_template_fallback(self):
        case = sample_case(["근저당"], [])

        def unsafe_generator(system_prompt, user_prompt):
            return {
                "easy_explanation": "이 매물은 무조건 전세사기입니다.",
                "actions": ["계약하지 마세요.", "신고하세요."],
            }

        result = generate_easy_explanation(case, unsafe_generator)

        self.assertEqual(result["explanation_source"], "template_fallback")
        self.assertNotIn("전세사기입니다", result["easy_explanation"])

    def test_safe_llm_result_is_used(self):
        case = sample_case(["근저당"], [])

        def safe_generator(system_prompt, user_prompt):
            return {
                "easy_explanation": "이 상담사례에서는 근저당이 확인되었습니다. 권리 순서를 서류로 확인할 필요가 있습니다.",
                "actions": [
                    "최신 등기부에서 근저당을 확인하세요.",
                    "채권최고액을 확인하세요.",
                ],
            }

        result = generate_easy_explanation(case, safe_generator)

        self.assertEqual(result["explanation_source"], "llm")


if __name__ == "__main__":
    unittest.main()
