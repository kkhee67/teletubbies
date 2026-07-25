import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from guarantee_products import (  # noqa: E402
    JEONSE_RETURN,
    RENTAL_DEPOSIT,
    UNKNOWN_PRODUCT,
    canonical_product_type,
    infer_case_product_type,
)


class GuaranteeProductsTest(unittest.TestCase):
    def test_product_names_are_normalized(self):
        self.assertEqual(
            canonical_product_type("전세보증금반환보증"), JEONSE_RETURN
        )
        self.assertEqual(
            canonical_product_type("개인임대사업자임대보증금보증"),
            RENTAL_DEPOSIT,
        )

    def test_case_product_requires_explicit_product_wording(self):
        self.assertEqual(
            infer_case_product_type("HUG 전세보증보험에 가입했습니다."),
            JEONSE_RETURN,
        )
        self.assertEqual(
            infer_case_product_type("임대보증금보증 증서를 확인했습니다."),
            RENTAL_DEPOSIT,
        )
        self.assertEqual(
            infer_case_product_type("임대보증금 반환이 늦어지고 있습니다."),
            UNKNOWN_PRODUCT,
        )

    def test_conflicting_product_words_remain_unknown(self):
        self.assertEqual(
            infer_case_product_type(
                "전세보증보험과 임대보증금보증이 모두 언급되었습니다."
            ),
            UNKNOWN_PRODUCT,
        )


if __name__ == "__main__":
    unittest.main()
