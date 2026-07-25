import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from preprocess_consultations import deidentify, normalize_text  # noqa: E402


class PreprocessConsultationsTest(unittest.TestCase):
    def test_normalize_text_uses_unknown_for_missing_category(self):
        self.assertEqual(normalize_text(None, "미상"), "미상")

    def test_deidentify_replaces_contact_and_address(self):
        counts = {
            "resident_id": 0,
            "email": 0,
            "phone": 0,
            "road_address": 0,
        }
        source = "연락처 010-1234-5678, test@example.com, 안심로 12"

        result = deidentify(source, counts)

        self.assertEqual(result, "연락처 [전화번호], [이메일], [상세주소]")
        self.assertEqual(counts["phone"], 1)
        self.assertEqual(counts["email"], 1)
        self.assertEqual(counts["road_address"], 1)


if __name__ == "__main__":
    unittest.main()
