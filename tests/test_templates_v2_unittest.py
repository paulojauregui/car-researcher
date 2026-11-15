"""
Milestone M06 Unit Tests: Semantic HTML5 Shell & Modular SSR Renderer.

Pre-conditions:
    - Standard library unittest execution with zero external dependencies.
    - src/dashboard/templates/index.html and src/dashboard/templates.py are readable.
    - Design by Contract docstrings and static typing throughout.

Post-conditions:
    - Validates 100% of Milestone M06 acceptance criteria:
      1. Zero emojis, zero external CDN links, zero hardcoded default cluster ports.
      2. Complete semantic HTML5 landmarks and UX spec IDs.
      3. Explicit <label for="..."> for every visible input and select.
      4. Safe </script> escaping in initial-state script tag.
      5. Conditional TEMPORAL_UI_URL rendering.
      6. Deal Workbench grid and precision-table view parity.
      7. Degraded banner nominal and offline-sample states.
      8. History modal, model profile modal, and scan banner polling contracts.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List
import unittest

from src.config.settings import settings
from src.dashboard.templates import (
    render_degraded_banner,
    render_deals_section,
    render_full_dashboard_page,
    render_kpis_partial,
    render_listing_history_modal,
    render_model_profile_modal,
    render_scan_status_banner,
)


def _sample_deals() -> List[Dict[str, Any]]:
    """
    Construct a deterministic deal fixture list for template testing.

    Pre-conditions:
        - None.

    Post-conditions:
        - Returns a list of 2 deal dictionaries with all required fields.
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
            "thumbnail": "https://images.cars.com/phototab/1.jpg",
            "raw_data": {"make": "Mercedes-Benz", "model": "EQS", "year": 2023},
            "market_value": 52778,
            "price_delta": -12790,
            "pct_savings": 24.2,
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
            "is_bookmarked": True,
            "is_dismissed": False,
            "cpo": True,
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
            "thumbnail": None,
            "raw_data": {"make": "Mercedes-Benz", "model": "EQS", "year": 2023},
            "market_value": 63522,
            "price_delta": -12527,
            "pct_savings": 19.7,
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
            "is_bookmarked": False,
            "is_dismissed": False,
            "cpo": False,
        },
    ]


def _sample_kpis() -> Dict[str, Any]:
    """
    Construct a deterministic KPI dictionary for template testing.

    Pre-conditions:
        - None.

    Post-conditions:
        - Returns a dictionary with summary metrics.
    """
    return {
        "total_active": 24,
        "excellent_count": 8,
        "good_count": 10,
        "price_drops_count": 4,
        "saved_count": 2,
        "dismissed_count": 1,
        "max_savings": 14500,
        "avg_discount": 5200,
        "below_p25_count": 7,
        "high_leverage_count": 6,
        "tax_credit_eligible_count": 3,
        "avg_msrp_discount_pct": 46.2,
        "avg_dom": 22.4,
    }


