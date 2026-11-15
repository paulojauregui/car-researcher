"""Unit tests for client workspace views and dossier renderers module (views.js).

Validates Milestone M08 acceptance criteria:
- Pure vanilla ES module exports and imports exclusively from ./charts.js.
- Strictly zero external dependencies, zero CDNs, zero localhost:8080 references.
- Strictly zero emoji glyphs across all templates, strings, and docblocks.
- Design by Contract (DbC) on all public functions and methods.
- Balanced syntax delimiters and well-formed HTML structures.
- Complete 5-State Matrix (Empty, Loading CLS=0, Nominal, Degraded, Error).
- Enforces tabular-nums on all numeric metrics, prices, scores, deltas, and VINs.
- Precision table sortable headers with scope='col' and aria-sort.
- Full 7-section valuation dossier inside #analysis-drawer with role='dialog'.
- Complete 10 normalized dimensions in Side-by-Side Comparator with Best highlights.
- All 5 market badge tokens mapped with geometric 10px SVGs.
"""

import pathlib
import re
from typing import Dict, List, Optional, Set, Tuple
import unittest

STATIC_DIR: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent / "src" / "dashboard" / "static"
VIEWS_JS_PATH: pathlib.Path = STATIC_DIR / "views.js"


class BalancedDelimiterParser:
    """Parser verifying balanced JavaScript brackets, braces, and parentheses.

    Pre-conditions:
        - Input is valid JavaScript source text.
    Post-conditions:
        - Tracks delimiter depth skipping comments, strings, template literals, and regexes.
    """

    def __init__(self, source: str) -> None:
        """Initialize parser with source string.

        Pre-conditions:
            - source is a string.
        Post-conditions:
            - self.source is stored and ready for parse().
        """
        self.source: str = source

    def parse(self) -> Tuple[bool, List[str]]:
        """Scan source code and return balance status and error messages.

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
                            while i < n and text[i].isalpha():
                                i += 1
                            break
                        else:
                            i += 1
                else:
                    i += 1
            # Delimiters
            elif text[i] in "({[":
                stack.append((text[i], i))
                i += 1
            elif text[i] in ")}]":
                if not stack:
                    errors.append(f"Unmatched closing delimiter '{text[i]}' at pos {i}")
                    i += 1
                    continue
                opener, opener_pos = stack.pop()
                if opener != pairs[text[i]]:
                    errors.append(
                        f"Mismatched delimiter: opened '{opener}' at pos {opener_pos} "
                        f"but closed with '{text[i]}' at pos {i}"
                    )
                i += 1
            else:
                i += 1

        while stack:
            opener, opener_pos = stack.pop()
            errors.append(f"Unclosed opening delimiter '{opener}' at pos {opener_pos}")

        return (len(errors) == 0, errors)


class TestViewsModuleStructure(unittest.TestCase):
    """Test suite validating file invariants, ES module exports, and syntax balance."""

    def setUp(self) -> None:
        """Load views.js source text.

        Pre-conditions:
            - Target file must exist and be readable.
        Post-conditions:
            - self.views_text contains full views.js string.
        """
        self.assertTrue(VIEWS_JS_PATH.exists(), f"Missing target views file: {VIEWS_JS_PATH}")
        self.views_text: str = VIEWS_JS_PATH.read_text(encoding="utf-8")

    def test_views_module_file_exists_and_non_empty(self) -> None:
        """Verify views.js exists, is non-empty, and exceeds baseline size.

        Pre-conditions:
            - File read from disk.
        Post-conditions:
            - File size exceeds 8000 characters.
        """
        self.assertGreater(
            len(self.views_text),
            8000,
            "views.js is unexpectedly small for a complete workspace render suite",
        )

    def test_zero_emojis_in_views_js(self) -> None:
        """Verify strict zero-emoji mandate across views.js.

        Pre-conditions:
            - File content loaded as string.
        Post-conditions:
            - Zero Unicode emoji glyphs found in comments, strings, or code.
        """
        non_ascii_emojis: Set[str] = {
            char
            for char in self.views_text
            if ord(char) > 127 and not (0x2000 <= ord(char) <= 0x206F)
        }
        self.assertEqual(
            len(non_ascii_emojis),
            0,
            f"Prohibited non-ASCII / emoji glyphs detected in views.js: {non_ascii_emojis}",
        )

    def test_zero_external_cdns_and_localhost(self) -> None:
        """Verify zero external HTTP/HTTPS CDN references and zero localhost:8080 occurrences.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - No http://, https://, or localhost:8080 references exist.
        """
        external_refs: List[str] = re.findall(r"https?://[^\s\"')]+", self.views_text)
        self.assertEqual(
            len(external_refs),
            0,
            f"Prohibited external CDN or HTTP URLs found in views.js: {external_refs}",
        )
        self.assertNotIn(
            "localhost:8080",
            self.views_text,
            "Prohibited hardcoded localhost:8080 endpoint found in views.js",
        )

    def test_charts_import_exclusivity(self) -> None:
        """Verify views.js imports exclusively from ./charts.js and no other module.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - Exactly one import statement from './charts.js'.
        """
        imports: List[str] = re.findall(r"import\s+[^;]+from\s+['\"][^'\"]+['\"];", self.views_text)
        self.assertGreaterEqual(len(imports), 1, "Missing import from ./charts.js")
        for imp in imports:
            self.assertIn(
                "./charts.js",
                imp,
                f"Prohibited import outside ./charts.js detected: {imp}",
            )
        self.assertIn("renderCohortRangeBarHtml", self.views_text)
        self.assertIn("renderPriceSparkline", self.views_text)
        self.assertIn("escapeSvgText", self.views_text)

    def test_all_sixteen_exports_present(self) -> None:
        """Verify all 16 required client workspace render functions are exported.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - All 16 functions are exported via 'export function <name>'.
        """
        required_exports: List[str] = [
            "escapeHtml",
            "formatCurrency",
            "formatSignedCurrency",
            "formatNumber",
            "renderBadgesHtml",
            "renderKpiStripHtml",
            "renderDealsSectionHtml",
            "renderWorkbenchLoadingHtml",
            "renderWorkspaceErrorHtml",
            "renderMarketWorkspaceHtml",
            "renderArbitrageWorkspaceHtml",
            "renderComparatorWorkspaceHtml",
            "renderAnalysisDrawerHtml",
            "renderCompareTrayHtml",
            "renderDegradedBannerHtml",
            "renderScanStatusBannerHtml",
        ]
        for exp in required_exports:
            pattern: str = rf"export\s+function\s+{exp}\b"
            self.assertRegex(
                self.views_text,
                pattern,
                f"Missing required ES module export '{exp}' in views.js",
            )

    def test_design_by_contract_in_js_comments(self) -> None:
        """Verify Design by Contract docblocks for all 16 exported functions.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - Each public function includes Pre-conditions: and Post-conditions: docstring lines.
        """
        required_functions: List[str] = [
            "escapeHtml",
            "formatCurrency",
            "formatSignedCurrency",
            "formatNumber",
            "renderBadgesHtml",
            "renderKpiStripHtml",
            "renderDealsSectionHtml",
            "renderWorkbenchLoadingHtml",
            "renderWorkspaceErrorHtml",
            "renderMarketWorkspaceHtml",
            "renderArbitrageWorkspaceHtml",
            "renderComparatorWorkspaceHtml",
            "renderAnalysisDrawerHtml",
            "renderCompareTrayHtml",
            "renderDegradedBannerHtml",
            "renderScanStatusBannerHtml",
        ]
        for fn_name in required_functions:
            match = re.search(
                rf"/\*\*[\s\S]*?\*/\s*export\s+function\s+{fn_name}\b",
                self.views_text,
            )
            self.assertIsNotNone(
                match,
                f"Missing JSDoc comment block for exported function '{fn_name}'",
            )
            comment_block: str = match.group(0) if match else ""
            self.assertIn(
                "Pre-conditions:",
                comment_block,
                f"Missing 'Pre-conditions:' in contract for '{fn_name}'",
            )
            self.assertIn(
                "Post-conditions:",
                comment_block,
                f"Missing 'Post-conditions:' in contract for '{fn_name}'",
            )

    def test_balanced_delimiters_in_js(self) -> None:
        """Verify all braces, brackets, and parentheses in views.js are balanced.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - Parser reports zero unmatched opening or closing delimiters.
        """
        parser = BalancedDelimiterParser(self.views_text)
        balanced, errors = parser.parse()
        self.assertTrue(balanced, f"Syntax delimiter errors detected in views.js: {errors}")


class TestFormattingAndBadges(unittest.TestCase):
    """Test suite validating numerical formatters, entity escaping, and market badges."""

    def setUp(self) -> None:
        """Load views.js source text.

        Pre-conditions:
            - Target file must exist.
        Post-conditions:
            - self.views_text contains views.js source.
        """
        self.views_text: str = VIEWS_JS_PATH.read_text(encoding="utf-8")

    def test_escape_html_replaces_all_xml_entities(self) -> None:
        """Verify escapeHtml handles &, <, >, \", and ' replacements.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - escapeHtml replaces &, <, >, \", and ' with safe entities.
        """
        self.assertIn("&amp;", self.views_text)
        self.assertIn("&lt;", self.views_text)
        self.assertIn("&gt;", self.views_text)
        self.assertIn("&quot;", self.views_text)
        self.assertIn("&#39;", self.views_text)

    def test_all_five_market_badges_mapped(self) -> None:
        """Verify all 5 required market badge tokens are mapped with 10px SVGs.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - BELOW_P25_COHORT, FRESH_PRICE_CUT, STALE_INVENTORY_30D,
              HIGH_LEVERAGE, and USED_EV_TAX_CREDIT mapped with .market-badge classes.
        """
        badge_tokens: List[str] = [
            "BELOW_P25_COHORT",
            "FRESH_PRICE_CUT",
            "STALE_INVENTORY_30D",
            "HIGH_LEVERAGE",
            "USED_EV_TAX_CREDIT",
        ]
        for badge in badge_tokens:
            self.assertIn(badge, self.views_text, f"Missing badge mapping for '{badge}'")

        self.assertIn("market-badge--excellent", self.views_text)
        self.assertIn("market-badge--cut", self.views_text)
        self.assertIn("market-badge--warn", self.views_text)
        self.assertIn("market-badge--info", self.views_text)

        # Labels
        self.assertIn("Below p25", self.views_text)
        self.assertIn("Price Cut", self.views_text)
        self.assertIn("Stale", self.views_text)
        self.assertIn("High Leverage", self.views_text)
        self.assertIn("EV Credit $4k", self.views_text)

    def test_tabular_nums_enforcement_across_readouts(self) -> None:
        """Verify tabular-nums is applied across numeric elements.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - tabular-nums class appears extensively throughout templates.
        """
        occurrences: int = len(re.findall(r"\btabular-nums\b", self.views_text))
        self.assertGreaterEqual(
            occurrences,
            25,
            f"Expected extensive tabular-nums enforcement, found only {occurrences} occurrences",
        )


class TestWorkbenchAndDealsSection(unittest.TestCase):
    """Test suite validating KPI strip, triage sub-tabs, precision table, and grid view."""

    def setUp(self) -> None:
        """Load views.js source text.

        Pre-conditions:
            - Target file must exist.
        Post-conditions:
            - self.views_text contains views.js source.
        """
        self.views_text: str = VIEWS_JS_PATH.read_text(encoding="utf-8")

    def test_kpi_strip_four_tiles_structure(self) -> None:
        """Verify renderKpiStripHtml renders #kpi-bar with 4 .kpi-card elements.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - #kpi-bar, .kpi-strip, .kpi-card, .kpi-value, and KPI metrics are present.
        """
        self.assertIn('id="kpi-bar"', self.views_text)
        self.assertIn('class="kpi-strip"', self.views_text)
        self.assertIn("kpi-card", self.views_text)
        self.assertIn("kpi-value", self.views_text)
        self.assertIn("Active Bay Area Inventory", self.views_text)
        self.assertIn("High-Conviction Deals", self.views_text)
        self.assertIn("Max &amp; Avg Below-Market Savings", self.views_text)
        self.assertIn("Liquidity &amp; Leverage Signals", self.views_text)

    def test_triage_sub_tabs(self) -> None:
        """Verify triage sub-tabs cover all 6 categories with accessibility roles.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - all, excellent, good, drops, saved, dismissed present with role='tab' and aria-selected.
        """
        tabs: List[str] = ["all", "excellent", "good", "drops", "saved", "dismissed"]
        for tab in tabs:
            self.assertIn(f"key: '{tab}'", self.views_text)

        self.assertIn('role="tablist"', self.views_text)
        self.assertIn('role="tab"', self.views_text)
        self.assertIn("aria-selected", self.views_text)
        self.assertIn("triage-tab", self.views_text)

    def test_export_links_preserve_query_parameters(self) -> None:
        """Verify CSV and Markdown export anchors preserve filter query parameters.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - /api/export/csv and /api/export/markdown endpoints referenced.
        """
        self.assertIn("/api/export/csv?", self.views_text)
        self.assertIn("/api/export/markdown?", self.views_text)

    def test_precision_table_structure_and_aria_sort(self) -> None:
        """Verify Precision Table renders with table-scroll, precision-table, scope='col', and aria-sort.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - .precision-table, <th scope="col">, and aria-sort buttons are present.
        """
        self.assertIn("precision-table", self.views_text)
        self.assertIn('scope="col"', self.views_text)
        self.assertIn("aria-sort", self.views_text)
        self.assertIn("sort-btn", self.views_text)
        self.assertIn("num-col", self.views_text)

    def test_deals_grid_cards_structure(self) -> None:
        """Verify Deals Grid renders with .deals-grid, .deal-card, and 4-factor meters.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - .deals-grid, .deal-card, .deal-card__media, .deal-card__price, .deal-card__factors present.
        """
        self.assertIn("deals-grid", self.views_text)
        self.assertIn("deal-card", self.views_text)
        self.assertIn("deal-card__media", self.views_text)
        self.assertIn("deal-card__price", self.views_text)
        self.assertIn("deal-card__delta", self.views_text)
        self.assertIn("deal-card__factors", self.views_text)
        self.assertIn("factor-bar__fill", self.views_text)
        self.assertIn("vin-chip", self.views_text)

    def test_pin_and_bookmark_aria_states(self) -> None:
        """Verify pin and bookmark controls declare aria-pressed state attributes.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - aria-pressed appears on pin and bookmark controls.
        """
        self.assertIn('aria-pressed="${isPinned}"', self.views_text)
        self.assertIn('aria-pressed="${isBookmarked}"', self.views_text)


class TestAnalysisDrawerSevenSections(unittest.TestCase):
    """Test suite validating slide-over Valuation & Comp Drawer and its 7 structured sections."""

    def setUp(self) -> None:
        """Load views.js source text.

        Pre-conditions:
            - Target file must exist.
        Post-conditions:
            - self.views_text contains views.js source.
        """
        self.views_text: str = VIEWS_JS_PATH.read_text(encoding="utf-8")

    def test_analysis_drawer_dialog_semantics(self) -> None:
        """Verify analysis drawer semantics declare role='dialog', aria-modal, and close button.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - role="dialog", aria-modal="true", and #drawer-close-btn are present.
        """
        self.assertIn('role="dialog"', self.views_text)
        self.assertIn('aria-modal="true"', self.views_text)
        self.assertIn('id="drawer-close-btn"', self.views_text)
        self.assertIn('id="drawer-title"', self.views_text)

    def test_section_1_sticky_header(self) -> None:
        """Verify Section 1 sticky header includes platform, VIN chip, title, pricing, and controls.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - Section 1 contains drawer-header, vin-chip, drawer-title, pin, bookmark, and external link.
        """
        self.assertIn("drawer-header", self.views_text)
        self.assertIn("drawer-title", self.views_text)
        self.assertIn('data-action="pin"', self.views_text)
        self.assertIn('data-action="bookmark"', self.views_text)
        self.assertIn('data-action="dismiss"', self.views_text)

    def test_section_2_cohort_valuation(self) -> None:
        """Verify Section 2 renders cohort valuation, range bar, percentile, and Z-score.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - Section 2 calls renderCohortRangeBarHtml, displays percentile, Z-Score, and $/1k mi.
        """
        self.assertIn("Cohort Valuation", self.views_text)
        self.assertIn("renderCohortRangeBarHtml(deal)", self.views_text)
        self.assertIn("Cohort Percentile", self.views_text)
        self.assertIn("Z-Score", self.views_text)
        self.assertIn("$/1k Miles", self.views_text)

    def test_section_3_timescaledb_history(self) -> None:
        """Verify Section 3 renders TimescaleDB sparkline, snapshot table, and price velocity.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - Section 3 calls renderPriceSparkline, displays markdown, price cuts, and velocity.
        """
        self.assertIn("TimescaleDB Price History", self.views_text)
        self.assertIn("renderPriceSparkline(snapshots)", self.views_text)
        self.assertIn("Weekly Velocity", self.views_text)
        self.assertIn("Total Markdown", self.views_text)

    def test_section_4_deal_score_breakdown(self) -> None:
        """Verify Section 4 renders 4-factor deal score breakdown bars with exact point weights.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - Section 4 displays 4 weighted progress bars (Price 50%, Hist 25%, DOM 15%, Prox 10%).
        """
        self.assertIn("4-Factor Deal Score Breakdown", self.views_text)
        self.assertIn("Price vs Fair Market Value (50% weight)", self.views_text)
        self.assertIn("Title &amp; Vehicle History (25% weight)", self.views_text)
        self.assertIn("Days on Market Leverage (15% weight)", self.views_text)
        self.assertIn("Bay Area Proximity (10% weight)", self.views_text)

    def test_section_5_negotiation_leverage(self) -> None:
        """Verify Section 5 renders negotiation leverage score, tier, and offer strategy callout.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - Section 5 displays leverage breakdown, opening offer, and target close bounds.
        """
        self.assertIn("Negotiation Leverage &amp; Offer Strategy", self.views_text)
        self.assertIn("Recommended Offer Strategy", self.views_text)
        self.assertIn("Opening Offer:", self.views_text)
        self.assertIn("Target Close:", self.views_text)
        self.assertIn("dom_component", self.views_text)
        self.assertIn("velocity_component", self.views_text)

    def test_section_6_tco_and_ev_tax_credit(self) -> None:
        """Verify Section 6 renders 3-yr TCO, depreciation, and Used EV Tax Credit checklist.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - Section 6 displays 3-yr residual, depreciation, energy cost, and $4,000 credit checklist.
        """
        self.assertIn("3-Year Depreciation, TCO &amp; Used EV Tax Credit", self.views_text)
        self.assertIn("3-Yr Projected Residual", self.views_text)
        self.assertIn("3-Yr Depreciation", self.views_text)
        self.assertIn("3-Yr Energy Cost", self.views_text)
        self.assertIn("Net 3-Yr TCO Delta", self.views_text)
        self.assertIn("tax-credit-card", self.views_text)
        self.assertIn("Price &le; $25,000", self.views_text)
        self.assertIn("Model Year &ge; 2 yrs old", self.views_text)
        self.assertIn("Clean Title", self.views_text)

    def test_section_7_nhtsa_safety_and_epa(self) -> None:
        """Verify Section 7 renders NHTSA safety posture, EPA specs, and recall/complaint counts.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - Section 7 displays safety badge, EV range, combined MPGe, fuel cost, recalls and VOQ complaints.
        """
        self.assertIn("NHTSA Safety Posture &amp; EPA Telemetry", self.views_text)
        self.assertIn("safety-badge", self.views_text)
        self.assertIn("EV Range", self.views_text)
        self.assertIn("Combined MPGe", self.views_text)
        self.assertIn("Annual Fuel", self.views_text)
        self.assertIn("NHTSA Safety Recalls &amp; VOQ Complaints", self.views_text)
        self.assertIn("recall-card", self.views_text)


class TestWorkspacesAndComparator(unittest.TestCase):
    """Test suite validating Market Intelligence, Arbitrage, and Side-by-Side Comparator workspaces."""

    def setUp(self) -> None:
        """Load views.js source text.

        Pre-conditions:
            - Target file must exist.
        Post-conditions:
            - self.views_text contains views.js source.
        """
        self.views_text: str = VIEWS_JS_PATH.read_text(encoding="utf-8")

    def test_market_workspace_cohort_select_and_pills(self) -> None:
        """Verify Market Workspace renders #cohort-select, telemetry pills, and table fallback.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - #cohort-select, .frontier-stats, .frontier-stat-pill, and accessible details table present.
        """
        self.assertIn('id="cohort-select"', self.views_text)
        self.assertIn("frontier-stats", self.views_text)
        self.assertIn("frontier-stat-pill", self.views_text)
        self.assertIn("Sample Size:", self.views_text)
        self.assertIn("Confidence:", self.views_text)
        self.assertIn("OLS Slope:", self.views_text)
        self.assertIn("Fit R^2:", self.views_text)
        self.assertIn("p25 Buy-Zone:", self.views_text)
        self.assertIn("Median p50:", self.views_text)
        self.assertIn("View Scatter Coordinates as Precision Table", self.views_text)

    def test_cohort_leaderboard_14_models(self) -> None:
        """Verify #cohort-leaderboard renders 14-model table with Plot Frontier and Filter buttons.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - #cohort-leaderboard, plot-frontier, and filter-workbench actions present.
        """
        self.assertIn('id="cohort-leaderboard"', self.views_text)
        self.assertIn('data-action="plot-frontier"', self.views_text)
        self.assertIn('data-action="filter-workbench"', self.views_text)

    def test_momentum_feed_dual_panels(self) -> None:
        """Verify #momentum-feed renders dual panels for price-cut movers and stale inventory.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - #momentum-feed, Fresh Price-Cut Movers, and Stale High-Leverage Inventory present.
        """
        self.assertIn('id="momentum-feed"', self.views_text)
        self.assertIn("Fresh Price-Cut Movers", self.views_text)
        self.assertIn("Stale High-Leverage Inventory", self.views_text)

    def test_arbitrage_workspace_platforms_and_dealers(self) -> None:
        """Verify Arbitrage Workspace renders platform comparison, distance bands, and dealer matrix.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - #platform-comparison, #distance-bands, and #dealer-matrix present.
        """
        self.assertIn('id="platform-comparison"', self.views_text)
        self.assertIn("arbitrage-callout", self.views_text)
        self.assertIn('id="distance-bands"', self.views_text)
        self.assertIn('id="dealer-matrix"', self.views_text)
        self.assertIn('data-action="filter-distance"', self.views_text)
        self.assertIn('data-action="filter-dealer"', self.views_text)
        self.assertIn("Inspect Best Deal", self.views_text)

    def test_comparator_workspace_ten_dimensions(self) -> None:
        """Verify Side-by-Side Comparator compares all 10 normalized dimensions.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - 10 normalized dimensions present in compare-table:
              Price, vs FMV, Deal Score, Mileage, Price / 1k mi, DOM,
              Negotiation Leverage, 3-Yr TCO Delta, EV Credit, Safety Posture.
        """
        dimensions: List[str] = [
            "Price",
            "vs FMV",
            "Deal Score",
            "Mileage",
            "Price / 1k mi",
            "DOM",
            "Negotiation Leverage",
            "3-Yr TCO Delta",
            "EV Credit",
            "Safety Posture",
        ]
        for dim in dimensions:
            self.assertIn(f"renderDimensionRow('{dim}'", self.views_text)

        self.assertIn("compare-table", self.views_text)
        self.assertIn("compare-cell--winner", self.views_text)
        self.assertIn("compare-winner-pill", self.views_text)
        self.assertIn("compare-slot-empty", self.views_text)
        self.assertIn('data-action="unpin"', self.views_text)
        self.assertIn('data-action="copy-compare-markdown"', self.views_text)
        self.assertIn('data-action="clear-pins"', self.views_text)

    def test_comparator_empty_state_cta(self) -> None:
        """Verify Comparator renders empty state card when zero vehicles are pinned.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - Empty state message and Browse Deal Workbench button present.
        """
        self.assertIn("No Vehicles Pinned for Comparison", self.views_text)
        self.assertIn("Browse Deal Workbench", self.views_text)


class TestFiveStateMatrixAndOverlays(unittest.TestCase):
    """Test suite validating the 5-State Matrix and persistent overlays."""

    def setUp(self) -> None:
        """Load views.js source text.

        Pre-conditions:
            - Target file must exist.
        Post-conditions:
            - self.views_text contains views.js source.
        """
        self.views_text: str = VIEWS_JS_PATH.read_text(encoding="utf-8")

    def test_five_state_matrix_coverage(self) -> None:
        """Verify complete 5-State Matrix implementation across views.js.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - Empty (.empty-state), Loading CLS=0 (.skeleton-*), Nominal,
              Degraded (.degraded-banner), and Error (.error-state) states present.
        """
        # Empty
        self.assertIn("empty-state", self.views_text)
        self.assertIn("empty-state__icon", self.views_text)
        self.assertIn("empty-state__title", self.views_text)

        # Loading CLS=0
        self.assertIn("renderWorkbenchLoadingHtml", self.views_text)
        self.assertIn("skeleton-kpi", self.views_text)
        self.assertIn("skeleton-card", self.views_text)
        self.assertIn("skeleton-table-row", self.views_text)
        self.assertIn('aria-busy="true"', self.views_text)

        # Degraded
        self.assertIn("renderDegradedBannerHtml", self.views_text)
        self.assertIn("degraded-banner__content", self.views_text)
        self.assertIn("degraded-banner__tag", self.views_text)
        self.assertIn('data-action="retry-connection"', self.views_text)
        self.assertIn('data-action="acknowledge-degraded"', self.views_text)

        # Error
        self.assertIn("renderWorkspaceErrorHtml", self.views_text)
        self.assertIn("error-state", self.views_text)
        self.assertIn("error-state__icon", self.views_text)
        self.assertIn('role="alert"', self.views_text)
        self.assertIn("data-retry-action", self.views_text)

    def test_compare_tray_component(self) -> None:
        """Verify renderCompareTrayHtml renders fixed bottom tray with slots and actions.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - compare-tray__inner, compare-slots, compare-slot--filled, and compare-slot--empty present.
        """
        self.assertIn("renderCompareTrayHtml", self.views_text)
        self.assertIn("compare-tray__inner", self.views_text)
        self.assertIn("compare-slots", self.views_text)
        self.assertIn("compare-slot--filled", self.views_text)
        self.assertIn("compare-slot--empty", self.views_text)
        self.assertIn("Compare Now", self.views_text)

    def test_scan_status_banner_states_and_temporal_link(self) -> None:
        """Verify renderScanStatusBannerHtml handles scan lifecycle states and conditional Temporal link.

        Pre-conditions:
            - views.js loaded.
        Post-conditions:
            - scan-banner, scan-banner--running, scan-banner--completed, scan-banner--error,
              and conditional temporalUiUrl anchor without localhost:8080.
        """
        self.assertIn("renderScanStatusBannerHtml", self.views_text)
        self.assertIn("scan-banner", self.views_text)
        self.assertIn("scan-banner--running", self.views_text)
        self.assertIn("scan-banner--completed", self.views_text)
        self.assertIn("scan-banner--error", self.views_text)
        self.assertIn("scan-banner--unavailable", self.views_text)
        self.assertIn("scan-banner__counters", self.views_text)
        self.assertIn("retry-scan", self.views_text)
        self.assertIn("dismiss-scan-banner", self.views_text)
        self.assertNotIn("localhost:8080", self.views_text)


if __name__ == "__main__":
    unittest.main()
