from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
import re
from statistics import median
from typing import Any
from urllib.parse import unquote
from xml.etree import ElementTree

import httpx


DEFAULT_JUSO_SEARCH_URL = "https://business.juso.go.kr/addrlink/addrLinkApi.do"
DEFAULT_BUILDING_REGISTER_TITLE_URL = (
    "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
)
DEFAULT_RENT_API_URLS = {
    "apartment": "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
    "officetel": "https://apis.data.go.kr/1613000/RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent",
    "row_house": "https://apis.data.go.kr/1613000/RTMSDataSvcRHRent/getRTMSDataSvcRHRent",
    "detached": "https://apis.data.go.kr/1613000/RTMSDataSvcSHRent/getRTMSDataSvcSHRent",
}
DEFAULT_LOOKBACK_MONTHS = 6
DEFAULT_TIMEOUT_SECONDS = 5.0

RENT_TYPE_SOURCE_NAMES = {
    "apartment": "MOLIT apartment rent actual transaction API",
    "officetel": "MOLIT officetel rent actual transaction API",
    "row_house": "MOLIT row-house rent actual transaction API",
    "multi_unit": "MOLIT row-house/multi-unit rent actual transaction API",
    "multi_household": "MOLIT single/multi-household rent actual transaction API",
    "detached": "MOLIT single/multi-household rent actual transaction API",
    "unknown": "MOLIT rent actual transaction APIs",
}
RENT_TYPE_TO_API_TYPE = {
    "apartment": "apartment",
    "officetel": "officetel",
    "row_house": "row_house",
    "multi_unit": "row_house",
    "multi_household": "detached",
    "detached": "detached",
}
ALL_RENT_API_TYPES = ["apartment", "officetel", "row_house", "detached"]

DISTRICT_PATTERN = re.compile(r"([\uac00-\ud7a3A-Za-z0-9]+(?:\uad6c|\uad70))\b")
CITY_PATTERN = re.compile(r"([\uac00-\ud7a3A-Za-z0-9]+\uc2dc)\b")

SEOUL_LAWD_CODES = {
    "\uc885\ub85c\uad6c": "11110",
    "\uc911\uad6c": "11140",
    "\uc6a9\uc0b0\uad6c": "11170",
    "\uc131\ub3d9\uad6c": "11200",
    "\uad11\uc9c4\uad6c": "11215",
    "\ub3d9\ub300\ubb38\uad6c": "11230",
    "\uc911\ub791\uad6c": "11260",
    "\uc131\ubd81\uad6c": "11290",
    "\uac15\ubd81\uad6c": "11305",
    "\ub3c4\ubd09\uad6c": "11320",
    "\ub178\uc6d0\uad6c": "11350",
    "\uc740\ud3c9\uad6c": "11380",
    "\uc11c\ub300\ubb38\uad6c": "11410",
    "\ub9c8\ud3ec\uad6c": "11440",
    "\uc591\ucc9c\uad6c": "11470",
    "\uac15\uc11c\uad6c": "11500",
    "\uad6c\ub85c\uad6c": "11530",
    "\uae08\ucc9c\uad6c": "11545",
    "\uc601\ub4f1\ud3ec\uad6c": "11560",
    "\ub3d9\uc791\uad6c": "11590",
    "\uad00\uc545\uad6c": "11620",
    "\uc11c\ucd08\uad6c": "11650",
    "\uac15\ub0a8\uad6c": "11680",
    "\uc1a1\ud30c\uad6c": "11710",
    "\uac15\ub3d9\uad6c": "11740",
}

BUSAN_LAWD_CODES = {
    "\uc911\uad6c": "26110",
    "\uc11c\uad6c": "26140",
    "\ub3d9\uad6c": "26170",
    "\uc601\ub3c4\uad6c": "26200",
    "\ubd80\uc0b0\uc9c4\uad6c": "26230",
    "\ub3d9\ub798\uad6c": "26260",
    "\ub0a8\uad6c": "26290",
    "\ubd81\uad6c": "26320",
    "\ud574\uc6b4\ub300\uad6c": "26350",
    "\uc0ac\ud558\uad6c": "26380",
    "\uae08\uc815\uad6c": "26410",
    "\uac15\uc11c\uad6c": "26440",
    "\uc5f0\uc81c\uad6c": "26470",
    "\uc218\uc601\uad6c": "26500",
    "\uc0ac\uc0c1\uad6c": "26530",
    "\uae30\uc7a5\uad70": "26710",
}


