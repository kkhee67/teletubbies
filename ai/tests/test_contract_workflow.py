import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from contract_workflow import (  # noqa: E402
    GUARANTEE_STATUSES,
    address_identity,
    build_analysis,
    build_guarantee,
    calculate_analysis_confidence,
    default_facts,
    demo_facts,
    fill_from_situation,
    guarantee_from_input,
)


class ContractWorkflowTest(unittest.TestCase):
    def test_address_is_reduced_to_administrative_area(self):
        display, sido, sigungu = address_identity(
            "부산시 수영구 광안해변로 123 101동 202호"
        )

        self.assertEqual(display, "부산광역시 수영구 일대")
        self.assertEqual(sido, "부산광역시")
        self.assertEqual(sigungu, "수영구")
        self.assertNotIn("광안해변로", display)

    def test_only_enrolled_status_is_protected(self):
        for status, config in GUARANTEE_STATUSES.items():
            guarantee = build_guarantee(
                "jeonse_return",
                {
                    "status": status,
                    "source": {
                        "source_type": "official",
                        "source_name": "테스트 공식자료",
                        "reference_date": "2026-07-25",
                    },
                },
            )
            self.assertEqual(guarantee["is_enrolled"], status == "enrolled")
            self.assertEqual(
                guarantee["group"] == "protected", status == "enrolled"
            )
            self.assertEqual(guarantee["group"], config["group"])

    def test_future_mortgage_removal_promise_means_mortgage_exists(self):
        facts = fill_from_situation(
            default_facts(),
            "집주인이 잔금일에 근저당을 말소한다고 했습니다.",
        )

        self.assertEqual(facts["mortgage"]["status"], "exists")
        self.assertEqual(
            facts["mortgage"]["source"]["source_type"], "user_confirmed"
        )

    def test_mock_data_does_not_raise_analysis_confidence(self):
        facts = demo_facts()
        guarantee = guarantee_from_input(None, demo_mode=True)

        self.assertEqual(calculate_analysis_confidence(facts, guarantee), 0)

    def test_unknown_values_are_checks_not_confirmed_risks(self):
        facts = default_facts()
        guarantee = guarantee_from_input(None, demo_mode=False)
        analysis = build_analysis(200_000_000, facts, guarantee)

        self.assertEqual(analysis["confirmed_risk_count"], 0)
        self.assertGreaterEqual(analysis["required_check_count"], 1)
        self.assertTrue(
            all(item["severity"] == "check" for item in analysis["required_checks"])
        )

    def test_down_contract_request_is_confirmed_only_when_explicit(self):
        facts = default_facts()
        guarantee = guarantee_from_input(None, demo_mode=False)

        analysis = build_analysis(
            200_000_000,
            facts,
            guarantee,
            "집주인이 실제 보증금보다 낮게 계약서를 작성하자고 했습니다.",
        )

        self.assertIn(
            "DOWN_CONTRACT_REQUESTED",
            {item["code"] for item in analysis["confirmed_risks"]},
        )

    def test_guarantee_unknown_uses_team_contract_code(self):
        analysis = build_analysis(
            200_000_000,
            default_facts(),
            guarantee_from_input(None, demo_mode=False),
        )

        self.assertIn(
            "GUARANTEE_UNKNOWN",
            {item["code"] for item in analysis["required_checks"]},
        )


if __name__ == "__main__":
    unittest.main()
