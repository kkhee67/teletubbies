from main import app
from fastapi.testclient import TestClient
from services import ai_client


def api_call(method: str, path: str, **kwargs):
    with TestClient(app) as client:
        return getattr(client, method)(path, **kwargs)


def test_health():
    response = api_call("get", "/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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


def test_analyze_contract():
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
    assert body["ai_api_status"] in {"ok", "fallback"}


def test_analyze_calls_ai_api_with_product_type(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
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
    assert body["ai_api_status"] == "ok"
    assert body["similar_cases"][0]["case_id"] == "CASE-AI-001"
    assert body["similar_cases"][0]["similarity"] == 87.6
    assert body["similar_cases"][0]["source"] == "AI API 유사 상담사례"
    assert body["easy_explanation"]["plain_explanation"] == "AI API에서 받은 쉬운 설명입니다."


def test_analyze_falls_back_when_ai_api_fails(monkeypatch):
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
    assert body["ai_api_status"] == "fallback"
    assert body["similar_cases"]
    assert body["similar_cases"][0]["source"] == "아이엔 비식별 상담데이터 패턴 기반 모의사례"


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


def test_simulate_contract():
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
