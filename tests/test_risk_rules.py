import json
import unittest
from copy import deepcopy
from pathlib import Path

from backend.scoring.confidence import calculate_analysis_confidence
from backend.scoring.risk_rules import (
    RISK_RULES_VERSION,
    analyze_property,
    calculate_deposit_ratio,
)
from backend.scoring.service import analyze_sample, list_sample_properties
from scripts.build_sample_results import build_sample_results

ROOT = Path(__file__).resolve().parents[1]


class RiskRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.properties = json.loads(
            (ROOT / "backend/data/mock_properties.json").read_text(encoding="utf-8")
        )
        cls.locations = json.loads(
            (ROOT / "backend/data/location_context.json").read_text(encoding="utf-8")
        )
        cls.spec = json.loads(
            (ROOT / "analysis/05_risk_rules/risk_rules_spec.json").read_text(encoding="utf-8")
        )

    def property(self, property_id):
        return deepcopy(next(p for p in self.properties if p["property_id"] == property_id))

    @staticmethod
    def codes(result, key):
        return {item["code"] for item in result["analysis"][key]}

    def test_high_risk_sample_is_reconsider(self):
        result = analyze_property(
            self.property("MOCK-001"),
            200_000_000,
            location_context=self.locations["MOCK-001"],
        )
        self.assertEqual(result["analysis"]["risk_stage"], "계약 전 재검토")
        self.assertEqual(result["analysis"]["confirmed_risk_count"], 2)
        self.assertEqual(
            self.codes(result, "confirmed_risks"),
            {"MORTGAGE_EXISTS", "GUARANTEE_INELIGIBLE"},
        )
        self.assertFalse(result["location_context"]["included_in_risk_score"])

    def test_unverified_ratio_is_provisional_not_confirmed_risk(self):
        result = analyze_property(self.property("MOCK-001"), 200_000_000)
        self.assertEqual(result["property"]["deposit_ratio"], 90.9)
        self.assertEqual(result["property"]["deposit_ratio_status"], "provisional")
        self.assertNotIn("HIGH_DEPOSIT_RATIO", self.codes(result, "confirmed_risks"))
        self.assertIn("REFERENCE_VALUE_UNVERIFIED", self.codes(result, "required_checks"))
        self.assertIn("VALUE_UNIT_COMPARABILITY_UNKNOWN", self.codes(result, "required_checks"))

    def test_verified_deposit_ratio_uses_one_code_with_two_severities(self):
        prop = self.property("MOCK-002")
        medium = analyze_property(prop, 432_000_000)
        high = analyze_property(prop, 480_000_000)

        medium_signal = next(r for r in medium["analysis"]["confirmed_risks"] if r["code"] == "HIGH_DEPOSIT_RATIO")
        high_signal = next(r for r in high["analysis"]["confirmed_risks"] if r["code"] == "HIGH_DEPOSIT_RATIO")
        self.assertEqual(medium_signal["severity"], "medium")
        self.assertEqual(high_signal["severity"], "high")
        self.assertNotIn("DEPOSIT_RATIO_AT_LEAST_100", self.codes(high, "confirmed_risks"))

    def test_unknown_information_is_not_confirmed_risk(self):
        result = analyze_property(self.property("MOCK-003"), 180_000_000)
        self.assertEqual(result["analysis"]["confirmed_risk_count"], 0)
        self.assertEqual(result["analysis"]["risk_stage"], "추가 확인 필요")
        checks = self.codes(result, "required_checks")
        self.assertIn("SENIOR_TENANT_DEPOSITS_UNKNOWN", checks)
        self.assertIn("MORTGAGE_UNKNOWN", checks)
        self.assertIn("GUARANTEE_UNKNOWN", checks)

    def test_unverified_absence_is_not_treated_as_confirmed_clear(self):
        prop = self.property("MOCK-002")
        prop["is_mock"] = False
        for name in ("property_type", "mortgage_status", "seizure_status", "joint_collateral"):
            prop[name]["source_type"] = "mock"
        result = analyze_property(prop, 250_000_000)
        checks = self.codes(result, "required_checks")
        self.assertIn("PROPERTY_TYPE_UNKNOWN", checks)
        self.assertIn("MORTGAGE_UNKNOWN", checks)
        self.assertIn("SEIZURE_UNKNOWN", checks)
        self.assertIn("JOINT_COLLATERAL_UNKNOWN", checks)
        self.assertEqual(result["analysis"]["confirmed_risk_count"], 0)

    def test_officetel_estimate_creates_checks_not_risk(self):
        result = analyze_property(self.property("MOCK-004"), 230_000_000)
        self.assertEqual(result["analysis"]["confirmed_risk_count"], 0)
        checks = self.codes(result, "required_checks")
        self.assertIn("OFFICETEL_USE_UNKNOWN", checks)
        self.assertIn("GUARANTEE_ESTIMATED_ONLY", checks)

    def test_enrolled_guarantee_does_not_cancel_or_add_risk(self):
        clean = analyze_property(self.property("MOCK-002"), 250_000_000)
        self.assertEqual(clean["guarantee"]["group"], "protected")
        self.assertEqual(clean["analysis"]["risk_stage"], "기본 확인")
        self.assertNotIn("GUARANTEE_INELIGIBLE", self.codes(clean, "confirmed_risks"))

        prop = self.property("MOCK-002")
        prop["mortgage_status"]["value"] = "exists"
        risky = analyze_property(prop, 250_000_000)
        self.assertIn("MORTGAGE_EXISTS", self.codes(risky, "confirmed_risks"))

    def test_guarantee_six_status_mapping(self):
        expectations = {
            "estimated_eligible": (None, "GUARANTEE_ESTIMATED_ONLY"),
            "officially_eligible": (None, "GUARANTEE_ENROLLMENT_NOT_COMPLETED"),
            "applied": (None, "GUARANTEE_ENROLLMENT_NOT_COMPLETED"),
            "enrolled": (None, None),
            "ineligible": ("GUARANTEE_INELIGIBLE", None),
            "unknown": (None, "GUARANTEE_UNKNOWN"),
        }
        for status, (risk_code, check_code) in expectations.items():
            with self.subTest(status=status):
                prop = self.property("MOCK-002")
                prop["guarantee_status"]["value"] = status
                result = analyze_property(prop, 250_000_000)
                risks = self.codes(result, "confirmed_risks")
                checks = self.codes(result, "required_checks")
                if risk_code:
                    self.assertIn(risk_code, risks)
                else:
                    self.assertNotIn("GUARANTEE_INELIGIBLE", risks)
                if check_code:
                    self.assertIn(check_code, checks)
                else:
                    self.assertFalse({"GUARANTEE_ESTIMATED_ONLY", "GUARANTEE_ENROLLMENT_NOT_COMPLETED", "GUARANTEE_UNKNOWN"} & checks)

    def test_down_contract_is_high_risk(self):
        prop = self.property("MOCK-002")
        prop["down_contract_requested"] = True
        result = analyze_property(prop, 250_000_000)
        signal = next(r for r in result["analysis"]["confirmed_risks"] if r["code"] == "DOWN_CONTRACT_REQUESTED")
        self.assertEqual(signal["severity"], "high")
        self.assertEqual(result["analysis"]["risk_stage"], "주의")

    def test_confidence_uses_verified_sources_only(self):
        verified = self.property("MOCK-002")
        fields = {name: verified.get(name) for name in (
            "property_type", "reference_value", "mortgage_status", "seizure_status",
            "joint_collateral", "guarantee_status", "housing_required_info",
        )}
        self.assertEqual(calculate_analysis_confidence(fields), 100)

        mock = self.property("MOCK-001")
        mock_fields = {name: mock.get(name) for name in fields}
        self.assertEqual(calculate_analysis_confidence(mock_fields), 0)

    def test_estimated_guarantee_does_not_increase_confidence(self):
        prop = self.property("MOCK-002")
        prop["guarantee_status"]["value"] = "estimated_eligible"
        fields = {name: prop.get(name) for name in (
            "property_type", "reference_value", "mortgage_status", "seizure_status",
            "joint_collateral", "guarantee_status", "housing_required_info",
        )}
        self.assertEqual(calculate_analysis_confidence(fields), 82)

    def test_location_context_never_changes_stage(self):
        prop = self.property("MOCK-003")
        without = analyze_property(prop, 180_000_000)
        with_location = analyze_property(
            prop, 180_000_000, location_context=self.locations["MOCK-003"]
        )
        self.assertEqual(without["analysis"]["risk_stage"], with_location["analysis"]["risk_stage"])
        self.assertFalse(with_location["location_context"]["included_in_risk_score"])

    def test_invalid_deposit_rejected(self):
        for value in (0, -1, True, "100000000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                calculate_deposit_ratio(value, 200_000_000)

    def test_response_has_no_numeric_risk_score(self):
        result = analyze_property(self.property("MOCK-002"), 250_000_000)
        self.assertNotIn("risk_score", result["analysis"])
        self.assertNotIn("accident_probability", result["analysis"])
        self.assertEqual(result["analysis"]["rule_version"], self.spec["version"])
        self.assertEqual(RISK_RULES_VERSION, self.spec["version"])

    def test_service_lists_and_analyzes_samples(self):
        samples = list_sample_properties()
        self.assertEqual(len(samples), 5)
        self.assertTrue(all(item["is_mock"] for item in samples))
        self.assertTrue(all(item["dataset_type"] == "synthetic" for item in samples))
        self.assertTrue(all(item["data_version"] == "2026-07-26-v1" for item in samples))
        result = analyze_sample("MOCK-001", 200_000_000)
        self.assertEqual(result["property"]["property_id"], "MOCK-001")
        self.assertEqual(result["property"]["dataset_type"], "synthetic")
        self.assertEqual(result["property"]["data_version"], "2026-07-26-v1")

    def test_sample_results_cover_all_four_stages(self):
        stages = {row["result"]["analysis"]["risk_stage"] for row in build_sample_results()}
        self.assertEqual(stages, {"기본 확인", "추가 확인 필요", "주의", "계약 전 재검토"})

    def test_service_rejects_unknown_sample(self):
        with self.assertRaises(KeyError):
            analyze_sample("NOT-FOUND", 200_000_000)


if __name__ == "__main__":
    unittest.main()