@dataclass(frozen=True)
class MarketReference:
    reference_value: int
    source_name: str
    source_type: str
    note: str
    lawd_cd: str
    deal_months: list[str]
    sample_count: int
    api_types: list[str]
    housing_type: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "reference_value": self.reference_value,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "note": self.note,
            "lawd_cd": self.lawd_cd,
            "deal_months": self.deal_months,
            "sample_count": self.sample_count,
            "api_types": self.api_types,
            "housing_type": self.housing_type,
        }


def lookup_official_property_data(
    address: str,
    housing_type_hint: str | None = None,
) -> dict[str, Any]:
    address_meta = lookup_address(address)
    building_meta = lookup_building_register(address_meta) if address_meta else None
    housing_type = (
        (building_meta or {}).get("housing_type")
        or infer_housing_type_from_address(address_meta)
        or housing_type_hint
        or "unknown"
    )
    market = estimate_reference_value(
        address,
        housing_type=housing_type,
        address_meta=address_meta,
    )
    return {
        "address": address_meta,
        "building": building_meta,
        "housing_type": housing_type,
        "market_reference": market,
    }


def estimate_reference_value(
    address: str,
    housing_type: str | None = None,
    address_meta: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not market_reference_enabled():
        return None

    service_key = public_data_service_key()
    if not service_key:
        return None

    lawd_cd = (
        (address_meta or {}).get("lawd_cd")
        or resolve_lawd_code_from_juso(address)
        or resolve_lawd_code_from_local_map(address)
    )
    if not lawd_cd:
        return None

    months = recent_deal_months(lookback_months())
    api_types = rent_api_types_for_housing_type(housing_type)
    deposits: list[int] = []
    successful_api_types: list[str] = []
    for api_type in api_types:
        before_count = len(deposits)
        for deal_ymd in months:
            try:
                deposits.extend(fetch_rent_deposits(api_type, lawd_cd, deal_ymd, service_key))
            except (httpx.HTTPError, ElementTree.ParseError, ValueError, TypeError):
                continue
        if len(deposits) > before_count:
            successful_api_types.append(api_type)

    if not deposits:
        return None

    reference_value = int(round(median(deposits)))
    source_name = RENT_TYPE_SOURCE_NAMES.get(housing_type or "unknown") or RENT_TYPE_SOURCE_NAMES[
        "unknown"
    ]
    if len(successful_api_types) > 1 or not housing_type or housing_type == "unknown":
        source_name = RENT_TYPE_SOURCE_NAMES["unknown"]
    return MarketReference(
        reference_value=reference_value,
        source_name=source_name,
        source_type="public_api",
        note=(
            "Reference value is the median deposit from recent rent transactions "
            "in the same legal-district area. It is not an official appraisal, "
            "public price, or guarantee review result."
        ),
        lawd_cd=lawd_cd,
        deal_months=months,
        sample_count=len(deposits),
        api_types=successful_api_types or api_types,
        housing_type=housing_type or "unknown",
    ).as_dict()


def lookup_address(address: str) -> dict[str, Any] | None:
    key = juso_confirm_key()
    if not key:
        return None

    try:
        response = httpx.get(
            juso_search_url(),
            params={
                "confmKey": key,
                "currentPage": 1,
                "countPerPage": 1,
                "keyword": address,
                "resultType": "json",
            },
            timeout=market_reference_timeout(),
        )
        response.raise_for_status()
        rows = response.json().get("results", {}).get("juso", [])
        if not rows:
            return None
        row = rows[0]
        adm_cd = str(row.get("admCd") or "")
        return {
            "road_address": row.get("roadAddr") or row.get("roadFullAddr") or address,
            "jibun_address": row.get("jibunAddr") or "",
            "lawd_cd": adm_cd[:5] if len(adm_cd) >= 5 else "",
            "adm_cd": adm_cd,
            "sigungu_cd": adm_cd[:5] if len(adm_cd) >= 5 else "",
            "bjdong_cd": adm_cd[5:10] if len(adm_cd) >= 10 else "",
            "district": row.get("sggNm") or "",
            "legal_dong": row.get("emdNm") or "",
            "road_name": row.get("rn") or "",
            "building_management_number": row.get("bdMgtSn") or "",
            "is_apartment_building": str(row.get("bdKdcd") or "") == "1",
            "plat_gb_cd": "1" if str(row.get("mtYn") or "0") == "1" else "0",
            "bun": normalize_lot_number(row.get("lnbrMnnm")),
            "ji": normalize_lot_number(row.get("lnbrSlno")),
        }
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return None


def lookup_building_register(address_meta: dict[str, Any]) -> dict[str, Any] | None:
    if not building_register_enabled():
        return None

    service_key = building_register_service_key()
    if not service_key:
        return None

    sigungu_cd = address_meta.get("sigungu_cd") or ""
    bjdong_cd = address_meta.get("bjdong_cd") or ""
    if not sigungu_cd or not bjdong_cd:
        return None

    try:
        response = httpx.get(
            building_register_title_url(),
            params={
                "serviceKey": service_key,
                "sigunguCd": sigungu_cd,
                "bjdongCd": bjdong_cd,
                "platGbCd": address_meta.get("plat_gb_cd") or "0",
                "bun": address_meta.get("bun") or "0000",
                "ji": address_meta.get("ji") or "0000",
                "pageNo": 1,
                "numOfRows": 10,
                "_type": "json",
            },
            timeout=market_reference_timeout(),
        )
        response.raise_for_status()
        items = extract_response_items(response)
        if not items:
            return None
        return normalize_building_register_item(items[0])
    except (httpx.HTTPError, ElementTree.ParseError, ValueError, TypeError, KeyError):
        return None


def fetch_rent_deposits(
    api_type: str,
    lawd_cd: str,
    deal_ymd: str,
    service_key: str,
) -> list[int]:
    response = httpx.get(
        rent_api_url(api_type),
        params={
            "serviceKey": service_key,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ymd,
            "pageNo": 1,
            "numOfRows": 1000,
        },
        timeout=market_reference_timeout(),
    )
    response.raise_for_status()
    return parse_deposits(response.text)


def parse_deposits(xml_text: str) -> list[int]:
    root = ElementTree.fromstring(xml_text)
    deposits: list[int] = []
    for item in root.iter("item"):
        row = {strip_namespace(child.tag): child.text or "" for child in list(item)}
        amount = first_value(
            row,
            "\ubcf4\uc99d\uae08\uc561",
            "\ubcf4\uc99d\uae08",
            "deposit",
            "depositAmount",
            "rentDeposit",
        )
        deposit = parse_molit_money_to_won(amount)
        if deposit > 0:
            deposits.append(deposit)
    return deposits


def extract_response_items(response: httpx.Response) -> list[dict[str, Any]]:
    try:
        body = response.json()
        items = body.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items, dict):
            return [items]
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    except ValueError:
        pass

    root = ElementTree.fromstring(response.text)
    parsed_items: list[dict[str, Any]] = []
    for item in root.iter("item"):
        parsed_items.append({strip_namespace(child.tag): child.text or "" for child in list(item)})
    return parsed_items


