from main import app
from fastapi.testclient import TestClient


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
