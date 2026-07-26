from services import market_reference


class FakeResponse:
    def __init__(self, json_body=None, text=""):
        self._json_body = json_body
        self.text = text

    def raise_for_status(self):
        return None

    def json(self):
        if self._json_body is None:
            raise ValueError("No JSON body")
        return self._json_body


def test_parse_deposits_from_xml():
    xml = """
    <response>
      <body>
        <items>
          <item><deposit>20,000</deposit></item>
          <item><depositAmount>35,000</depositAmount></item>
          <item><deposit>0</deposit></item>
        </items>
      </body>
    </response>
    """

    assert market_reference.parse_deposits(xml) == [200000000, 350000000]


def test_market_reference_can_be_disabled(monkeypatch):
    monkeypatch.setenv("MARKET_REFERENCE_ENABLED", "false")

    assert market_reference.estimate_reference_value("Seoul Gangnam-gu") is None


def test_public_data_service_key_accepts_url_encoded_key(monkeypatch):
    monkeypatch.setenv("PUBLIC_DATA_SERVICE_KEY", "abc%2Bdef%3D")

    assert market_reference.public_data_service_key() == "abc+def="


def test_rent_api_types_follow_housing_type():
    assert market_reference.rent_api_types_for_housing_type("apartment") == [
        "apartment"
    ]
    assert market_reference.rent_api_types_for_housing_type("officetel") == [
        "officetel"
    ]
    assert market_reference.rent_api_types_for_housing_type("multi_unit") == [
        "row_house"
    ]
    assert market_reference.rent_api_types_for_housing_type("multi_household") == [
        "detached"
    ]
    assert market_reference.rent_api_types_for_housing_type("unknown") == [
        "apartment",
        "officetel",
        "row_house",
        "detached",
    ]


def test_lookup_official_property_data_uses_address_building_and_rent(monkeypatch):
    monkeypatch.setenv("JUSO_CONFIRM_KEY", "juso-key")
    monkeypatch.setenv("PUBLIC_DATA_SERVICE_KEY", "public-key")
    monkeypatch.setenv("MARKET_REFERENCE_LOOKBACK_MONTHS", "1")

    calls = []

    def fake_get(url, params, timeout):
        calls.append({"url": url, "params": params, "timeout": timeout})
        if "addrLinkApi" in url:
            return FakeResponse(
                json_body={
                    "results": {
                        "juso": [
                            {
                                "roadAddr": "\uc11c\uc6b8\ud2b9\ubcc4\uc2dc \uac15\ub0a8\uad6c \ud14c\ud5e4\ub780\ub85c 152",
                                "jibunAddr": "",
                                "admCd": "1168010100",
                                "sggNm": "\uac15\ub0a8\uad6c",
                                "emdNm": "\uc5ed\uc0bc\ub3d9",
                                "rn": "\ud14c\ud5e4\ub780\ub85c",
                                "bdMgtSn": "1168010100100000000000001",
                                "bdKdcd": "1",
                                "mtYn": "0",
                                "lnbrMnnm": "123",
                                "lnbrSlno": "0",
                            }
                        ]
                    }
                }
            )
        if "BldRgstHubService" in url:
            assert params["sigunguCd"] == "11680"
            assert params["bjdongCd"] == "10100"
            assert params["bun"] == "0123"
            assert params["ji"] == "0000"
            return FakeResponse(
                json_body={
                    "response": {
                        "body": {
                            "items": {
                                "item": {
                                    "mainPurpsCdNm": "\uc544\ud30c\ud2b8",
                                    "useAprDay": "20200101",
                                    "hhldCnt": "20",
                                }
                            }
                        }
                    }
                }
            )
        if "RTMSDataSvcAptRent" in url:
            return FakeResponse(
                text="""
                <response>
                  <body><items><item><deposit>40,000</deposit></item></items></body>
                </response>
                """
            )
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(market_reference.httpx, "get", fake_get)

    result = market_reference.lookup_official_property_data(
        "\uc11c\uc6b8\ud2b9\ubcc4\uc2dc \uac15\ub0a8\uad6c \ud14c\ud5e4\ub780\ub85c 152"
    )

    assert result["address"]["lawd_cd"] == "11680"
    assert result["address"]["district"] == "\uac15\ub0a8\uad6c"
    assert result["building"]["housing_type"] == "apartment"
    assert result["building"]["built_year"] == 2020
    assert result["housing_type"] == "apartment"
    assert result["market_reference"]["reference_value"] == 400000000
    assert result["market_reference"]["api_types"] == ["apartment"]
    assert any("RTMSDataSvcAptRent" in call["url"] for call in calls)