def normalize_building_register_item(item: dict[str, Any]) -> dict[str, Any]:
    main_purpose = str(item.get("mainPurpsCdNm") or item.get("etcPurps") or "")
    use_approval_date = str(item.get("useAprDay") or "")
    return {
        "source_name": "MOLIT building register API",
        "source_type": "public_api",
        "building_name": str(item.get("bldNm") or ""),
        "main_purpose": main_purpose,
        "housing_type": classify_housing_type(main_purpose),
        "built_year": parse_year(use_approval_date),
        "use_approval_date": use_approval_date,
        "household_count": parse_optional_int(item.get("hhldCnt")),
        "family_count": parse_optional_int(item.get("fmlyCnt")),
        "ground_floor_count": parse_optional_int(item.get("grndFlrCnt")),
    }


def classify_housing_type(text: str) -> str | None:
    if not text:
        return None
    if "\uc624\ud53c\uc2a4\ud154" in text:
        return "officetel"
    if "\uc544\ud30c\ud2b8" in text:
        return "apartment"
    if "\uc5f0\ub9bd" in text:
        return "row_house"
    if "\ub2e4\uc138\ub300" in text:
        return "multi_unit"
    if "\ub2e4\uac00\uad6c" in text:
        return "multi_household"
    if "\ub2e8\ub3c5" in text:
        return "detached"
    return None


def infer_housing_type_from_address(address_meta: dict[str, Any] | None) -> str | None:
    if not address_meta:
        return None
    return "apartment" if address_meta.get("is_apartment_building") else None


