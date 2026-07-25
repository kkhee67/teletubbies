import json
import re
import unittest
from datetime import datetime
from pathlib import Path

from backend.scoring.service import analyze_sample, list_sample_properties
from scripts.build_sample_results import build_sample_results


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "backend" / "data"
FACT_FIELDS = (
    "property_type",
    "reference_value",
    "mortgage_status",
    "seizure_status",
    "joint_collateral",
    "guarantee_status",
    "housing_required_info",
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class DataContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(DATA_DIR / "data_manifest.json")
        cls.properties = load_json(DATA_DIR / "mock_properties.json")
        cls.locations = load_json(DATA_DIR / "location_context.json")
        cls.contract = load_json(DATA_DIR / "analysis_api_contract.json")
        cls.sample_results = load_json(DATA_DIR / "sample_analysis_results.json")

    def test_manifest_points_to_existing_canonical_files(self):
        self.assertEqual(
            self.manifest["canonical_scope"],
            "explainable_rental_risk_analysis",
        )
        self.assertEqual(self.manifest["canonical_data_root"], "backend/data")
        for dataset in self.manifest["datasets"].values():
            path = ROOT / dataset["path"]
            self.assertTrue(path.is_file(), dataset["path"])
            load_json(path)
        self.assertEqual(
            self.manifest["datasets"]["properties"]["record_count"],
            len(self.properties),
        )
        self.assertEqual(
            self.manifest["datasets"]["location_context"]["record_count"],
            len(self.locations),
        )
        self.assertEqual(
            self.manifest["datasets"]["sample_results"]["record_count"],
            len(self.sample_results),
        )

    def test_property_ids_are_unique_and_stable(self):
        property_ids = [item["property_id"] for item in self.properties]
        self.assertEqual(len(property_ids), len(set(property_ids)))
        self.assertTrue(
            all(re.fullmatch(r"MOCK-\d{3}", value) for value in property_ids)
        )

    def test_property_metadata_matches_manifest(self):
        for item in self.properties:
            with self.subTest(property_id=item["property_id"]):
                self.assertEqual(item["dataset_type"], self.manifest["dataset_type"])
                self.assertEqual(item["data_version"], self.manifest["data_version"])
                self.assertEqual(item["updated_at"], self.manifest["updated_at"])
                datetime.fromisoformat(item["updated_at"])
                self.assertTrue(item["is_mock"])

    def test_every_fact_has_provenance_and_retrieval_time(self):
        for item in self.properties:
            for field_name in FACT_FIELDS:
                with self.subTest(
                    property_id=item["property_id"], field=field_name
                ):
                    fact = item[field_name]
                    self.assertIn(fact["source_type"], {"mock", "official", "user_confirmed"})
                    self.assertTrue(fact["source_name"])
                    datetime.strptime(fact["reference_date"], "%Y-%m-%d")
                    datetime.fromisoformat(fact["retrieved_at"])

    def test_guarantee_status_keeps_evidence_and_estimate_separate(self):
        statuses = {
            item["guarantee_status"]["value"]: item["guarantee_status"]
            for item in self.properties
        }
        enrolled = statuses["enrolled"]
        self.assertEqual(enrolled["source_type"], "official")
        self.assertTrue(enrolled["source_name"])
        estimated = statuses["estimated_eligible"]
        self.assertEqual(estimated["source_type"], "mock")
        self.assertFalse(
            self.manifest["policies"]["synthetic_records_are_real_evidence"]
        )

    def test_location_context_is_versioned_and_never_scores_risk(self):
        property_ids = {item["property_id"] for item in self.properties}
        self.assertEqual(set(self.locations), property_ids)
        for property_id, context in self.locations.items():
            with self.subTest(property_id=property_id):
                self.assertEqual(context["dataset_type"], self.manifest["dataset_type"])
                self.assertEqual(context["data_version"], self.manifest["data_version"])
                self.assertEqual(context["updated_at"], self.manifest["updated_at"])
                datetime.fromisoformat(context["retrieved_at"])
                self.assertFalse(context["included_in_risk_score"])

    def test_search_and_analysis_expose_the_same_data_version(self):
        search_items = list_sample_properties()
        search_item = next(
            item for item in search_items if item["property_id"] == "MOCK-001"
        )
        analysis = analyze_sample("MOCK-001", 200_000_000)
        self.assertEqual(
            search_item["data_version"], analysis["property"]["data_version"]
        )
        self.assertEqual(
            analysis["property"]["data_version"], self.manifest["data_version"]
        )
        self.assertEqual(
            analysis["property"]["dataset_type"], self.manifest["dataset_type"]
        )

    def test_saved_sample_results_match_current_rules(self):
        self.assertEqual(self.sample_results, build_sample_results())

    def test_internal_contract_declares_version_policy(self):
        self.assertEqual(self.contract["contract_version"], "1.1.0")
        data_contract = self.contract["data_contract"]
        self.assertEqual(
            data_contract["manifest_file"], "backend/data/data_manifest.json"
        )
        self.assertEqual(
            data_contract["version_mismatch_action"],
            "reload_property_before_analysis",
        )
        self.assertEqual(
            data_contract["version_mismatch_implementation"], "contract_only"
        )


if __name__ == "__main__":
    unittest.main()
