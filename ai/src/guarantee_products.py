from __future__ import annotations

import re
from typing import Any


JEONSE_RETURN = "jeonse_return"
RENTAL_DEPOSIT = "rental_deposit"
JEONSE_LOAN = "jeonse_loan"
UNKNOWN_PRODUCT = "unknown"

PRODUCT_LABELS = {
    JEONSE_RETURN: "전세보증금반환보증",
    RENTAL_DEPOSIT: "임대보증금보증",
    JEONSE_LOAN: "전세자금대출특약보증",
    UNKNOWN_PRODUCT: "보증상품 미확인",
}

SELECTABLE_PRODUCT_TYPES = {JEONSE_RETURN, RENTAL_DEPOSIT, UNKNOWN_PRODUCT}

PRODUCT_ALIASES = {
    "전세": JEONSE_RETURN,
    "전세보증": JEONSE_RETURN,
    "전세보증금반환보증": JEONSE_RETURN,
    "전세보증보험": JEONSE_RETURN,
    "jeonse": JEONSE_RETURN,
    "jeonse_return": JEONSE_RETURN,
    "임대": RENTAL_DEPOSIT,
    "임대보증": RENTAL_DEPOSIT,
    "임대보증금보증": RENTAL_DEPOSIT,
    "개인임대사업자임대보증금보증": RENTAL_DEPOSIT,
    "rental": RENTAL_DEPOSIT,
    "rental_deposit": RENTAL_DEPOSIT,
    "전세자금대출특약보증": JEONSE_LOAN,
    "jeonse_loan": JEONSE_LOAN,
    "": UNKNOWN_PRODUCT,
    "미상": UNKNOWN_PRODUCT,
    "미확인": UNKNOWN_PRODUCT,
    "unknown": UNKNOWN_PRODUCT,
    "none": UNKNOWN_PRODUCT,
    "null": UNKNOWN_PRODUCT,
}

JEONSE_CASE_PATTERN = re.compile(
    r"(?:전세보증금반환보증|전세보증보험|전세지킴보증)"
)
RENTAL_CASE_PATTERN = re.compile(
    r"(?:임대보증금보증|임대보증보험|임대인\s*보증보험)"
)


def canonical_product_type(value: Any) -> str:
    if value is None:
        return UNKNOWN_PRODUCT
    text = re.sub(r"\s+", "", str(value)).strip()
    lowered = text.lower()
    if lowered in PRODUCT_ALIASES:
        return PRODUCT_ALIASES[lowered]
    if "전세자금대출" in text:
        return JEONSE_LOAN
    if "전세보증금반환" in text or "전세보증보험" in text:
        return JEONSE_RETURN
    if "임대보증금보증" in text or "임대보증보험" in text:
        return RENTAL_DEPOSIT
    return UNKNOWN_PRODUCT


def product_label(product_type: Any) -> str:
    return PRODUCT_LABELS[canonical_product_type(product_type)]


def infer_case_product_type(text: Any) -> str:
    clean_text = "" if text is None else str(text)
    has_jeonse = bool(JEONSE_CASE_PATTERN.search(clean_text))
    has_rental = bool(RENTAL_CASE_PATTERN.search(clean_text))
    if has_jeonse == has_rental:
        return UNKNOWN_PRODUCT
    return JEONSE_RETURN if has_jeonse else RENTAL_DEPOSIT