def resolve_lawd_code(address: str) -> str | None:
    from_juso = resolve_lawd_code_from_juso(address)
    if from_juso:
        return from_juso
    return resolve_lawd_code_from_local_map(address)


def resolve_lawd_code_from_juso(address: str) -> str | None:
    meta = lookup_address(address)
    return meta.get("lawd_cd") if meta else None


def resolve_lawd_code_from_local_map(address: str) -> str | None:
    district = extract_district(address)
    if not district:
        return None
    if "\ubd80\uc0b0" in address:
        return BUSAN_LAWD_CODES.get(district)
    return SEOUL_LAWD_CODES.get(district)


def extract_district(address: str) -> str | None:
    match = DISTRICT_PATTERN.search(address)
    if match:
        return match.group(1)
    match = CITY_PATTERN.search(address)
    return match.group(1) if match else None


def rent_api_types_for_housing_type(housing_type: str | None) -> list[str]:
    api_type = RENT_TYPE_TO_API_TYPE.get(housing_type or "")
    return [api_type] if api_type else ALL_RENT_API_TYPES


def recent_deal_months(count: int) -> list[str]:
    today = datetime.now().astimezone()
    year = today.year
    month = today.month
    months: list[str] = []
    for _ in range(max(1, count)):
        month -= 1
        if month == 0:
            year -= 1
            month = 12
        months.append(f"{year:04d}{month:02d}")
    return months


def parse_molit_money_to_won(value: Any) -> int:
    if value is None:
        return 0
    text = str(value).replace(",", "").strip()
    if not text:
        return 0
    amount_in_10k_krw = int(float(text))
    return amount_in_10k_krw * 10_000


def normalize_lot_number(value: Any) -> str:
    try:
        return f"{int(value or 0):04d}"
    except (TypeError, ValueError):
        return "0000"


def parse_year(value: Any) -> int | None:
    text = str(value or "")
    return int(text[:4]) if len(text) >= 4 and text[:4].isdigit() else None


def parse_optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def first_value(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value not in {None, ""}:
            return value
    return None


def strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def market_reference_enabled() -> bool:
    return env_bool("MARKET_REFERENCE_ENABLED", True)


def building_register_enabled() -> bool:
    return env_bool("BUILDING_REGISTER_ENABLED", True)


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def public_data_service_key() -> str:
    key = (
        os.getenv("PUBLIC_DATA_SERVICE_KEY")
        or os.getenv("MOLIT_API_SERVICE_KEY")
        or ""
    ).strip()
    return unquote(key)


def building_register_service_key() -> str:
    key = (
        os.getenv("BUILDING_REGISTER_SERVICE_KEY")
        or os.getenv("PUBLIC_DATA_SERVICE_KEY")
        or os.getenv("MOLIT_API_SERVICE_KEY")
        or ""
    ).strip()
    return unquote(key)


def juso_confirm_key() -> str:
    return (
        os.getenv("JUSO_CONFIRM_KEY")
        or os.getenv("JUSO_API_KEY")
        or ""
    ).strip()


def lookback_months() -> int:
    raw_value = os.getenv("MARKET_REFERENCE_LOOKBACK_MONTHS", str(DEFAULT_LOOKBACK_MONTHS))
    try:
        return max(1, min(24, int(raw_value)))
    except ValueError:
        return DEFAULT_LOOKBACK_MONTHS


def market_reference_timeout() -> float:
    raw_value = os.getenv("MARKET_REFERENCE_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    try:
        return max(0.5, float(raw_value))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def rent_api_url(api_type: str) -> str:
    env_names = {
        "apartment": "MOLIT_APT_RENT_API_URL",
        "officetel": "MOLIT_OFFICETEL_RENT_API_URL",
        "row_house": "MOLIT_ROW_HOUSE_RENT_API_URL",
        "detached": "MOLIT_DETACHED_RENT_API_URL",
    }
    env_name = env_names.get(api_type, "")
    return os.getenv(env_name, DEFAULT_RENT_API_URLS[api_type]).strip()


def molit_apt_rent_url() -> str:
    return rent_api_url("apartment")


def building_register_title_url() -> str:
    return os.getenv(
        "BUILDING_REGISTER_TITLE_API_URL",
        DEFAULT_BUILDING_REGISTER_TITLE_URL,
    ).strip()


def juso_search_url() -> str:
    return os.getenv("JUSO_SEARCH_API_URL", DEFAULT_JUSO_SEARCH_URL).strip()