class TestTemplatesV2Unit(unittest.TestCase):
    """
    Test suite verifying Milestone M06 HTML templates and SSR renderers.

    Pre-conditions:
        - Templates modules are present.

    Post-conditions:
        - All assertions pass without external network access or pip packages.
    """

    def setUp(self) -> None:
        """Store initial settings for restoration after test execution."""
        self._orig_temporal_ui = getattr(settings, "temporal_ui_url", None)

    def tearDown(self) -> None:
        """Restore original settings."""
        settings.temporal_ui_url = self._orig_temporal_ui

    def test_source_code_invariants(self) -> None:
        """
        Verify that index.html, templates.py, and this test file have zero emojis,
        zero external CDN links, and zero hardcoded default cluster host strings.

        Pre-conditions:
            - Files exist and are readable as UTF-8 text.

        Post-conditions:
            - Non-ASCII character count is 0 in all files.
            - Forbidden host strings do not appear anywhere.
            - External CDNs (tailwindcss, htmx.org) do not appear.
        """
        base_dir = Path(__file__).resolve().parent.parent / "src" / "dashboard"
        files_to_check = [
            base_dir / "templates" / "index.html",
            base_dir / "templates.py",
            Path(__file__).resolve(),
        ]

        for file_path in files_to_check:
            self.assertTrue(file_path.is_file(), f"Missing file: {file_path}")
            content = file_path.read_text(encoding="utf-8")

            # Invariant 1: Zero non-ASCII characters (strictly zero emojis)
            non_ascii = [c for c in content if ord(c) > 127]
            self.assertEqual(
                len(non_ascii),
                0,
                f"Found {len(non_ascii)} non-ASCII characters in {file_path.name}: {set(non_ascii)}",
            )

        # Invariant 2: Zero hardcoded cluster port in production files
        forbidden_host = "localhost:" + "8080"
        for file_path in files_to_check[:2]:
            content = file_path.read_text(encoding="utf-8")
            self.assertNotIn(
                forbidden_host,
                content,
                f"Found forbidden {forbidden_host} in {file_path.name}",
            )

        # Invariant 3: Zero external CDNs in index.html and templates.py
        for file_path in files_to_check[:2]:
            content = file_path.read_text(encoding="utf-8")
            self.assertNotIn("cdn.tailwindcss.com", content)
            self.assertNotIn("unpkg.com/htmx.org", content)

    def test_semantic_landmarks_and_ids(self) -> None:
        """
        Verify that render_full_dashboard_page produces all required semantic landmarks
        and UX specification element IDs.

        Pre-conditions:
            - Sample deals and KPI dictionaries are available.

        Post-conditions:
            - All documented HTML5 landmarks and container IDs are present in the output.
        """
        rendered = render_full_dashboard_page(_sample_deals(), _sample_kpis(), {})

        required_ids = [
            "live-announcer",
            "console-header",
            "provenance-badge",
            "scan-trigger-form",
            "scan-target-select",
            "scan-submit-btn",
            "tab-workbench",
            "tab-market",
            "tab-arbitrage",
            "tab-compare",
            "compare-tab-badge",
            "main-content",
            "degraded-banner",
            "scan-status-banner",
            "workspace-workbench",
            "filter-form",
            "tab-input",
            "view-input",
            "search-input",
            "make-select",
            "max-price-select",
            "max-mileage-select",
            "max-distance-select",
            "sort-select",
            "view-grid-btn",
            "view-table-btn",
            "reset-filters-btn",
            "deals-container",
            "workspace-market",
            "cohort-select",
            "frontier-stats",
            "frontier-chart",
            "frontier-svg",
            "frontier-tooltip",
            "cohort-leaderboard",
            "momentum-feed",
            "workspace-arbitrage",
            "platform-comparison",
            "distance-bands",
            "dealer-matrix",
            "workspace-compare",
            "compare-matrix-container",
            "compare-tray",
            "analysis-drawer",
            "drawer-backdrop",
            "drawer-close-btn",
            "drawer-body",
            "detail-modal",
            "modal-body",
            "initial-state",
        ]

        for elem_id in required_ids:
            self.assertIn(
                f'id="{elem_id}"',
                rendered,
                f"Required element ID id=\"{elem_id}\" missing from rendered dashboard page",
            )

        # Semantic landmarks
        self.assertIn('<a class="skip-link" href="#main-content">Skip to main content</a>', rendered)
        self.assertIn('<header id="console-header"', rendered)
        self.assertIn('<nav class="workspace-nav"', rendered)
        self.assertIn('<main id="main-content"', rendered)
        self.assertIn('<footer role="contentinfo"', rendered)

    def test_explicit_form_labels(self) -> None:
        """
        Verify that every visible <input> and <select> across the rendered HTML5 shell
        has an explicit, matching <label for="..."> element (WCAG 2.2 AA).

        Pre-conditions:
            - Rendered full dashboard HTML.

        Post-conditions:
            - Every input with type != 'hidden' and every select matches an existing label.
        """
        rendered = render_full_dashboard_page(_sample_deals(), _sample_kpis(), {})

        # Extract all <label for="..."> attributes
        label_for_targets = set(re.findall(r'<label[^>]+for=["\']([^"\']+)["\']', rendered))

        # Check all non-hidden <input> elements
        input_matches = re.findall(r'<input\s+([^>]+)>', rendered)
        for input_attrs in input_matches:
            type_match = re.search(r'type=["\']([^"\']+)["\']', input_attrs)
            input_type = type_match.group(1) if type_match else "text"
            if input_type == "hidden":
                continue

            id_match = re.search(r'id=["\']([^"\']+)["\']', input_attrs)
            self.assertIsNotNone(id_match, f"Visible input missing id attribute: {input_attrs}")
            input_id = id_match.group(1)
            self.assertIn(
                input_id,
                label_for_targets,
                f"Visible input id=\"{input_id}\" has no matching <label for=\"{input_id}\">",
            )

        # Check all <select> elements
        select_matches = re.findall(r'<select\s+([^>]+)>', rendered)
        for select_attrs in select_matches:
            id_match = re.search(r'id=["\']([^"\']+)["\']', select_attrs)
            self.assertIsNotNone(id_match, f"Select missing id attribute: {select_attrs}")
            select_id = id_match.group(1)
            self.assertIn(
                select_id,
                label_for_targets,
                f"Select id=\"{select_id}\" has no matching <label for=\"{select_id}\">",
            )

    def test_safe_initial_state_escaping(self) -> None:
        """
        Verify that embedded JSON in <script id="initial-state"> safely escapes
        </script> sequences so malicious listing titles cannot break script tags.

        Pre-conditions:
            - Listing title containing '</script><script>alert(1)</script>'.

        Post-conditions:
            - Rendered initial-state script tag does not contain raw '</script>'.
            - The JSON parses back correctly when JSON-decoded.
        """
        malicious_deals = [
            {
                "id": "xss-test-01",
                "vin": "12345678901234567",
                "title": "2023 Tesla Model 3 </script><script>alert('xss')</script>",
                "price": 25000,
                "market_value": 30000,
                "price_delta": -5000,
                "pct_savings": 16.7,
                "deal_score": 88.0,
                "recommendation": "Great Deal",
                "mileage": 10000,
                "days_on_market": 4,
                "score_breakdown": {},
            }
        ]
        rendered = render_full_dashboard_page(malicious_deals, _sample_kpis(), {})

        # Extract the content between <script id="initial-state" ...> and </script>
        script_pattern = r'<script id="initial-state"[^>]*>(.*?)</script>'
        match = re.search(script_pattern, rendered, re.DOTALL)
        self.assertIsNotNone(match, "initial-state script tag not found")
        script_content = match.group(1)

        # Invariant: Must NOT contain raw unescaped </script> inside script_content
        self.assertNotIn("</script>", script_content)
        self.assertIn(r"<\/script>", script_content)

        # The JSON payload must parse successfully
        parsed = json.loads(script_content)
        self.assertEqual(len(parsed["deals"]), 1)
        self.assertEqual(
            parsed["deals"][0]["title"],
            "2023 Tesla Model 3 </script><script>alert('xss')</script>",
        )

    def test_temporal_ui_url_conditional_rendering(self) -> None:
        """
        Verify that TEMPORAL_UI_URL is conditionally rendered in the header and scan banner
        only when explicitly configured in settings, with zero hardcoded ports.

        Pre-conditions:
            - Toggle settings.temporal_ui_url between None, empty string, and a valid URL.

        Post-conditions:
            - When None or empty, no external Temporal UI anchor is rendered.
            - When configured, safe rel="noopener noreferrer" anchor is rendered.
        """
        # Case 1: None / unset
        settings.temporal_ui_url = None
        page_none = render_full_dashboard_page(_sample_deals(), _sample_kpis(), {})
        self.assertNotIn("Temporal UI &rarr;", page_none)
        self.assertNotIn("Inspect in Temporal UI", page_none)

        banner_none = render_scan_status_banner("wf-1", {"is_completed": False, "total_scraped": 5})
        self.assertNotIn("Inspect in Temporal UI", banner_none)

        # Case 2: Configured URL
        settings.temporal_ui_url = "https://temporal.paulojauregui.com"
        page_url = render_full_dashboard_page(_sample_deals(), _sample_kpis(), {})
        self.assertIn("https://temporal.paulojauregui.com", page_url)
        self.assertIn('rel="noopener noreferrer"', page_url)

        banner_running = render_scan_status_banner("wf-42", {"is_completed": False, "total_scraped": 12})
        self.assertIn("https://temporal.paulojauregui.com/namespaces/default/workflows/wf-42", banner_running)

        banner_done = render_scan_status_banner("wf-42", {"is_completed": True, "total_scraped": 24, "total_scored": 24})
        self.assertIn("https://temporal.paulojauregui.com/namespaces/default/workflows/wf-42", banner_done)

    def test_deals_section_grid_table_and_empty_views(self) -> None:
        """
        Verify render_deals_section properly outputs card grid, precision table,
        and empty state based on filters['view'] and deals content.

        Pre-conditions:
            - Sample deals and KPI dictionaries.

        Post-conditions:
            - view=grid renders .deals-grid and .deal-card elements.
            - view=table renders .precision-table with table columns.
            - deals=[] renders .empty-state markup with relaxation message.
        """
        deals = _sample_deals()
        kpis = _sample_kpis()

        # Grid view (default)
        grid_html = render_deals_section(deals, kpis, {"view": "grid"})
        self.assertIn('<div class="deals-grid">', grid_html)
        self.assertIn('<article class="deal-card"', grid_html)
        self.assertIn("W1KCG2DB6PA043095", grid_html)
        self.assertIn("2023 Mercedes-Benz EQS 450+ Base", grid_html)

        # Table view
        table_html = render_deals_section(deals, kpis, {"view": "table"})
        self.assertIn('<table class="precision-table">', table_html)
        self.assertIn("2023 Mercedes-Benz EQS 450+ Base", table_html)
        self.assertIn("W1KCG2DB6PA043095", table_html)

        # Empty view
        empty_html = render_deals_section([], kpis, {})
        self.assertIn('<div class="empty-state">', empty_html)
        self.assertIn("No matching vehicles found", empty_html)

        # Subtab active state selection
        drops_html = render_deals_section(deals, kpis, {"tab": "drops"})
        self.assertIn('data-tab="drops" aria-selected="true"', drops_html)

    def test_degraded_banner_nominal_and_offline_states(self) -> None:
        """
        Verify render_degraded_banner produces a visible notice on offline-sample mode
        and a hidden banner on live timescaledb or fixture modes.

        Pre-conditions:
            - Provenance dictionaries representing offline vs live mode.

        Post-conditions:
            - offline-sample mode renders visible amber banner without hidden attribute.
            - timescaledb mode renders banner with hidden attribute.
        """
        # Offline sample mode: banner is visible
        offline_prov = {"mode": "offline-sample", "detail": "Cluster unreachable; serving sample listings."}
        banner_offline = render_degraded_banner(offline_prov)
        self.assertIn('id="degraded-banner"', banner_offline)
        self.assertIn("Degraded Mode / Offline Sample Data", banner_offline)
        self.assertNotIn(" hidden", banner_offline)

        # Live TimescaleDB mode: banner is hidden
        live_prov = {"mode": "timescaledb", "detail": "Live database connected."}
        banner_live = render_degraded_banner(live_prov)
        self.assertIn('id="degraded-banner"', banner_live)
        self.assertIn("hidden", banner_live)
        self.assertNotIn("Degraded Mode", banner_live)

        # None provenance: banner is hidden
        banner_none = render_degraded_banner(None)
        self.assertIn('id="degraded-banner"', banner_none)
        self.assertIn("hidden", banner_none)

    def test_modals_and_scan_banner_contracts(self) -> None:
        """
        Verify render_listing_history_modal, render_model_profile_modal, and
        render_scan_status_banner fulfill their required output contracts.

        Pre-conditions:
            - History data, profile data, and scan summary fixtures.

        Post-conditions:
            - History modal contains 'TimescaleDB Price Snapshots', VIN, price, and delta.
            - Model profile modal contains recalls, complaints, and EPA benchmarks.
            - Scan banner in running mode renders #active-scan-poller with 2s polling trigger.
        """
        # History modal
        history_data = {
            "deal": _sample_deals()[0],
            "snapshots": [
                {"time": "2026-10-20 04:00:00", "price": 39988, "price_change": -1500, "days_on_market": 12},
                {"time": "2026-10-18 04:00:00", "price": 41488, "price_change": 0, "days_on_market": 10},
            ],
        }
        hist_html = render_listing_history_modal(history_data)
        self.assertIn("TimescaleDB Price Snapshots", hist_html)
        self.assertIn("W1KCG2DB6PA043095", hist_html)
        self.assertIn("$39,988", hist_html)
        self.assertIn("-$1,500", hist_html)

        # Model profile modal
        profile_data = {
            "make": "Mercedes-Benz",
            "model": "EQS",
            "year": 2023,
            "recalls_count": 2,
            "complaints_count": 3,
            "fire_count": 0,
            "recalls": [
                {"campaign_number": "23V100", "component": "BATTERY", "summary": "Software glitch", "remedy": "Update"}
            ],
            "complaints": [
                {"odi_number": "1001", "component": "STEERING", "summary": "Vibration at high speed", "crash": False, "fire": False}
            ],
            "epa_specs": [
                {"range_miles": 350, "comb_mpge": 97, "annual_fuel_cost": 850}
            ],
        }
        prof_html = render_model_profile_modal(profile_data)
        self.assertIn("Mercedes-Benz", prof_html)
        self.assertIn("EQS", prof_html)
        self.assertIn("EPA Range &amp; Efficiency Benchmarks", prof_html)
        self.assertIn("350 mi", prof_html)
        self.assertIn("Campaign #23V100", prof_html)

        # Scan banner running mode
        running_html = render_scan_status_banner("scan-1234", {"is_completed": False, "total_scraped": 15, "total_scored": 5})
        self.assertIn('id="active-scan-poller"', running_html)
        self.assertIn('hx-get="/api/scan/scan-1234/status"', running_html)
        self.assertIn('hx-trigger="every 2s"', running_html)
        self.assertIn("scan-1234", running_html)

        # Scan banner completed mode
        done_html = render_scan_status_banner("scan-1234", {"is_completed": True, "total_scraped": 20, "total_scored": 20, "top_deals_count": 3})
        self.assertIn("Scan Completed (scan-1234)", done_html)
        self.assertIn('hx-get="/partials/deals"', done_html)


if __name__ == "__main__":
    unittest.main()
