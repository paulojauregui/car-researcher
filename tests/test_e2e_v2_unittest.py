"""
Milestone M09 Unit & End-to-End Integration Tests.

Validates complete Milestone M09 acceptance criteria:
- DashboardApp initialized with default DashboardRepository(fallback_deals=None),
  proving offline-sample 24-EV mode works out of the box.
- HTTP routing for GET /, HEAD /, and safe static assets: tokens.css, components.css,
  app.js, views.js, charts.js.
- v2 Market Intelligence JSON APIs: /api/health, /api/deals, /api/market/overview,
  /api/market/cohorts, /api/market/dealers, /api/listings/{id}/analysis,
  /api/listings/{id}/history, and /api/compare.
- Strict zero-emoji mandate across all .py, .html, .css, and .js files in
  src/dashboard/ and src/activities/market_analytics.py.
- Strict zero external CDN references and zero hardcoded cluster port strings.
- Explicit <label for="..."> validation on every non-hidden input and select in rendered HTML.
- Static structural verification of app.js (balanced delimiters, imports, contracts).

Pre-conditions:
    - Python standard library only (unittest, pathlib, re, json, html.parser).
    - Network boundaries mocked via GovAPIClient patch.
Post-conditions:
    - 100% test pass rate with zero external pip dependencies.
    - Zero emojis and zero hardcoded localhost:8080 strings.
"""

from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import unittest
from unittest.mock import AsyncMock, patch

from src.dashboard.app import DashboardApp
from src.dashboard.queries import DashboardRepository


def _header_val(headers: Dict[str, str], name: str) -> str:
    """
    Case-insensitive HTTP header lookup.

    Pre-conditions:
        - headers is a string-to-string dictionary.
        - name is the header name to find.
    Post-conditions:
        - Returns header value string, or empty string if not present.
    """
    target = name.lower()
    for k, v in headers.items():
        if k.lower() == target:
            return v
    return ""


class BalancedDelimiterParser:
    """
    Parser verifying balanced JavaScript brackets, braces, and parentheses.

    Pre-conditions:
        - Input source is valid JavaScript source text.
    Post-conditions:
        - Tracks delimiter depth skipping comments, strings, template literals, and regexes.
    """

    def __init__(self, source: str) -> None:
        """
        Initialize delimiter parser with source code.

        Pre-conditions:
            - source is a string.
        Post-conditions:
            - self.source is stored.
        """
        self.source: str = source

    def parse(self) -> Tuple[bool, List[str]]:
        """
        Scan source code and return balance status and error messages.

        Pre-conditions:
            - None.
        Post-conditions:
            - Returns (True, []) if all delimiters match and stack is empty,
              or (False, [errors]) describing unmatched or mismatched tokens.
        """
        stack: List[Tuple[str, int]] = []
        pairs: Dict[str, str] = {")": "(", "}": "{", "]": "["}
        errors: List[str] = []
        i: int = 0
        n: int = len(self.source)
        text: str = self.source

        while i < n:
            # Single-line comment
            if text[i : i + 2] == "//":
                end_idx: int = text.find("\n", i)
                i = n if end_idx == -1 else end_idx + 1
            # Multi-line comment
            elif text[i : i + 2] == "/*":
                end_idx = text.find("*/", i)
                if end_idx == -1:
                    errors.append(f"Unterminated block comment starting at pos {i}")
                    break
                i = end_idx + 2
            # String literals and template literals
            elif text[i] in ("'", '"', "`"):
                quote_char: str = text[i]
                start_pos: int = i
                i += 1
                closed: bool = False
                while i < n:
                    if text[i] == "\\":
                        i += 2
                    elif text[i] == quote_char:
                        closed = True
                        i += 1
                        break
                    else:
                        i += 1
                if not closed:
                    errors.append(f"Unterminated string starting at pos {start_pos}")
                    break
            # Regular expression literal
            elif text[i] == "/" and i + 1 < n and text[i + 1] not in ("/", "*"):
                prev: str = text[:i].rstrip()
                if prev and prev[-1] in "=(:[{,;!&|?":
                    i += 1
                    while i < n:
                        if text[i] == "\\":
                            i += 2
                        elif text[i] == "/":
                            i += 1
                            break
                        else:
                            i += 1
                else:
                    i += 1
            # Opening delimiters
            elif text[i] in ("(", "{", "["):
                stack.append((text[i], i))
                i += 1
            # Closing delimiters
            elif text[i] in (")", "}", "]"):
                expected_open: str = pairs[text[i]]
                if not stack:
                    errors.append(f"Unmatched closing '{text[i]}' at pos {i}")
                else:
                    actual_open, open_pos = stack.pop()
                    if actual_open != expected_open:
                        errors.append(
                            f"Mismatched delimiter: expected closing for '{actual_open}' from pos {open_pos}, but found '{text[i]}' at pos {i}"
                        )
                i += 1
            else:
                i += 1

        while stack:
            unclosed, pos = stack.pop()
            errors.append(f"Unclosed '{unclosed}' opened at pos {pos}")

        return (len(errors) == 0, errors)


