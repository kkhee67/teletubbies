import json
from datetime import datetime

from main import app, get_cors_allow_origins
from fastapi.testclient import TestClient
from repositories import property_repository
from services import ai_client, analysis_service


def setup_function():
    property_repository.clear_cache()


def teardown_function():
    property_repository.clear_cache()


def api_call(method: str, path: str, **kwargs):
    with TestClient(app) as client:
        return getattr(client, method)(path, **kwargs)


def test_health():
    response = api_call("get", "/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_cors_allows_deployed_frontend_origin():
    response = api_call(
        "options",
        "/health",
        headers={
            "Origin": "https://dive-2026-teletubbies.hgumax.chatgpt.site",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://dive-2026-teletubbies.hgumax.chatgpt.site"
    )


def test_cors_origins_can_be_configured_with_env(monkeypatch):
    monkeypatch.setenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000, https://example.com ",
    )
    assert get_cors_allow_origins() == [
        "http://localhost:3000",
        "https://example.com",
    ]


def test_property_repository_uses_json_store_and_refreshes_on_version(tmp_path, monkeypatch):
    data_path = tmp_path / "properties.json"
    base_row = {
        "property_id": "PX01",
        "address_display": "부산광역시 테스트구 버전로 1",
        "district": "테스트구",
        "legal_dong": "테스트동",
        "housing_type": "apartment",
        "reference_value": 100000000,
        "value_source": "test store",
        "mortgage_status": "none",
        "seizure_status": "none",
        "joint_collateral": "none",
        "guarantee_status": "enrolled",
        "guarantee_product_type": "jeonse_return",
    }
    data_path.write_text(json.dumps([base_row], ensure_ascii=False), encoding="utf-8")

    monkeypatch.setenv("PROPERTY_DATA_PATH", str(data_path))
    monkeypatch.setenv("PROPERTY_STORE_TTL_SECONDS", "3600")

    assert property_repository.get("PX01")["address_display"].endswith("버전로 1")

    changed_row = {**base_row, "address_display": "부산광역시 테스트구 버전로 22"}
    data_path.write_text(json.dumps([changed_row], ensure_ascii=False), encoding="utf-8")

    assert property_repository.get("PX01")["address_display"].endswith("버전로 22")


def test_search_properties():
    response = api_call("get", "/properties/search", params={"q": "수영구"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    assert items[0]["property_id"] == "P001"


def test_get_property():
    response = api_call("get", "/properties/P001")
    assert response.status_code == 200
    assert response.json()["address_display"].startswith("부산광역시")


def test_invalid_deposit():
    response = api_call(
        "post",
        "/analyze",
        json={
            "property_id": "P001",
            "planned_deposit": 0,
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_property_not_found_error_shape():
    response = api_call(
        "post",
        "/analyze",
        json={"property_id": "NOPE", "planned_deposit": 100000000},
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": "매물을 찾을 수 없습니다.",
        "code": "PROPERTY_NOT_FOUND",
        "extra": {},
    }


def test_analyze_contract(monkeypatch):
    monkeypatch.setenv("AI_API_ENABLED", "false")

    response = api_call(
        "post",
        "/analyze",
        json={
            "property_id": "P001",
            "address_query": "부산광역시 수영구 안심로 24",
            "planned_deposit": 200000000,
            "monthly_rent": 0,
            "user_note": "잔금일에 근저당을 말소한다고 들었습니다.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["risk_score"] >= 0
    assert body["property_summary"]["deposit_ratio"] == 90.9
    assert "signals" in body
    assert "checklist" in body
    assert body["guarantee"]["status"] == "unknown"
    assert body["guarantee"]["group"] == "check_required"
    assert body["ai_api_status"] == "disabled"
    assert body["similar_cases"] == []
    generated_at = datetime.fromisoformat(body["generated_at"])
    assert generated_at.tzinfo is not None


def test_analyze_address_only_request(monkeypatch):
    monkeypatch.setenv("AI_API_ENABLED", "false")

    response = api_call(
        "post",
        "/analyze",
        json={
            "address_query": "서울특별시 강남구 테헤란로 152",
            "planned_deposit": 200000000,
            "user_note": "등기부 확인 전입니다.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    summary = body["property_summary"]
    assert summary["property_id"].startswith("ADDR-")
    assert summary["address_display"] == "서울특별시 강남구 테헤란로 152"
    assert summary["district"] == "강남구"
    assert summary["housing_type"] == "unknown"
    assert summary["mortgage_status"] == "unknown"
    assert summary["seizure_status"] == "unknown"
    assert summary["joint_collateral"] == "unknown"
    assert summary["guarantee_status"] == "unknown"
    assert body["ai_api_status"] == "disabled"
    assert {
        "MORTGAGE_UNKNOWN",
        "SEIZURE_UNKNOWN",
        "JOINT_COLLATERAL_UNKNOWN",
        "GUARANTEE_UNKNOWN",
    }.issubset({signal["code"] for signal in body["signals"]})


def test_address_only_uses_market_reference_for_deposit_ratio(monkeypatch):
    monkeypatch.setenv("AI_API_ENABLED", "false")

    def fake_reference(address, housing_type=None, address_meta=None):
        return {
            "reference_value": 400000000,
            "source_name": "MOLIT apartment rent actual transaction API",
            "source_type": "public_api",
            "note": "test market reference",
            "lawd_cd": "11680",
            "deal_months": ["202606"],
            "sample_count": 3,
        }

    monkeypatch.setattr(
        analysis_service.market_reference,
        "estimate_reference_value",
        fake_reference,
    )

    low = api_call(
        "post",
        "/analyze",
        json={
            "address_query": "Seoul Gangnam-gu Teheran-ro 152",
            "planned_deposit": 200000000,
        },
    )
    high = api_call(
        "post",
        "/analyze",
        json={
            "address_query": "Seoul Gangnam-gu Teheran-ro 152",
            "planned_deposit": 380000000,
        },
    )

    assert low.status_code == 200
    assert high.status_code == 200
    low_body = low.json()
    high_body = high.json()
    assert low_body["property_summary"]["reference_value"] == 400000000
    assert high_body["property_summary"]["reference_value"] == 400000000
    assert low_body["property_summary"]["deposit_ratio"] == 50.0
    assert high_body["property_summary"]["deposit_ratio"] == 95.0
    assert high_body["risk_score"] > low_body["risk_score"]
    assert (
        high_body["property_summary"]["value_source"]
        == "MOLIT apartment rent actual transaction API"
    )
    assert high_body["market_context"][0]["included_in_risk_score"] is True


def test_address_only_without_market_reference_uses_provisional_reference(monkeypatch):
    monkeypatch.setenv("AI_API_ENABLED", "false")
    monkeypatch.setenv("MARKET_REFERENCE_ENABLED", "false")

    def fake_search(query):
        return [
            {"reference_value": 300000000},
            {"reference_value": 500000000},
        ]

    monkeypatch.setattr(analysis_service.property_repository, "search", fake_search)

    low = api_call(
        "post",
        "/analyze",
        json={
            "address_query": "Seoul Gangnam-gu Teheran-ro 152",
            "planned_deposit": 200000000,
        },
    )
    high = api_call(
        "post",
        "/analyze",
        json={
            "address_query": "Seoul Gangnam-gu Teheran-ro 152",
            "planned_deposit": 380000000,
        },
    )

    assert low.status_code == 200
    assert high.status_code == 200
    low_body = low.json()
    high_body = high.json()
    assert low_body["property_summary"]["reference_value"] == 400000000
    assert high_body["property_summary"]["reference_value"] == 400000000
    assert low_body["property_summary"]["deposit_ratio"] == 50.0
    assert high_body["property_summary"]["deposit_ratio"] == 95.0
    assert high_body["risk_score"] > low_body["risk_score"]
    assert (
        high_body["property_summary"]["value_source"]
        == "Address-only provisional datastore median"
    )


def test_analyze_calls_ai_api_with_product_type(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "ok",
                "similar_cases": [
                    {
                        "case_id": "CASE-AI-001",
                        "case_product_type": "rental_deposit",
                        "case_product_label": "임대보증금보증",
                        "similarity": 0.876,
                        "similarity_label": "상담사례 유사도",
                        "matched_factors": ["임대보증금보증", "다가구주택"],
                        "confirmed_risk_tags": ["근저당"],
                        "required_check_tags": ["반환보증 확인"],
                        "dispute_type": "보증금미반환",
                        "progress_stage": "상담·검토",
                        "easy_explanation": "AI API에서 받은 쉬운 설명입니다.",
                        "actions": ["보증기관 확인", "최신 등기부 확인"],
                        "explanation_source": "template",
                        "safety_passed": True,
                        "source": {
                            "source_type": "provided_synthetic_consultations",
                            "source_name": "Synthetic consultation cases",
                            "is_synthetic": True,
                            "reference_date": "2026-07-25",
                        },
                        "disclaimer": "참고사례입니다.",
                    }
                ],
                "meta": {"result_count": 1},
            }

    def fake_post(url, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(ai_client.httpx, "post", fake_post)

    response = api_call(
        "post",
        "/analyze",
        json={
            "property_id": "P004",
            "planned_deposit": 150000000,
            "guarantee_product_type": "rental_deposit",
            "user_note": "선순위 권리가 걱정됩니다.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert calls[0]["url"].endswith("/api/similar-cases")
    assert calls[0]["json"]["property_data"]["guarantee_product_type"] == "rental_deposit"
    assert calls[0]["json"]["property_data"]["housing_type"] == "다가구주택"
    assert calls[0]["json"]["top_k"] == 3
    assert calls[0]["timeout"] == 3.0
    assert body["ai_api_status"] == "ok"
    assert body["similar_cases"][0]["case_id"] == "CASE-AI-001"
    assert body["similar_cases"][0]["similarity"] == 87.6
    assert body["similar_cases"][0]["source"] == {
        "source_type": "provided_synthetic_consultations",
        "source_name": "Synthetic consultation cases",
        "is_synthetic": True,
        "reference_date": "2026-07-25",
    }
    assert body["similar_cases"][0]["source_type"] == "provided_synthetic_consultations"
    assert body["similar_cases"][0]["source_name"] == "Synthetic consultation cases"
    assert body["easy_explanation"]["plain_explanation"] == "AI API에서 받은 쉬운 설명입니다."
    assert "SEIZURE_UNKNOWN" in {signal["code"] for signal in body["signals"]}


def test_analyze_skips_ai_api_for_unknown_product_type(monkeypatch):
    calls = []

    def fail_if_called(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("unknown guarantee_product_type must not call AI API")

    monkeypatch.setenv("AI_API_ENABLED", "true")
    monkeypatch.setenv("LOCAL_SIMILAR_CASES_ENABLED", "false")
    monkeypatch.setattr(ai_client.httpx, "post", fail_if_called)

    response = api_call(
        "post",
        "/analyze",
        json={
            "property_id": "P001",
            "planned_deposit": 200000000,
            "guarantee_product_type": "unknown",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ai_api_status"] == "unsupported_product_type"
    assert "not supported" in body["ai_api_message"]
    assert body["similar_cases"] == []
    assert body["easy_explanation"] is None
    assert calls == []


def test_analyze_preserves_ai_fallback_status(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "fallback",
                "similar_cases": [],
                "message": "AI API used fallback explanation.",
                "meta": {"result_count": 0},
            }

    def fake_post(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setenv("AI_API_ENABLED", "true")
    monkeypatch.setenv("LOCAL_SIMILAR_CASES_ENABLED", "false")
    monkeypatch.setattr(ai_client.httpx, "post", fake_post)

    response = api_call(
        "post",
        "/analyze",
        json={"property_id": "P004", "planned_deposit": 150000000},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ai_api_status"] == "fallback"
    assert body["ai_api_message"] == "AI API used fallback explanation."
    assert body["similar_cases"] == []


def test_analyze_returns_empty_cases_when_ai_api_fails(monkeypatch):
    def fail_post(*args, **kwargs):
        raise ai_client.httpx.ConnectError("AI server unavailable")

    monkeypatch.setattr(ai_client.httpx, "post", fail_post)

    response = api_call(
        "post",
        "/analyze",
        json={"property_id": "P001", "planned_deposit": 200000000},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ai_api_status"] == "unavailable"
    assert body["ai_api_message"] == "AI API is unavailable."
    assert body["similar_cases"] == []
    assert body["easy_explanation"] is None


def test_guarantee_six_status_mapping():
    expectations = {
        "estimated_eligible": "check_required",
        "officially_eligible": "in_progress",
        "applied": "in_progress",
        "enrolled": "protected",
        "ineligible": "deep_analysis",
        "unknown": "check_required",
    }

    for status, group in expectations.items():
        response = api_call(
            "post",
            "/analyze",
            json={
                "property_id": "P001",
                "planned_deposit": 200000000,
                "user_corrections": {"guarantee_status": status},
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["property_summary"]["guarantee_status"] == status
        assert body["guarantee"]["status"] == status
        assert body["guarantee"]["group"] == group
        assert body["guarantee_branch"] == group
        if status == "applied":
            assert body["guarantee"] == {
                "status": "applied",
                "group": "in_progress",
                "display_text": "가입 신청 중",
                "message": "신청은 접수됐지만 보증서 발급 확인이 필요합니다.",
                "next_actions": ["보증서 발급 여부 확인"],
            }


def test_simulate_contract(monkeypatch):
    calls = []

    def fail_if_called(**kwargs):
        calls.append(kwargs)
        raise AssertionError("simulate must not call AI search")

    monkeypatch.setattr(analysis_service, "fetch_similar_cases", fail_if_called)

    response = api_call(
        "post",
        "/simulate",
        json={
            "current": {
                "property_id": "P001",
                "planned_deposit": 200000000,
            },
            "changed": {
                "property_id": "P001",
                "planned_deposit": 170000000,
                "user_corrections": {
                    "mortgage_status": "removed",
                    "joint_collateral": "none",
                    "guarantee_status": "enrolled",
                },
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["changed"]["risk_score"] < body["current"]["risk_score"]
    assert calls == []
    generated_at = datetime.fromisoformat(body["generated_at"])
    assert generated_at.tzinfo is not None
