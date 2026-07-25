import sys
import unittest
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from product_context import ProductContextRepository  # noqa: E402


class ProductContextTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repository = ProductContextRepository()

    def test_all_seven_provided_sources_are_registered(self):
        self.assertEqual(self.repository.data_source_count, 7)

    def test_jeonse_context_uses_only_jeonse_and_shared_sources(self):
        context = self.repository.get_context("jeonse_return", "다세대주택")
        source_ids = {source["source_id"] for source in context["sources"]}

        self.assertTrue(context["product_separation_applied"])
        self.assertEqual(
            source_ids,
            {
                "auction_distributions",
                "guarantee_subrogation",
                "jeonse_accident_status",
                "jeonse_housing_value_ratio",
                "debtor_auction_status",
            },
        )

    def test_rental_context_uses_only_rental_and_shared_sources(self):
        context = self.repository.get_context("rental_deposit", "오피스텔")
        source_ids = {source["source_id"] for source in context["sources"]}

        self.assertTrue(context["product_separation_applied"])
        self.assertEqual(
            source_ids,
            {
                "rental_guarantee_accidents",
                "auction_distributions",
                "guarantee_subrogation",
                "debtor_auction_status",
            },
        )

    def test_data_usage_lists_all_sources_without_cross_product_mixing(self):
        usage = self.repository.get_data_usage("jeonse_return")
        applied = {
            source["source_id"]: source["applied_to_request"]
            for source in usage["sources"]
        }

        self.assertEqual(usage["total_source_count"], 7)
        self.assertTrue(applied["jeonse_accident_status"])
        self.assertFalse(applied["rental_guarantee_accidents"])

    def test_future_synthetic_dates_are_flagged_not_used_as_reference_date(self):
        context = self.repository.get_context("jeonse_return")
        flagged = [
            source for source in context["sources"] if source["future_date_count"]
        ]

        self.assertTrue(flagged)
        for source in flagged:
            self.assertTrue(source["data_quality_notes"])
            if source["reference_date"]:
                self.assertLessEqual(
                    date.fromisoformat(source["reference_date"]), date.today()
                )


if __name__ == "__main__":
    unittest.main()