class FormLabelAuditParser(HTMLParser):
    """
    HTML parser that collects all label 'for' attributes and non-hidden inputs/selects.

    Pre-conditions:
        - HTML content is valid UTF-8 text.
    Post-conditions:
        - self.labels maps target element IDs to True.
        - self.inputs and self.selects contain attribute dicts for inspection.
    """

    def __init__(self) -> None:
        """
        Initialize the label audit parser.

        Pre-conditions:
            - None.
        Post-conditions:
            - Internal registries initialized.
        """
        super().__init__()
        self.labels: Set[str] = set()
        self.inputs: List[Dict[str, str]] = []
        self.selects: List[Dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        """
        Process start tag and register labels, inputs, and selects.

        Pre-conditions:
            - tag is element name.
            - attrs is list of attribute tuples.
        Post-conditions:
            - Updates labels, inputs, or selects registries.
        """
        attr_dict: Dict[str, str] = {k: (v or "") for k, v in attrs}
        if tag == "label":
            for_target: str = attr_dict.get("for", "").strip()
            if for_target:
                self.labels.add(for_target)
        elif tag == "input":
            input_type: str = attr_dict.get("type", "text").lower()
            if input_type != "hidden":
                self.inputs.append(attr_dict)
        elif tag == "select":
            self.selects.append(attr_dict)


class TestDashboardE2EV2(unittest.IsolatedAsyncioTestCase):
    """
    End-to-end integration and static contract verification test suite.

    Pre-conditions:
        - Standard library execution.
    Post-conditions:
        - All assertions pass with zero emojis and zero external network calls.
    """

    def setUp(self) -> None:
        """
        Initialize test fixtures and app instances before each test.

        Pre-conditions:
            - None.
        Post-conditions:
            - self.repo and self.app configured in default offline-sample mode.
        """
        self.repo: DashboardRepository = DashboardRepository(fallback_deals=None)
        self.app: DashboardApp = DashboardApp(repo=self.repo)
        self.base_dir: Path = Path(__file__).resolve().parent.parent

    async def test_01_root_get_nominal_e2e(self) -> None:
        """
        Verify GET / serves semantic HTML shell with populated initial state in offline mode.

        Pre-conditions:
            - DashboardApp initialized with default DashboardRepository().
        Post-conditions:
            - Status 200, Content-Type text/html.
            - Contains all 4 workspace panels, #compare-tray, #analysis-drawer.
            - Initial state contains exactly 24 offline sample deals.
        """
        status, headers, body = await self.app.handle_request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", _header_val(headers, "content-type"))

        html_text: str = body.decode("utf-8")
        self.assertIn("<!DOCTYPE html>", html_text)
        self.assertIn("Bay Area EV Deal Surveillance", html_text)
        self.assertIn('id="live-announcer"', html_text)
        self.assertIn('id="workspace-workbench"', html_text)
        self.assertIn('id="workspace-market"', html_text)
        self.assertIn('id="workspace-arbitrage"', html_text)
        self.assertIn('id="workspace-compare"', html_text)
        self.assertIn('id="compare-tray"', html_text)
        self.assertIn('id="analysis-drawer"', html_text)
        self.assertIn('<script type="module" src="/static/app.js"></script>', html_text)

        # Parse and validate initial state JSON
        match = re.search(r'<script id="initial-state" type="application/json">(.*?)</script>', html_text, re.DOTALL)
        self.assertIsNotNone(match, "Initial state JSON script block must be present")
        if match:
            raw_json: str = match.group(1).replace("<\\/", "</")
            initial_state: Dict[str, Any] = json.loads(raw_json)
            self.assertIn("deals", initial_state)
            self.assertEqual(len(initial_state["deals"]), 24, "Default offline sample should contain 24 EVs")
            self.assertIn("kpis", initial_state)
            self.assertEqual(initial_state["kpis"].get("total_active"), 24)
            self.assertIn("filters", initial_state)
            self.assertIn("provenance", initial_state)

    async def test_02_root_head_nominal_e2e(self) -> None:
        """
        Verify HEAD / returns status 200 with headers and strictly zero body bytes.

        Pre-conditions:
            - Server is ready.
        Post-conditions:
            - Status 200, Content-Type text/html, empty body.
        """
        status, headers, body = await self.app.handle_request("HEAD", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", _header_val(headers, "content-type"))
        self.assertEqual(len(body), 0, "HEAD response must have zero body bytes")

    async def test_03_static_assets_delivery_e2e(self) -> None:
        """
        Verify traversal-safe delivery and MIME types of all client static assets.

        Pre-conditions:
            - STATIC_DIR exists.
        Post-conditions:
            - tokens.css, components.css, app.js, views.js, charts.js return 200 with correct MIME.
            - Path traversal attempts return 404.
        """
        assets: List[Tuple[str, str]] = [
            ("/static/tokens.css", "text/css"),
            ("/static/components.css", "text/css"),
            ("/static/app.js", "application/javascript"),
            ("/static/views.js", "application/javascript"),
            ("/static/charts.js", "application/javascript"),
        ]
        for path, expected_mime in assets:
            status, headers, body = await self.app.handle_request("GET", path)
            self.assertEqual(status, 200, f"Expected 200 for static asset: {path}")
            self.assertIn(expected_mime, _header_val(headers, "content-type"))
            self.assertGreater(len(body), 0, f"Static asset {path} must not be empty")

        # Traversal protection verification
        status_trav, _, _ = await self.app.handle_request("GET", "/static/../app.py")
        self.assertIn(status_trav, (403, 404), "Path traversal outside static dir must be rejected")

    async def test_04_api_health_e2e(self) -> None:
        """
        Verify GET /api/health returns operational telemetry and data source provenance.

        Pre-conditions:
            - app is initialized.
        Post-conditions:
            - Status 200, JSON containing status, mode, and detail.
        """
        status, headers, body = await self.app.handle_request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertIn("application/json", _header_val(headers, "content-type"))
        data: Dict[str, Any] = json.loads(body)
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("provenance", data)
        self.assertIn("mode", data["provenance"])

    async def test_05_api_deals_and_filtering_e2e(self) -> None:
        """
        Verify GET /api/deals returns 24 default vehicles and responds accurately to query filters.

        Pre-conditions:
            - 24-EV offline sample dataset is loaded.
        Post-conditions:
            - Filters by query keyword, maximum price, and triage tab work accurately.
        """
        # Baseline fetch
        status, _, body = await self.app.handle_request("GET", "/api/deals")
        self.assertEqual(status, 200)
        data: Dict[str, Any] = json.loads(body)
        self.assertEqual(data.get("count"), 24)
        self.assertEqual(len(data.get("deals", [])), 24)

        # Keyword filter
        status_q, _, body_q = await self.app.handle_request("GET", "/api/deals", query_params={"q": "Mercedes"})
        self.assertEqual(status_q, 200)
        data_q: Dict[str, Any] = json.loads(body_q)
        for deal in data_q.get("deals", []):
            full_text: str = f"{deal.get('title', '')} {deal.get('seller_name', '')} {deal.get('vin', '')}"
            self.assertIn("Mercedes", full_text)

        # Price ceiling filter
        status_p, _, body_p = await self.app.handle_request("GET", "/api/deals", query_params={"max_price": "35000"})
        self.assertEqual(status_p, 200)
        data_p: Dict[str, Any] = json.loads(body_p)
        for deal in data_p.get("deals", []):
            self.assertLessEqual(deal.get("price", 0), 35000)

        # Triage tab filter
        status_t, _, body_t = await self.app.handle_request("GET", "/api/deals", query_params={"tab": "excellent"})
        self.assertEqual(status_t, 200)
        data_t: Dict[str, Any] = json.loads(body_t)
        for deal in data_t.get("deals", []):
            self.assertGreaterEqual(float(deal.get("deal_score", 0.0)), 85.0)

    async def test_06_api_market_overview_e2e(self) -> None:
        """
        Verify GET /api/market/overview returns market overview analytics.

        Pre-conditions:
            - Market analytics pipeline is operational.
        Post-conditions:
            - Status 200, JSON containing kpis, leaderboard, and provenance.
        """
        status, headers, body = await self.app.handle_request("GET", "/api/market/overview")
        self.assertEqual(status, 200)
        self.assertIn("application/json", _header_val(headers, "content-type"))
        data: Dict[str, Any] = json.loads(body)
        self.assertIn("kpis", data)
        self.assertIn("leaderboard", data)
        self.assertIn("provenance", data)

    async def test_07_api_market_cohorts_e2e(self) -> None:
        """
        Verify GET /api/market/cohorts returns cohort percentiles and scatter points.

        Pre-conditions:
            - Sample listings are loaded.
        Post-conditions:
            - Status 200, JSON containing cohorts and all_scatter.
            - Cohort query parameter returns selected_cohort.
        """
        status, headers, body = await self.app.handle_request("GET", "/api/market/cohorts")
        self.assertEqual(status, 200)
        self.assertIn("application/json", _header_val(headers, "content-type"))
        data: Dict[str, Any] = json.loads(body)
        self.assertIn("cohorts", data)
        self.assertIn("scatter", data)

        status_c, _, body_c = await self.app.handle_request(
            "GET", "/api/market/cohorts", query_params={"cohort": "Tesla|Model 3"}
        )
        self.assertEqual(status_c, 200)
        data_c: Dict[str, Any] = json.loads(body_c)
        self.assertIn("selected_cohort", data_c)

    async def test_08_api_market_dealers_e2e(self) -> None:
        """
        Verify GET /api/market/dealers returns channel arbitrage and dealer spread matrix.

        Pre-conditions:
            - Sample listings are loaded.
        Post-conditions:
            - Status 200, JSON containing platforms, distance_bands, and dealers.
        """
        status, headers, body = await self.app.handle_request("GET", "/api/market/dealers")
        self.assertEqual(status, 200)
        self.assertIn("application/json", _header_val(headers, "content-type"))
        data: Dict[str, Any] = json.loads(body)
        self.assertIn("platforms", data)
        self.assertIn("distance_bands", data)
        self.assertIn("dealers", data)

    @patch("src.dashboard.queries.GovAPIClient")
    async def test_09_api_listings_analysis_and_history_e2e(self, mock_gov_cls: Any) -> None:
        """
        Verify GET /api/listings/{id}/analysis and history endpoints return dossier data.

        Pre-conditions:
            - GovAPIClient mocked to ensure zero outbound network calls.
        Post-conditions:
            - Returns 200 with complete 7-section valuation dossier for existing deal.
            - Returns 404 for nonexistent listing ID.
        """
        mock_gov = mock_gov_cls.return_value
        mock_gov.get_recalls = AsyncMock(return_value=[])
        mock_gov.get_complaints = AsyncMock(return_value=[])
        mock_gov.get_epa_fuel_economy = AsyncMock(return_value=[])

        # Retrieve a valid listing ID
        deals = await self.repo.fetch_all_Normalized_deals()
        self.assertGreater(len(deals), 0)
        target_id: str = str(deals[0].get("id"))

        # Test Analysis endpoint
        status_a, _, body_a = await self.app.handle_request("GET", f"/api/listings/{target_id}/analysis")
        self.assertEqual(status_a, 200)
        data_a: Dict[str, Any] = json.loads(body_a)
        self.assertIn("deal", data_a)
        self.assertIn("cohort", data_a)
        self.assertIn("snapshots", data_a)
        self.assertIn("depreciation_3yr", data_a)
        self.assertIn("leverage", data_a)
        self.assertIn("tax_credit", data_a)
        self.assertIn("safety_posture", data_a)

        # Test History endpoint
        status_h, _, body_h = await self.app.handle_request("GET", f"/api/listings/{target_id}/history")
        self.assertEqual(status_h, 200)
        data_h: Dict[str, Any] = json.loads(body_h)
        self.assertIn("deal", data_h)
        self.assertIn("snapshots", data_h)

        # Test 404 on nonexistent ID
        status_404, _, _ = await self.app.handle_request("GET", "/api/listings/00000000-0000-0000-0000-000000000999/analysis")
        self.assertEqual(status_404, 404)

    async def test_10_api_compare_e2e(self) -> None:
        """
        Verify GET /api/compare handles up to 3 listings and rejects > 3 listings with 400.

        Pre-conditions:
            - Sample listings are loaded.
        Post-conditions:
            - Returns 200 with items, deals, and highlights for <= 3 IDs.
            - Returns 400 when > 3 IDs are requested.
        """
        deals = await self.repo.fetch_all_Normalized_deals()
        id1 = str(deals[0].get("id"))
        id2 = str(deals[1].get("id"))

        status_ok, _, body_ok = await self.app.handle_request("GET", "/api/compare", query_params={"ids": f"{id1},{id2}"})
        self.assertEqual(status_ok, 200)
        data_ok: Dict[str, Any] = json.loads(body_ok)
        self.assertEqual(data_ok.get("count"), 2)
        self.assertEqual(len(data_ok.get("deals", [])), 2)
        self.assertIn("highlights", data_ok)

        # Test > 3 rejection
        status_bad, _, body_bad = await self.app.handle_request("GET", "/api/compare", query_params={"ids": "1,2,3,4"})
        self.assertEqual(status_bad, 400)
        data_bad: Dict[str, Any] = json.loads(body_bad)
        self.assertIn("error", data_bad)

    async def test_11_optimistic_triage_endpoints_e2e(self) -> None:
        """
        Verify POST /api/listing/{id}/bookmark and /dismiss handle JSON negotiation cleanly.

        Pre-conditions:
            - Existing listing ID.
        Post-conditions:
            - Status 200, JSON containing id, flag, value, and updated kpis.
        """
        deals = await self.repo.fetch_all_Normalized_deals()
        target_id: str = str(deals[0].get("id"))

        status_bm, _, body_bm = await self.app.handle_request(
            "POST",
            f"/api/listing/{target_id}/bookmark",
            headers={"accept": "application/json"},
        )
        self.assertEqual(status_bm, 200)
        data_bm: Dict[str, Any] = json.loads(body_bm)
        self.assertEqual(data_bm.get("id"), target_id)
        self.assertIn("value", data_bm)
        self.assertIn("kpis", data_bm)

        status_dis, _, body_dis = await self.app.handle_request(
            "POST",
            f"/api/listing/{target_id}/dismiss",
            headers={"accept": "application/json"},
        )
        self.assertEqual(status_dis, 200)
        data_dis: Dict[str, Any] = json.loads(body_dis)
        self.assertEqual(data_dis.get("id"), target_id)
        self.assertIn("value", data_dis)
        self.assertIn("kpis", data_dis)

    def test_12_zero_emojis_across_dashboard_and_analytics(self) -> None:
        """
        Verify strict zero-emoji mandate across all files in src/dashboard/ and market_analytics.py.

        Pre-conditions:
            - Files exist on filesystem.
        Post-conditions:
            - Zero Unicode emoji glyphs found anywhere in Python, HTML, CSS, or JS files.
        """
        emoji_pattern = re.compile(
            r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]",
            flags=re.UNICODE,
        )
        targets: List[Path] = []
        dashboard_dir: Path = self.base_dir / "src" / "dashboard"
        for ext in ("*.py", "*.html", "*.css", "*.js"):
            targets.extend(dashboard_dir.rglob(ext))

        analytics_file: Path = self.base_dir / "src" / "activities" / "market_analytics.py"
        if analytics_file.exists():
            targets.append(analytics_file)

        self.assertGreater(len(targets), 5, "Must inspect multiple dashboard files")

        for file_path in targets:
            content: str = file_path.read_text(encoding="utf-8")
            match = emoji_pattern.search(content)
            self.assertIsNone(
                match,
                f"Prohibited emoji glyph '{match.group(0) if match else ''}' detected in {file_path}",
            )

    def test_13_zero_external_cdns_and_cluster_ports(self) -> None:
        """
        Verify zero external CDN strings and zero hardcoded localhost:8080 occurrences across src/dashboard/.

        Pre-conditions:
            - src/dashboard/ directory exists.
        Post-conditions:
            - Zero references to cdn.tailwindcss.com, unpkg.com, fonts.googleapis.
            - Zero hardcoded localhost:8080 references.
        """
        prohibited_cdns: List[str] = ["cdn.tailwindcss.com", "unpkg.com", "fonts.googleapis"]
        prohibited_ports: List[str] = ["localhost:8080"]

        dashboard_dir: Path = self.base_dir / "src" / "dashboard"
        targets: List[Path] = []
        for ext in ("*.py", "*.html", "*.css", "*.js"):
            targets.extend(dashboard_dir.rglob(ext))

        for file_path in targets:
            content: str = file_path.read_text(encoding="utf-8")
            for cdn in prohibited_cdns:
                self.assertNotIn(
                    cdn,
                    content,
                    f"Forbidden external CDN '{cdn}' found in {file_path}",
                )
            for port in prohibited_ports:
                self.assertNotIn(
                    port,
                    content,
                    f"Forbidden cluster port '{port}' found in {file_path}",
                )

    async def test_14_explicit_label_for_all_inputs_and_selects(self) -> None:
        """
        Validate explicit <label for="..."> association for every non-hidden <input> and <select>.

        Pre-conditions:
            - Rendered GET / HTML output.
        Post-conditions:
            - Every non-hidden input and select has an ID with a matching label element.
        """
        status, _, body = await self.app.handle_request("GET", "/")
        self.assertEqual(status, 200)
        html_text: str = body.decode("utf-8")

        parser = FormLabelAuditParser()
        parser.feed(html_text)

        self.assertGreater(len(parser.labels), 0, "Rendered HTML must contain form labels")

        for inp in parser.inputs:
            input_id: str = inp.get("id", "").strip()
            self.assertTrue(
                input_id and input_id in parser.labels,
                f"Missing explicit <label for='...'> matching input id='{input_id}' (attrs: {inp})",
            )

        for sel in parser.selects:
            select_id: str = sel.get("id", "").strip()
            self.assertTrue(
                select_id and select_id in parser.labels,
                f"Missing explicit <label for='...'> matching select id='{select_id}' (attrs: {sel})",
            )

    def test_15_app_js_static_contracts(self) -> None:
        """
        Validate app.js static contracts, ES module imports, required tokens, and delimiter balance.

        Pre-conditions:
            - src/dashboard/static/app.js exists.
        Post-conditions:
            - Balanced delimiters, valid imports, and all required tokens present.
        """
        app_js_path: Path = self.base_dir / "src" / "dashboard" / "static" / "app.js"
        self.assertTrue(app_js_path.exists(), "src/dashboard/static/app.js must exist")

        content: str = app_js_path.read_text(encoding="utf-8")

        # 1. Delimiter balance verification
        parser = BalancedDelimiterParser(content)
        is_balanced, errors = parser.parse()
        self.assertTrue(
            is_balanced,
            f"app.js syntax delimiters are not balanced: {errors}",
        )

        # 2. Imports verification (strictly from ./views.js and ./charts.js)
        import_statements: List[str] = re.findall(r"from\s+['\"]([^'\"]+)['\"]", content)
        for imp in import_statements:
            self.assertIn(
                imp,
                ("./views.js", "./charts.js"),
                f"app.js must only import from ./views.js and ./charts.js, but imports from '{imp}'",
            )

        # 3. Required tokens and contracts
        required_tokens: List[str] = [
            "car_researcher_compare_pins",
            "ArrowLeft",
            "ArrowRight",
            "Escape",
            "2000",
            "DOMContentLoaded",
            "window.setFilterTab",
            "window.toggleViewMode",
            "window.openModal",
            "window.closeModal",
        ]
        for token in required_tokens:
            self.assertIn(
                token,
                content,
                f"Required token '{token}' must be present in app.js",
            )

        # 4. Design by Contract docstrings
        self.assertIn("Pre-conditions:", content)
        self.assertIn("Post-conditions:", content)


if __name__ == "__main__":
    unittest.main()
