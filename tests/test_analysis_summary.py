import tempfile
import unittest
from pathlib import Path

from scripts.build_analysis_summary import build_summary


class AnalysisSummaryTest(unittest.TestCase):
    def test_summary_is_grouped_without_probability_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "전세사고(주택가액 대비 임대보증금)_합성데이터.csv"
            path.write_text(
                "주택유형,주택가액 대비 임대보증금액 비율(%)\n"
                "아파트,80\n아파트,100\n기타(오피스텔),95\n",
                encoding="utf-8-sig",
            )
            result = build_summary(path)
        self.assertEqual(result["housing_stats"]["apartment"]["count"], 2)
        self.assertEqual(result["housing_stats"]["officetel"]["over_90_rate"], 1.0)
        self.assertIn("사고확률", result["interpretation_notice"])


if __name__ == "__main__":
    unittest.main()
