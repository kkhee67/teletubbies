import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from api import app  # noqa: E402


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)

    def test_health_reports_loaded_cases(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertTrue(response.json()["model_loaded"])
        self.assertEqual(response.json()["case_count"], 938)
        self.assertTrue(response.json()["product_context_loaded"])
        self.assertEqual(response.json()["data_source_count"], 7)
        self.assertEqual(response.json()["mock_property_count"], 5)

    def test_contract_options_expose_two_products_and_six_statuses(self):
        response = self.client.get("/api/contract-options")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            {item["value"] for item in body["guarantee_products"]},
            {"jeonse_return", "rental_deposit"},
        )
        self.assertEqual(len(body["guarantee_statuses"]), 6)
        enrolled = next(
            item
            for item in body["guarantee_statuses"]
            if item["value"] == "enrolled"
        )
        self.assertEqual(enrolled["group"], "protected")

    def test_contract_analysis_matches_three_frontend_screens(self):
        raw_address = "부산광역시 수영구 광안해변로 123 101동 202호"
        response = self.client.post(
            "/api/contract-analysis",
            json={
                "address": raw_address,
                "planned_deposit": 200000000,
                "situation_text": "집주인이 잔금일에 근저당을 말소한다고 했습니다.",
                "guarantee_product_type": "jeonse_return",
                "demo_mode": True,
                "top_k": 3,
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["property"]["planned_deposit"], 200000000)
        self.assertTrue(body["property"]["is_mock"])
        self.assertIn("모의 매물·실제 주소 아님", body["property"]["display_address"])
        self.assertNotIn(raw_address, response.text)
        cards = {card["key"]: card for card in body["property_snapshot"]["cards"]}
        self.assertEqual(cards["housing_type"]["value"], "다세대주택")
        self.assertEqual(cards["reference_value"]["value"], 220000000)
        self.assertEqual(cards["mortgage"]["value"], "exists")
        self.assertEqual(cards["seizure"]["value"], "none")
        self.assertEqual(cards["joint_collateral"]["value"], "unknown")
        self.assertEqual(body["guarantee"]["status"], "unknown")
        self.assertEqual(body["guarantee"]["group"], "check_required")
        self.assertFalse(body["guarantee"]["is_enrolled"])
        self.assertEqual(body["data_usage"]["total_source_count"], 7)
        self.assertEqual(len(body["similar_cases"]), 3)
        self.assertTrue(
            all(
                case["case_product_type"] == "jeonse_return"
                for case in body["similar_cases"]
            )
        )

    def test_contract_analysis_separates_rental_sources(self):
        response = self.client.post(
            "/api/contract-analysis",
            json={
                "address": "부산광역시 수영구 광안동 1",
                "planned_deposit": 150000000,
                "guarantee_product_type": "rental_deposit",
                "demo_mode": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        usage = {
            item["source_id"]: item["applied_to_request"]
            for item in body["data_usage"]["sources"]
        }
        self.assertTrue(usage["rental_guarantee_accidents"])
        self.assertFalse(usage["jeonse_accident_status"])
        self.assertFalse(usage["jeonse_housing_value_ratio"])
        self.assertTrue(
            all(
                case["case_product_type"] == "rental_deposit"
                for case in body["similar_cases"]
            )
        )

    def test_official_facts_can_fill_all_three_screens(self):
        source = {
            "source_type": "official",
            "source_name": "연동 공식자료",
            "reference_date": "2026-07-25",
        }
        response = self.client.post(
            "/api/contract-analysis",
            json={
                "address": "부산광역시 수영구 광안동 1",
                "planned_deposit": 100000000,
                "guarantee_product_type": "jeonse_return",
                "property_facts": {
                    "housing_type": {"value": "아파트", "source": source},
                    "reference_value": {
                        "amount": 300000000,
                        "value_type": "official_reference_value",
                        "source": source,
                    },
                    "mortgage": {"status": "none", "source": source},
                    "seizure": {"status": "none", "source": source},
                    "joint_collateral": {"status": "none", "source": source},
                },
                "guarantee_fact": {"status": "enrolled", "source": source},
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["guarantee"]["group"], "protected")
        self.assertTrue(body["guarantee"]["is_enrolled"])
        self.assertEqual(body["analysis"]["analysis_confidence"], 100)
        self.assertEqual(body["analysis"]["risk_stage"], "기본 확인")
        self.assertEqual(body["analysis"]["required_check_count"], 0)

    def test_contract_analysis_requires_explicit_product_type(self):
        response = self.client.post(
            "/api/contract-analysis",
            json={
                "address": "부산광역시 수영구 광안동 1",
                "planned_deposit": 100000000,
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_mock_property_search_and_lookup_minimize_address(self):
        search = self.client.get("/properties/search", params={"q": "부산광역시"})

        self.assertEqual(search.status_code, 200)
        self.assertEqual(len(search.json()), 5)
        self.assertTrue(all(item["is_mock"] for item in search.json()))
        self.assertNotIn("search_address", search.text)

        lookup = self.client.get("/properties/MOCK-001")
        self.assertEqual(lookup.status_code, 200)
        body = lookup.json()
        self.assertEqual(body["property"]["property_id"], "MOCK-001")
        self.assertIn("실제 주소 아님", body["property"]["display_address"])
        self.assertNotIn("search_address", lookup.text)
        self.assertFalse(body["location_context"]["included_in_risk_score"])

    def test_analyze_endpoint_matches_team_contract(self):
        response = self.client.post(
            "/analyze",
            json={
                "property_id": "MOCK-001",
                "deposit": 200000000,
                "user_text": "집주인이 잔금일에 근저당을 말소한다고 했습니다.",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["property"]["property_id"], "MOCK-001")
        self.assertEqual(body["guarantee"]["group"], "deep_analysis")
        self.assertEqual(body["analysis"]["risk_stage"], "계약 전 재검토")
        risk_codes = {item["code"] for item in body["analysis"]["confirmed_risks"]}
        self.assertIn("MORTGAGE_EXISTS", risk_codes)
        self.assertIn("GUARANTEE_INELIGIBLE", risk_codes)
        self.assertEqual(body["meta"]["ai_search_status"], "ok")

    def test_housing_type_specific_required_checks_are_returned(self):
        dagagu = self.client.post(
            "/analyze",
            json={"property_id": "MOCK-003", "deposit": 180000000},
        ).json()
        officetel = self.client.post(
            "/analyze",
            json={"property_id": "MOCK-004", "deposit": 120000000},
        ).json()

        self.assertIn(
            "SENIOR_TENANT_DEPOSITS_UNKNOWN",
            {item["code"] for item in dagagu["analysis"]["required_checks"]},
        )
        self.assertIn(
            "OFFICETEL_USE_UNKNOWN",
            {item["code"] for item in officetel["analysis"]["required_checks"]},
        )

    def test_simulation_compares_stages_without_claiming_completion(self):
        response = self.client.post(
            "/simulate",
            json={
                "property_id": "MOCK-001",
                "deposit": 200000000,
                "changes": {
                    "mortgage_status": "none",
                    "guarantee_status": "officially_eligible",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["is_simulation"])
        self.assertEqual(body["before"]["analysis"]["risk_stage"], "계약 전 재검토")
        self.assertEqual(body["after"]["guarantee"]["group"], "in_progress")
        self.assertTrue(body["comparison"]["risk_stage"]["changed"])
        self.assertEqual(body["after"]["analysis"]["analysis_confidence"], 0)
        self.assertIn("실제 완료로 확인된 것이 아니", body["notice"])

    def test_missing_mock_property_returns_404(self):
        response = self.client.post(
            "/analyze",
            json={"property_id": "MOCK-999", "deposit": 100000000},
        )

        self.assertEqual(response.status_code, 404)

    def test_ai_failure_keeps_analysis_and_returns_empty_cases(self):
        original_engine = self.client.app.state.search_engine

        class FailingSearchEngine:
            def search(self, *args, **kwargs):
                raise RuntimeError("temporary search failure")

        self.client.app.state.search_engine = FailingSearchEngine()
        try:
            response = self.client.post(
                "/analyze",
                json={"property_id": "MOCK-001", "deposit": 200000000},
            )
        finally:
            self.client.app.state.search_engine = original_engine

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["similar_cases"], [])
        self.assertEqual(body["meta"]["ai_search_status"], "unavailable")
        self.assertGreater(body["analysis"]["confirmed_risk_count"], 0)

    def test_similar_cases_response_is_public_and_explained(self):
        response = self.client.post(
            "/api/similar-cases",
            json={
                "property_data": {
                    "guarantee_product_type": "jeonse_return",
                    "housing_type": "다세대주택",
                    "deposit": 180000000,
                    "senior_rights": "근저당",
                    "guarantee_status": "unknown",
                },
                "analysis": {
                    "confirmed_risks": [
                        {"code": "MORTGAGE_EXISTS", "title": "선순위 근저당 확인"}
                    ],
                    "required_checks": [
                        {"code": "GUARANTEE_UNKNOWN", "title": "반환보증 확인 필요"}
                    ],
                },
                "user_text": "잔금일에 근저당을 말소한다고 했습니다.",
                "top_k": 3,
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["meta"]["result_count"], 3)
        self.assertFalse(body["meta"]["is_accident_probability"])
        self.assertEqual(body["meta"]["selected_product_type"], "jeonse_return")
        self.assertTrue(body["meta"]["product_separation_applied"])
        self.assertEqual(body["meta"]["data_source_count"], 7)
        self.assertEqual(body["product_context"]["source_count"], 5)
        self.assertEqual(len(body["similar_cases"]), 3)
        similarities = [case["similarity"] for case in body["similar_cases"]]
        self.assertEqual(similarities, sorted(similarities, reverse=True))
        first = body["similar_cases"][0]
        self.assertEqual(first["similarity_label"], "상담사례 유사도")
        self.assertEqual(len(first["actions"]), 2)
        self.assertTrue(first["safety_passed"])
        self.assertNotIn("source_summary", first)
        self.assertIn(first["case_product_type"], {"jeonse_return", "unknown"})

    def test_user_text_is_optional(self):
        response = self.client.post(
            "/api/similar-cases",
            json={
                "property_data": {
                    "guarantee_product_type": "rental_deposit",
                    "housing_type": "아파트",
                    "deposit": 250000000,
                    "guarantee_status": "enrolled",
                },
                "analysis": {},
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["similar_cases"]), 3)

    def test_product_context_sources_are_separated(self):
        def request(product_type):
            return self.client.post(
                "/api/similar-cases",
                json={
                    "property_data": {
                        "guarantee_product_type": product_type,
                        "housing_type": "다세대주택",
                    }
                },
            ).json()

        jeonse = request("jeonse_return")
        rental = request("rental_deposit")
        jeonse_sources = {
            source["source_id"] for source in jeonse["product_context"]["sources"]
        }
        rental_sources = {
            source["source_id"] for source in rental["product_context"]["sources"]
        }

        self.assertIn("jeonse_accident_status", jeonse_sources)
        self.assertNotIn("rental_guarantee_accidents", jeonse_sources)
        self.assertIn("rental_guarantee_accidents", rental_sources)
        self.assertNotIn("jeonse_accident_status", rental_sources)
        self.assertTrue(
            all(
                case["case_product_type"] == "jeonse_return"
                for case in jeonse["similar_cases"]
            )
        )
        self.assertTrue(
            all(
                case["case_product_type"] == "rental_deposit"
                for case in rental["similar_cases"]
            )
        )

    def test_unsupported_product_type_is_rejected(self):
        response = self.client.post(
            "/api/similar-cases",
            json={
                "property_data": {
                    "guarantee_product_type": "jeonse_loan",
                    "housing_type": "아파트",
                }
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_invalid_top_k_is_rejected(self):
        response = self.client.post(
            "/api/similar-cases",
            json={"property_data": {"housing_type": "아파트"}, "top_k": 0},
        )

        self.assertEqual(response.status_code, 422)

    def test_empty_search_context_is_rejected(self):
        response = self.client.post(
            "/api/similar-cases",
            json={"property_data": {}, "analysis": {}},
        )

        self.assertEqual(response.status_code, 422)

    def test_cors_preflight_allows_local_frontend(self):
        response = self.client.options(
            "/api/similar-cases",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )


if __name__ == "__main__":
    unittest.main()
