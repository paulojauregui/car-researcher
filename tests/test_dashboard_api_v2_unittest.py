"""
Milestone M04 Unit Tests: HTTP/ASGI Router, v2 Market Intelligence APIs & Static Serving.

Pre-conditions:
    - Standard library unittest execution with zero external dependencies.
    - All network boundaries and GovAPI client calls are strictly mocked.
    - DashboardRepository and DashboardApp modules are present.

Post-conditions:
    - Validates 100% of Milestone M04 acceptance criteria for DashboardApp and HTTP routing.
    - Confirms traversal safety for static asset delivery.
    - Confirms backward compatibility for v1 HTMX endpoints and forward compatibility for v2 JSON APIs.
    - Strictly zero emojis and zero hardcoded Temporal UI hosts across all assertions.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List
import unittest
from unittest.mock import AsyncMock, patch

from src.dashboard.app import (
    STATIC_DIR,
    DashboardApp,
    _handle_client,
    _parse_float,
    _parse_int,
    _parse_json_body,
    _read_request_headers,
    _status_text,
    _wants_html,
    _wants_json,
)
from src.dashboard.queries import DashboardRepository


def _sample_deals() -> List[Dict[str, Any]]:
    """
    Construct a deterministic 3-vehicle fixture dataset for offline API testing.

    Pre-conditions:
        - None.

    Post-conditions:
        - Returns a list of 3 vehicle listing dictionaries with price history snapshots.
    """
    return [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "vin": "W1KCG2DB6PA043095",
            "platform": "cars_com",
            "platform_id": "cc-101",
            "url": "https://www.cars.com/vehicledetail/cc-101/",
            "title": "2023 Mercedes-Benz EQS 450+ Base",
            "price": 39988,
            "mileage": 16479,
            "exterior_color": "Obsidian Black",
            "interior_color": "Black",
            "trim_detail": "EQS 450+",
            "seller_name": "Mercedes-Benz of Stevens Creek",
            "location_city": "San Jose",
            "distance_miles": 41.2,
            "title_status": "clean",
            "accident_count": 0,
            "owner_count": 1,
            "photos": ["https://images.cars.com/phototab/1.jpg"],
            "raw_data": {"make": "Mercedes-Benz", "model": "EQS", "year": 2023},
            "market_value": 52778,
            "price_delta": -12790,
            "deal_score": 87.6,
            "recommendation": "Excellent Deal - Strong Buy",
            "score_breakdown": {
                "price_score": 98.4,
                "history_score": 100.0,
                "leverage_score": 50.0,
                "proximity_score": 79.0,
                "estimated_msrp": 105550,
            },
            "price_change": -1500,
            "days_on_market": 12,
            "snapshot_count": 3,
            "price_history": [
                {
                    "time": "2026-10-20 04:00:00",
                    "price": 39988,
                    "mileage": 16479,
                    "price_change": -1500,
                    "days_on_market": 12,
                },
                {
                    "time": "2026-10-18 04:00:00",
                    "price": 41488,
                    "mileage": 16479,
                    "price_change": 0,
                    "days_on_market": 10,
                },
            ],
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "vin": "W1KCG4EB5PA031214",
            "platform": "cars_com",
            "platform_id": "cc-102",
            "url": "https://www.cars.com/vehicledetail/cc-102/",
            "title": "2023 Mercedes-Benz EQS 580 4MATIC",
            "price": 50995,
            "mileage": 19576,
            "exterior_color": "Polar White",
            "interior_color": "Macchiato Beige",
            "trim_detail": "EQS 580 4MATIC",
            "seller_name": "Autobahn Motors",
            "location_city": "Belmont",
            "distance_miles": 19.6,
            "title_status": "clean",
            "accident_count": 0,
            "owner_count": 1,
            "photos": [],
            "raw_data": {"make": "Mercedes-Benz", "model": "EQS", "year": 2023},
            "market_value": 63522,
            "price_delta": -12527,
            "deal_score": 89.2,
            "recommendation": "Excellent Deal - Strong Buy",
            "score_breakdown": {
                "price_score": 94.6,
                "history_score": 100.0,
                "leverage_score": 50.0,
                "proximity_score": 100.0,
                "estimated_msrp": 127100,
            },
            "price_change": 0,
            "days_on_market": 5,
            "snapshot_count": 2,
        },
        {
            "id": "33333333-3333-3333-3333-333333333333",
            "vin": "KNDC4DLC6P5123456",
            "platform": "cargurus",
            "platform_id": "cg-201",
            "url": "https://www.cargurus.com/Cars/cg-201",
            "title": "2023 Kia EV6 Wind AWD",
            "price": 29500,
            "mileage": 22000,
            "exterior_color": "Yacht Blue",
            "interior_color": "Black",
            "trim_detail": "Wind AWD",
            "seller_name": "Oakland Kia",
            "location_city": "Oakland",
            "distance_miles": 10.5,
            "title_status": "clean",
            "accident_count": 0,
            "owner_count": 1,
            "photos": [],
            "raw_data": {"make": "Kia", "model": "EV6", "year": 2023},
            "market_value": 31000,
            "price_delta": -1500,
            "deal_score": 76.5,
            "recommendation": "Good Value - Worth Investigating",
            "score_breakdown": {
                "price_score": 69.3,
                "history_score": 100.0,
                "leverage_score": 50.0,
                "proximity_score": 100.0,
                "estimated_msrp": 52600,
            },
            "price_change": 0,
            "days_on_market": 18,
            "snapshot_count": 1,
        },
    ]


class MockStreamWriter:
    """
    Mock asyncio StreamWriter capturing transmitted bytes.

    Pre-conditions:
        - None.

    Post-conditions:
        - Records written bytes into an in-memory bytearray.
    """

    def __init__(self) -> None:
        """
        Initialize the stream writer buffer.

        Pre-conditions:
            - None.

        Post-conditions:
            - Buffer is empty and closed is False.
        """
        self.buffer = bytearray()
        self.is_closed = False

    def write(self, data: bytes) -> None:
        """
        Append bytes to the stream buffer.

        Pre-conditions:
            - data is bytes.

        Post-conditions:
            - buffer is extended.
        """
        self.buffer.extend(data)

    async def drain(self) -> None:
        """
        Simulate async drain.

        Pre-conditions:
            - None.

        Post-conditions:
            - No-op.
        """
        pass

    def close(self) -> None:
        """
        Mark the writer as closed.

        Pre-conditions:
            - None.

        Post-conditions:
            - is_closed is set to True.
        """
        self.is_closed = True

    async def wait_closed(self) -> None:
        """
        Simulate waiting for closure.

        Pre-conditions:
            - None.

        Post-conditions:
            - No-op.
        """
        pass


class TestDashboardAPIV2Unit(unittest.IsolatedAsyncioTestCase):
    """
    Complete unit test suite for Milestone M04 HTTP router and v2 APIs.

    Pre-conditions:
        - In-memory repository seeded with deterministic sample deals.

    Post-conditions:
        - Verifies status codes, headers, and bodies for all v1 and v2 routes.
    """

    def setUp(self) -> None:
        """
        Set up the isolated dashboard application instance before each test.

        Pre-conditions:
            - None.

        Post-conditions:
            - self.repo and self.app are configured with deterministic deals.
        """
        self.repo = DashboardRepository(fallback_deals=_sample_deals())
        self.app = DashboardApp(repo=self.repo)

    # 1. Path-Safe Static File Serving
    async def test_static_file_serving_and_traversal_guards(self) -> None:
        """
        Verify static file serving, MIME mapping, cache headers, and directory traversal rejection.

        Pre-conditions:
            - STATIC_DIR exists and contains standard assets.

        Post-conditions:
            - Valid static files return 200 with Cache-Control: no-cache.
            - Traversal attacks return 403 Forbidden.
            - Missing files return 404 Not Found.
            - Non-GET/HEAD methods return 404.
        """
        # Ensure a known asset exists in STATIC_DIR
        self.assertTrue(STATIC_DIR.exists() and STATIC_DIR.is_dir())
        css_file = STATIC_DIR / "components.css"
        self.assertTrue(css_file.is_file())

        # Valid GET
        status, headers, body = await self.app.handle_request("GET", "/static/components.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/css; charset=utf-8")
        self.assertEqual(headers["Cache-Control"], "no-cache")
        self.assertGreater(len(body), 0)

        # Valid HEAD
        status_head, headers_head, body_head = await self.app.handle_request("HEAD", "/static/components.css")
        self.assertEqual(status_head, 200)
        self.assertEqual(headers_head["Content-Type"], "text/css; charset=utf-8")
        self.assertEqual(headers_head["Cache-Control"], "no-cache")
        self.assertEqual(body_head, b"")

        # Missing static file
        status_missing, _, _ = await self.app.handle_request("GET", "/static/nonexistent_file.css")
        self.assertEqual(status_missing, 404)

        # Directory traversal attempts
        status_trav1, _, _ = await self.app.handle_request("GET", "/static/../app.py")
        self.assertEqual(status_trav1, 403)

        status_trav2, _, _ = await self.app.handle_request("GET", "/static/%2e%2e/app.py")
        self.assertEqual(status_trav2, 403)

        status_trav3, _, _ = await self.app.handle_request("GET", "/static/nested/../../secret.txt")
        self.assertEqual(status_trav3, 403)

        # Null byte injection
        status_null, _, _ = await self.app.handle_request("GET", "/static/components.css\x00.js")
        self.assertEqual(status_null, 403)

        # Leading slash / empty target
        status_empty, _, _ = await self.app.handle_request("GET", "/static/")
        self.assertEqual(status_empty, 403)

        status_root, _, _ = await self.app.handle_request("GET", "/static")
        self.assertEqual(status_root, 403)

        # POST to static file should be rejected (only GET and HEAD permitted)
        status_post, _, _ = await self.app.handle_request("POST", "/static/components.css")
        self.assertEqual(status_post, 404)

    # 2. SSR Root Page & HEAD Support
    async def test_root_ssr_page_and_head(self) -> None:
        """
        Verify root SSR dashboard HTML delivery and HEAD response behavior.

        Pre-conditions:
            - Valid deals available in repository.

        Post-conditions:
            - GET / returns 200 HTML with rendered page.
            - HEAD / returns 200 HTML with zero body bytes.
        """
        status_get, headers_get, body_get = await self.app.handle_request("GET", "/")
        self.assertEqual(status_get, 200)
        self.assertIn("text/html", headers_get["Content-Type"])
        html_text = body_get.decode("utf-8")
        self.assertIn("Bay Area EV Deal Surveillance", html_text)

        status_head, headers_head, body_head = await self.app.handle_request("HEAD", "/")
        self.assertEqual(status_head, 200)
        self.assertIn("text/html", headers_head["Content-Type"])
        self.assertEqual(body_head, b"")

    # 3. HTMX Partials
    @patch("src.dashboard.queries.GovAPIClient")
    async def test_htmx_partials(self, mock_gov_cls: Any) -> None:
        """
        Verify HTMX partial endpoints for deals, KPIs, listing history modal, and model profile.

        Pre-conditions:
            - Mocked GovAPIClient to prevent external network calls.

        Post-conditions:
            - All partial endpoints return 200 text/html with required UI components.
        """
        mock_gov = mock_gov_cls.return_value
        mock_gov.get_recalls = AsyncMock(return_value=[])
        mock_gov.get_complaints = AsyncMock(return_value=[])
        mock_gov.get_epa_fuel_economy = AsyncMock(return_value=[])

        # GET /partials/deals
        status, headers, body = await self.app.handle_request("GET", "/partials/deals")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn("2023 Mercedes-Benz EQS 450+ Base", body.decode("utf-8"))

        # GET /partials/kpis
        status_kpi, headers_kpi, body_kpi = await self.app.handle_request("GET", "/partials/kpis")
        self.assertEqual(status_kpi, 200)
        self.assertIn("text/html", headers_kpi["Content-Type"])
        self.assertIn("active bay area inventory", body_kpi.decode("utf-8").lower())

        # GET /partials/listing/{id}/history
        target_id = "11111111-1111-1111-1111-111111111111"
        status_hist, _, body_hist = await self.app.handle_request("GET", f"/partials/listing/{target_id}/history")
        self.assertEqual(status_hist, 200)
        self.assertIn("TimescaleDB Price Snapshots", body_hist.decode("utf-8"))

        # GET /partials/model-profile
        status_prof, _, body_prof = await self.app.handle_request(
            "GET",
            "/partials/model-profile",
            query_params={"make": "Mercedes-Benz", "model": "EQS", "year": "2023"},
        )
        self.assertEqual(status_prof, 200)
        self.assertIn("Mercedes-Benz", body_prof.decode("utf-8"))

    # 4. Bookmark & Dismiss: v1 HTML and JSON Content Negotiation
    async def test_bookmark_and_dismiss_content_negotiation(self) -> None:
        """
        Verify legacy bookmark/dismiss endpoints handle HTML vs JSON responses properly.

        Pre-conditions:
            - Valid listing present in repo.

        Post-conditions:
            - HTML requests preserve v1 deals section HTML contract.
            - JSON requests return structured payload {id, flag, value, kpis}.
            - Missing listing in JSON mode returns 404.
        """
        target_id = "11111111-1111-1111-1111-111111111111"

        # HTML mode: legacy contract returns HTML fragment
        status_html, headers_html, body_html = await self.app.handle_request(
            "POST", f"/api/listing/{target_id}/bookmark"
        )
        self.assertEqual(status_html, 200)
        self.assertIn("text/html", headers_html["Content-Type"])
        self.assertIn("2023 Mercedes-Benz EQS 450+ Base", body_html.decode("utf-8"))

        # JSON mode via Accept header
        status_json, headers_json, body_json = await self.app.handle_request(
            "POST",
            f"/api/listing/{target_id}/bookmark",
            headers={"accept": "application/json"},
        )
        self.assertEqual(status_json, 200)
        self.assertEqual(headers_json["Content-Type"], "application/json")
        data_json = json.loads(body_json.decode("utf-8"))
        self.assertEqual(data_json["id"], target_id)
        self.assertEqual(data_json["flag"], "user_bookmarked")
        self.assertIn("value", data_json)
        self.assertIn("kpis", data_json)

        # JSON mode via query format=json on dismiss
        status_dis, headers_dis, body_dis = await self.app.handle_request(
            "POST",
            f"/api/listing/{target_id}/dismiss",
            query_params={"format": "json"},
        )
        self.assertEqual(status_dis, 200)
        self.assertEqual(headers_dis["Content-Type"], "application/json")
        data_dis = json.loads(body_dis.decode("utf-8"))
        self.assertEqual(data_dis["flag"], "user_dismissed")

        # Missing listing in JSON mode returns 404
        status_404, _, body_404 = await self.app.handle_request(
            "POST",
            "/api/listing/non-existent-id/bookmark",
            headers={"accept": "application/json"},
        )
        self.assertEqual(status_404, 404)
        err_data = json.loads(body_404.decode("utf-8"))
        self.assertIn("error", err_data)

    # 5. Canonical v2 Flag Endpoint with Key Normalization
    async def test_canonical_flag_toggle_endpoint(self) -> None:
        """
        Verify /api/listings/{id}/flag/{key} endpoint normalizes keys and returns JSON.

        Pre-conditions:
            - Valid listing present.

        Post-conditions:
            - user_bookmarked, bookmark, user_dismissed, and dismiss keys succeed.
            - Invalid flag keys return 400 JSON.
            - Missing listing returns 404 JSON.
        """
        target_id = "22222222-2222-2222-2222-222222222222"

        # Toggle user_bookmarked
        status, _, body = await self.app.handle_request(
            "POST", f"/api/listings/{target_id}/flag/user_bookmarked"
        )
        self.assertEqual(status, 200)
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(payload["flag"], "user_bookmarked")
        self.assertTrue(payload["value"])

        # Toggle via alias bookmark
        status_alias, _, body_alias = await self.app.handle_request(
            "POST", f"/api/listings/{target_id}/flag/bookmark"
        )
        self.assertEqual(status_alias, 200)
        payload_alias = json.loads(body_alias.decode("utf-8"))
        self.assertEqual(payload_alias["flag"], "user_bookmarked")
        self.assertFalse(payload_alias["value"])

        # Toggle via alias dismiss
        status_dis, _, body_dis = await self.app.handle_request(
            "POST", f"/api/listings/{target_id}/flag/dismiss"
        )
        self.assertEqual(status_dis, 200)
        payload_dis = json.loads(body_dis.decode("utf-8"))
        self.assertEqual(payload_dis["flag"], "user_dismissed")

        # Invalid flag key returns 400
        status_invalid, _, body_invalid = await self.app.handle_request(
            "POST", f"/api/listings/{target_id}/flag/unsupported_flag"
        )
        self.assertEqual(status_invalid, 400)
        err_invalid = json.loads(body_invalid.decode("utf-8"))
        self.assertIn("error", err_invalid)

        # Missing listing returns 404
        status_missing, _, body_missing = await self.app.handle_request(
            "POST", "/api/listings/missing-guid/flag/user_bookmarked"
        )
        self.assertEqual(status_missing, 404)
        err_missing = json.loads(body_missing.decode("utf-8"))
        self.assertIn("error", err_missing)

    # 6. Scan Workflow Endpoints
    async def test_scan_workflow_endpoints(self) -> None:
        """
        Verify scan workflow trigger and status endpoints in both JSON and HTML modes.

        Pre-conditions:
            - Temporal SDK may be absent or present.

        Post-conditions:
            - POST /api/scan returns JSON or clean HTML error banner gracefully.
            - GET /api/scan/status returns JSON summary or active scan tracking.
            - GET /api/scan/{wf_id}/status returns JSON or HTML status banner.
        """
        # POST /api/scan with format=json
        status, _, body = await self.app.handle_request(
            "POST",
            "/api/scan",
            body_params={"target": "Tesla|Model 3"},
            query_params={"format": "json"},
        )
        self.assertEqual(status, 200)
        payload = json.loads(body.decode("utf-8"))
        self.assertIn("started", payload)
        self.assertIn("temporal_available", payload)
        self.assertIn("temporal_ui_url", payload)
        if payload.get("temporal_ui_url"):
            self.assertNotIn("localhost:8080", payload["temporal_ui_url"])

        # POST /api/scan HTML mode (when Temporal fails/not installed)
        status_html, headers_html, body_html = await self.app.handle_request(
            "POST",
            "/api/scan",
            body_params={"target": "ALL"},
        )
        self.assertEqual(status_html, 200)
        self.assertIn("text/html", headers_html["Content-Type"])

        # Simulate a successful scan workflow trigger
        with patch.object(self.app, "trigger_scan_workflow", new=AsyncMock(return_value=("wf-test-123", None))):
            status_sim, _, body_sim = await self.app.handle_request(
                "POST",
                "/api/scan",
                headers={"accept": "application/json"},
            )
            self.assertEqual(status_sim, 200)
            sim_data = json.loads(body_sim.decode("utf-8"))
            self.assertTrue(sim_data["started"])
            self.assertEqual(sim_data["workflow_id"], "wf-test-123")
            self.assertEqual(self.app._last_scan_workflow_id, "wf-test-123")

        # GET /api/scan/status using tracked workflow ID
        with patch.object(
            self.app,
            "query_scan_workflow",
            new=AsyncMock(return_value={"is_completed": False, "total_scraped": 42, "total_scored": 10}),
        ):
            status_st, _, body_st = await self.app.handle_request("GET", "/api/scan/status")
            self.assertEqual(status_st, 200)
            st_data = json.loads(body_st.decode("utf-8"))
            self.assertEqual(st_data["active_workflow_id"], "wf-test-123")
            self.assertEqual(st_data["summary"]["total_scraped"], 42)

            # GET /api/scan/status HTML mode
            status_st_html, _, body_st_html = await self.app.handle_request(
                "GET", "/api/scan/status", query_params={"format": "html"}
            )
            self.assertEqual(status_st_html, 200)
            self.assertIn("wf-test-123", body_st_html.decode("utf-8"))

            # GET /api/scan/{wf_id}/status JSON mode
            status_wf_json, _, body_wf_json = await self.app.handle_request(
                "GET",
                "/api/scan/wf-test-123/status",
                headers={"accept": "application/json"},
            )
            self.assertEqual(status_wf_json, 200)
            wf_data = json.loads(body_wf_json.decode("utf-8"))
            self.assertEqual(wf_data["active_workflow_id"], "wf-test-123")

            # GET /api/scan/{wf_id}/status HTML mode
            status_wf_html, _, body_wf_html = await self.app.handle_request(
                "GET",
                "/api/scan/wf-test-123/status",
            )
            self.assertEqual(status_wf_html, 200)
            self.assertIn("wf-test-123", body_wf_html.decode("utf-8"))

    # 7. Exports: CSV and Markdown
    async def test_exports_csv_and_markdown(self) -> None:
        """
        Verify export endpoints for CSV and Markdown formatted output.

        Pre-conditions:
            - Repository contains sample listings.

        Post-conditions:
            - CSV export sets Content-Type text/csv and Content-Disposition attachment.
            - Markdown export sets Content-Type text/markdown.
        """
        # CSV
        status_csv, headers_csv, body_csv = await self.app.handle_request("GET", "/api/export/csv")
        self.assertEqual(status_csv, 200)
        self.assertEqual(headers_csv["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment", headers_csv["Content-Disposition"])
        csv_text = body_csv.decode("utf-8")
        self.assertIn("VIN", csv_text)
        self.assertIn("W1KCG2DB6PA043095", csv_text)

        # Markdown
        status_md, headers_md, body_md = await self.app.handle_request("GET", "/api/export/markdown")
        self.assertEqual(status_md, 200)
        self.assertEqual(headers_md["Content-Type"], "text/markdown; charset=utf-8")
        md_text = body_md.decode("utf-8")
        self.assertIn("TOP VEHICLE DEALS FOUND", md_text)
        self.assertIn("Mercedes-Benz", md_text)

    # 8. Provenance-Enriched Health & Deals Endpoints
    async def test_health_and_deals_apis_with_provenance(self) -> None:
        """
        Verify /api/health and /api/deals include provenance metadata.

        Pre-conditions:
            - Repository provides valid provenance dictionary.

        Post-conditions:
            - Both responses include non-empty provenance object.
        """
        # /api/health
        status_h, _, body_h = await self.app.handle_request("GET", "/api/health")
        self.assertEqual(status_h, 200)
        data_h = json.loads(body_h.decode("utf-8"))
        self.assertEqual(data_h["status"], "ok")
        self.assertEqual(data_h["service"], "car-researcher-dashboard")
        self.assertIn("provenance", data_h)
        self.assertIn("mode", data_h["provenance"])

        # /api/deals
        status_d, _, body_d = await self.app.handle_request("GET", "/api/deals")
        self.assertEqual(status_d, 200)
        data_d = json.loads(body_d.decode("utf-8"))
        self.assertIn("provenance", data_d)
        self.assertIn("kpis", data_d)
        self.assertIn("filters", data_d)
        self.assertEqual(data_d["count"], 3)
        self.assertEqual(len(data_d["deals"]), 3)

    # 9. Market Intelligence: Overview, Cohorts, Dealers
    async def test_market_intelligence_endpoints(self) -> None:
        """
        Verify market overview, cohort distributions, and dealer arbitrage APIs.

        Pre-conditions:
            - Repository analytics layer is functional.

        Post-conditions:
            - Returns 200 JSON with structured metrics for all three endpoints.
        """
        # /api/market/overview
        status_ov, _, body_ov = await self.app.handle_request("GET", "/api/market/overview")
        self.assertEqual(status_ov, 200)
        data_ov = json.loads(body_ov.decode("utf-8"))
        self.assertIn("kpis", data_ov)
        self.assertIn("leaderboard", data_ov)
        self.assertIn("provenance", data_ov)

        # /api/market/cohorts
        status_co, _, body_co = await self.app.handle_request(
            "GET",
            "/api/market/cohorts",
            query_params={"make": "Mercedes-Benz"},
        )
        self.assertEqual(status_co, 200)
        data_co = json.loads(body_co.decode("utf-8"))
        self.assertIn("cohorts", data_co)

        # /api/market/dealers
        status_dl, _, body_dl = await self.app.handle_request("GET", "/api/market/dealers")
        self.assertEqual(status_dl, 200)
        data_dl = json.loads(body_dl.decode("utf-8"))
        self.assertIn("dealers", data_dl)
        self.assertIn("platforms", data_dl)
        self.assertIn("distance_bands", data_dl)

    # 10. Listing History and Analysis Dossier Endpoints
    @patch("src.dashboard.queries.GovAPIClient")
    async def test_listing_history_and_analysis_apis(self, mock_gov_cls: Any) -> None:
        """
        Verify /api/listings/{id}/history and /api/listings/{id}/analysis endpoints.

        Pre-conditions:
            - Mocked GovAPIClient to eliminate external API calls.

        Post-conditions:
            - Valid listing returns 200 JSON with deal, snapshots, or full dossier.
            - Non-existent listing returns 404 JSON for both endpoints.
        """
        mock_gov = mock_gov_cls.return_value
        mock_gov.get_recalls = AsyncMock(return_value=[])
        mock_gov.get_complaints = AsyncMock(return_value=[])
        mock_gov.get_epa_fuel_economy = AsyncMock(return_value=[])

        target_id = "11111111-1111-1111-1111-111111111111"

        # Valid history
        status_h, _, body_h = await self.app.handle_request("GET", f"/api/listings/{target_id}/history")
        self.assertEqual(status_h, 200)
        data_h = json.loads(body_h.decode("utf-8"))
        self.assertIn("deal", data_h)
        self.assertIn("snapshots", data_h)
        self.assertIn("provenance", data_h)
        self.assertGreaterEqual(len(data_h["snapshots"]), 1)

        # Missing history -> 404
        status_h_404, _, body_h_404 = await self.app.handle_request(
            "GET", "/api/listings/00000000-0000-0000-0000-000000000000/history"
        )
        self.assertEqual(status_h_404, 404)
        self.assertIn("error", json.loads(body_h_404.decode("utf-8")))

        # Valid analysis dossier
        status_a, _, body_a = await self.app.handle_request("GET", f"/api/listings/{target_id}/analysis")
        self.assertEqual(status_a, 200)
        data_a = json.loads(body_a.decode("utf-8"))
        self.assertIn("deal", data_a)
        self.assertIn("cohort", data_a)
        self.assertIn("snapshots", data_a)
        self.assertIn("safety_posture", data_a)

        # Missing analysis -> 404
        status_a_404, _, body_a_404 = await self.app.handle_request(
            "GET", "/api/listings/00000000-0000-0000-0000-000000000000/analysis"
        )
        self.assertEqual(status_a_404, 404)
        self.assertIn("error", json.loads(body_a_404.decode("utf-8")))

    # 11. Model Intelligence Endpoint
    @patch("src.dashboard.queries.GovAPIClient")
    async def test_model_intelligence_api(self, mock_gov_cls: Any) -> None:
        """
        Verify /api/models/{make}/{model}/{year} endpoint and integer validation.

        Pre-conditions:
            - Mocked GovAPIClient to eliminate external API calls.

        Post-conditions:
            - Valid make/model/year returns 200 JSON with recalls, complaints, and EPA specs.
            - Non-integer year returns 400 JSON.
        """
        mock_gov = mock_gov_cls.return_value
        mock_gov.get_recalls = AsyncMock(return_value=[])
        mock_gov.get_complaints = AsyncMock(return_value=[])
        mock_gov.get_epa_fuel_economy = AsyncMock(return_value=[])

        # Valid request
        status, _, body = await self.app.handle_request("GET", "/api/models/Mercedes-Benz/EQS/2023")
        self.assertEqual(status, 200)
        profile = json.loads(body.decode("utf-8"))
        self.assertEqual(profile["make"], "Mercedes-Benz")
        self.assertEqual(profile["model"], "EQS")
        self.assertEqual(profile["year"], 2023)
        self.assertIn("recalls", profile)
        self.assertIn("complaints", profile)
        self.assertIn("epa_specs", profile)

        # Invalid year -> 400
        status_bad, _, body_bad = await self.app.handle_request("GET", "/api/models/Mercedes-Benz/EQS/not-a-year")
        self.assertEqual(status_bad, 400)
        err = json.loads(body_bad.decode("utf-8"))
        self.assertIn("error", err)

    # 12. Compare Endpoint (Max 3)
    async def test_compare_api(self) -> None:
        """
        Verify /api/compare endpoint handles 0 to 3 IDs and rejects 4 or more with 400.

        Pre-conditions:
            - Sample listings available in repo.

        Post-conditions:
            - 0, 2, 3 IDs return 200 JSON with comparison data.
            - >3 IDs return 400 JSON error.
        """
        # 0 IDs
        status_0, _, body_0 = await self.app.handle_request("GET", "/api/compare")
        self.assertEqual(status_0, 200)
        data_0 = json.loads(body_0.decode("utf-8"))
        self.assertEqual(len(data_0["deals"]), 0)

        # 2 IDs
        id1 = "11111111-1111-1111-1111-111111111111"
        id2 = "22222222-2222-2222-2222-222222222222"
        status_2, _, body_2 = await self.app.handle_request(
            "GET", "/api/compare", query_params={"ids": f"{id1},{id2}"}
        )
        self.assertEqual(status_2, 200)
        data_2 = json.loads(body_2.decode("utf-8"))
        self.assertEqual(len(data_2["deals"]), 2)

        # 3 IDs (max allowed)
        id3 = "33333333-3333-3333-3333-333333333333"
        status_3, _, body_3 = await self.app.handle_request(
            "GET", "/api/compare", query_params={"ids": f"{id1},{id2},{id3}"}
        )
        self.assertEqual(status_3, 200)
        data_3 = json.loads(body_3.decode("utf-8"))
        self.assertEqual(len(data_3["deals"]), 3)

        # 4 IDs (> 3 -> 400)
        status_4, _, body_4 = await self.app.handle_request(
            "GET", "/api/compare", query_params={"ids": f"{id1},{id2},{id3},44444444-4444-4444-4444-444444444444"}
        )
        self.assertEqual(status_4, 400)
        data_4 = json.loads(body_4.decode("utf-8"))
        self.assertIn("error", data_4)

    # 13. HTTP Connection Handler (_handle_client)
    async def test_handle_client_connection(self) -> None:
        """
        Verify _handle_client reads request lines, parses headers, handles JSON body, and writes response.

        Pre-conditions:
            - Mock reader and mock writer simulate an asyncio TCP socket.

        Post-conditions:
            - Client receives valid HTTP/1.1 response with proper headers, status text, and body.
        """
        # Test 1: GET request
        reader = asyncio.StreamReader()
        reader.feed_data(b"GET /api/health HTTP/1.1\r\nHost: localhost\r\nAccept: application/json\r\n\r\n")
        reader.feed_eof()
        writer = MockStreamWriter()

        await _handle_client(reader, writer, self.app)  # type: ignore[arg-type]
        output = writer.buffer.decode("utf-8")
        self.assertTrue(output.startswith("HTTP/1.1 200 OK\r\n"))
        self.assertIn("Content-Type: application/json", output)
        self.assertIn('"status": "ok"', output)
        self.assertTrue(writer.is_closed)

        # Test 2: POST request with JSON payload
        post_body = b'{"target": "Kia|EV6"}'
        reader_post = asyncio.StreamReader()
        reader_post.feed_data(
            b"POST /api/scan HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Content-Type: application/json\r\n"
            b"Accept: application/json\r\n"
            + f"Content-Length: {len(post_body)}\r\n\r\n".encode("utf-8")
            + post_body
        )
        reader_post.feed_eof()
        writer_post = MockStreamWriter()

        await _handle_client(reader_post, writer_post, self.app)  # type: ignore[arg-type]
        output_post = writer_post.buffer.decode("utf-8")
        self.assertTrue(output_post.startswith("HTTP/1.1 200 OK\r\n"))
        self.assertIn("application/json", output_post)

        # Test 3: 404 response status line mapping
        reader_404 = asyncio.StreamReader()
        reader_404.feed_data(b"GET /unknown-endpoint HTTP/1.1\r\nHost: localhost\r\n\r\n")
        reader_404.feed_eof()
        writer_404 = MockStreamWriter()

        await _handle_client(reader_404, writer_404, self.app)  # type: ignore[arg-type]
        output_404 = writer_404.buffer.decode("utf-8")
        self.assertTrue(output_404.startswith("HTTP/1.1 404 Not Found\r\n"))

    # 14. Helper Unit Tests
    def test_helper_parsers(self) -> None:
        """
        Verify helper functions _parse_int, _parse_float, _wants_json, _wants_html, _status_text, etc.

        Pre-conditions:
            - None.

        Post-conditions:
            - All parsing functions return expected types or fallbacks.
        """
        self.assertEqual(_parse_int("42"), 42)
        self.assertIsNone(_parse_int("abc"))
        self.assertIsNone(_parse_int(None))

        self.assertEqual(_parse_float("3.14"), 3.14)
        self.assertIsNone(_parse_float("xyz"))
        self.assertIsNone(_parse_float(None))

        self.assertTrue(_wants_json({"format": "json"}, None))
        self.assertTrue(_wants_json(None, {"accept": "application/json"}))
        self.assertFalse(_wants_json(None, {"accept": "text/html"}))

        self.assertTrue(_wants_html({"format": "html"}, None))
        self.assertTrue(_wants_html(None, {"accept": "text/html"}))
        self.assertFalse(_wants_html(None, {"accept": "application/json"}))

        self.assertEqual(_status_text(200), "OK")
        self.assertEqual(_status_text(400), "Bad Request")
        self.assertEqual(_status_text(403), "Forbidden")
        self.assertEqual(_status_text(404), "Not Found")
        self.assertEqual(_status_text(500), "Internal Server Error")

        headers = _read_request_headers([b"Host: 127.0.0.1:8000\r\n", b"Content-Type: application/json\r\n"])
        self.assertEqual(headers["host"], "127.0.0.1:8000")
        self.assertEqual(headers["content-type"], "application/json")

        json_parsed = asyncio.run(_parse_json_body(b'{"key": "value"}'))
        self.assertEqual(json_parsed, {"key": "value"})

        json_empty = asyncio.run(_parse_json_body(b"not json"))
        self.assertEqual(json_empty, {})

    # 15. Source Code Invariants: No Emojis & No Hardcoded Localhost:8080
    def test_source_code_invariants(self) -> None:
        """
        Verify that src/dashboard/app.py contains zero emojis and zero localhost:8080 strings.

        Pre-conditions:
            - src/dashboard/app.py exists and is readable.

        Post-conditions:
            - No characters with ord > 127 exist.
            - localhost:8080 does not appear anywhere in the source file.
        """
        app_path = Path(__file__).resolve().parent.parent / "src" / "dashboard" / "app.py"
        self.assertTrue(app_path.is_file())
        content = app_path.read_text(encoding="utf-8")

        # Zero non-ASCII characters (zero emojis)
        non_ascii = [c for c in content if ord(c) > 127]
        self.assertEqual(
            len(non_ascii),
            0,
            f"Found {len(non_ascii)} non-ASCII character(s) in src/dashboard/app.py: {set(non_ascii)}",
        )

        # Zero localhost:8080
        self.assertNotIn("localhost:8080", content)

    # 16. Root SSR Payload Compactness & Single-Pass Query Invariant
    async def test_root_ssr_payload_compactness_under_production_scale(self) -> None:
        """
        Verify GET / returns compact HTML (< 512 KB) without bloated raw_data,
        duplicated analytics dicts, or redundant market_overview database queries
        even when the repository contains hundreds of production-sized listings.

        Pre-conditions:
            - Repository seeded with 300 listings containing 5 KB raw scraper blobs.

        Post-conditions:
            - GET / response body is strictly under 512 KB (524,288 bytes).
            - Inline initial-state JSON omits raw_data, price_history, and duplicate analytics keys.
            - KPI total_active reflects the full 300-listing inventory while SSR cards are capped.
        """
        base_samples = _sample_deals()
        large_inventory: List[Dict[str, Any]] = []
        for idx in range(300):
            template = dict(base_samples[idx % len(base_samples)])
            template["id"] = f"00000000-0000-4000-8000-{idx:012d}"
            template["vin"] = f"W1KCG2DB6PA{idx:06d}"
            template["raw_data"] = {
                "make": "Mercedes-Benz",
                "model": "EQS",
                "year": 2023,
                "unpruned_scraper_payload": "X" * 5000,
            }
            large_inventory.append(template)

        prod_repo = DashboardRepository(fallback_deals=large_inventory)
        prod_app = DashboardApp(repo=prod_repo)

        with patch.object(
            prod_repo,
            "get_market_overview",
            wraps=prod_repo.get_market_overview,
        ) as spy_overview:
            status, headers, body = await prod_app.handle_request("GET", "/")

        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertLess(
            len(body),
            512 * 1024,
            f"GET / HTML payload ({len(body)} bytes) exceeded 512 KB threshold",
        )
        self.assertEqual(
            spy_overview.call_count,
            0,
            "GET / should not eagerly execute get_market_overview() during root SSR",
        )

        html_text = body.decode("utf-8")
        self.assertNotIn("unpruned_scraper_payload", html_text)

        import re
        match = re.search(
            r'<script id="initial-state" type="application/json">(.*?)</script>',
            html_text,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        if match:
            state_payload = json.loads(match.group(1).replace("<\\/", "</"))
            self.assertEqual(state_payload["kpis"]["total_active"], 300)
            self.assertLessEqual(len(state_payload["deals"]), 48)
            first_deal = state_payload["deals"][0]
            self.assertNotIn("raw_data", first_deal)
            self.assertNotIn("analytics", first_deal)
            self.assertNotIn("price_history", first_deal)
            self.assertIn("deal_score", first_deal)
            self.assertIn("price", first_deal)


if __name__ == "__main__":
    unittest.main()
