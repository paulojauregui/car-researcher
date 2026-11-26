"""Unit tests for automotive telemetry dashboard design tokens and component CSS.

Enforces Milestone M05 acceptance criteria: design token contracts, zero hardcoded
hex colors in component layers, zero external CDN references, balanced braces,
strict tabular numerals enforcement, 5-state matrix, and zero emoji glyphs.
"""

import pathlib
import re
from typing import List, Set
import unittest

STATIC_DIR: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent / "src" / "dashboard" / "static"
TOKENS_CSS_PATH: pathlib.Path = STATIC_DIR / "tokens.css"
COMPONENTS_CSS_PATH: pathlib.Path = STATIC_DIR / "components.css"


class TestStaticAssetsUnittest(unittest.TestCase):
    """Test suite validating production CSS design tokens and component stylesheets.

    Pre-conditions:
        - tokens.css and components.css exist on disk under src/dashboard/static/.
    Post-conditions:
        - Verifies tokens, components, accessibility, zero hardcoded hex/rgba,
          balanced syntax, tabular numerals, and zero emoji glyphs.
    """

    def setUp(self) -> None:
        """Load CSS contents into test context.

        Pre-conditions:
            - Files must be readable as UTF-8 text.
        Post-conditions:
            - self.tokens_text and self.components_text contain full file contents.
        """
        self.assertTrue(TOKENS_CSS_PATH.exists(), f"Missing tokens file: {TOKENS_CSS_PATH}")
        self.assertTrue(COMPONENTS_CSS_PATH.exists(), f"Missing components file: {COMPONENTS_CSS_PATH}")
        self.tokens_text: str = TOKENS_CSS_PATH.read_text(encoding="utf-8")
        self.components_text: str = COMPONENTS_CSS_PATH.read_text(encoding="utf-8")

    def test_static_files_exist_and_non_empty(self) -> None:
        """Verify tokens.css and components.css exist and contain non-trivial CSS rules.

        Pre-conditions:
            - Target files are loaded from disk.
        Post-conditions:
            - File byte sizes exceed baseline thresholds (> 2000 bytes).
        """
        self.assertGreater(len(self.tokens_text), 2000, "tokens.css is unexpectedly small")
        self.assertGreater(len(self.components_text), 5000, "components.css is unexpectedly small")

    def test_zero_emojis_in_css_assets(self) -> None:
        """Verify strict zero-emoji mandate across all static CSS assets.

        Pre-conditions:
            - Stylesheet contents loaded.
        Post-conditions:
            - No Unicode pictographs/emojis exist in comments, strings, or selectors.
        """
        # Range check: emojis reside above ASCII and outside standard typographic punctuation
        for fname, text in [("tokens.css", self.tokens_text), ("components.css", self.components_text)]:
            non_ascii_emojis: Set[str] = {
                char
                for char in text
                if ord(char) > 127 and not (0x2000 <= ord(char) <= 0x206F)
            }
            self.assertEqual(
                len(non_ascii_emojis),
                0,
                f"Prohibited non-ASCII / emoji glyphs detected in {fname}: {non_ascii_emojis}",
            )

    def test_zero_external_cdn_references(self) -> None:
        """Verify zero external HTTP/HTTPS CDN scripts, fonts, or @import statements.

        Pre-conditions:
            - Stylesheet contents loaded.
        Post-conditions:
            - No http:// or https:// URLs exist inside the CSS files.
        """
        for fname, text in [("tokens.css", self.tokens_text), ("components.css", self.components_text)]:
            external_refs: List[str] = re.findall(r"https?://[^\s\"')]+", text)
            self.assertEqual(
                len(external_refs),
                0,
                f"Prohibited external CDN references in {fname}: {external_refs}",
            )
            self.assertNotIn("@import", text, f"Prohibited @import rule detected in {fname}")

    def test_zero_hardcoded_hex_colors_in_components(self) -> None:
        """Verify components.css consumes custom properties exclusively with zero hardcoded hex.

        Pre-conditions:
            - components.css loaded as string.
        Post-conditions:
            - No 3, 4, 6, or 8 digit hex color literals exist in components.css.
        """
        # Find potential hex matches
        matches: List[str] = re.findall(r"#[0-9a-fA-F]{3,8}\b", self.components_text)
        # Filter: valid DOM IDs (like #tab-workbench or #degraded-banner) are not hex colors
        hardcoded_hex: List[str] = [
            m for m in matches
            if len(m[1:]) in (3, 4, 6, 8) and all(c in "0123456789abcdefABCDEF" for c in m[1:])
        ]
        self.assertEqual(
            len(hardcoded_hex),
            0,
            f"Hardcoded hex colors prohibited in components.css: {hardcoded_hex}",
        )

    def test_zero_hardcoded_rgb_rgba_in_components(self) -> None:
        """Verify components.css does not contain hardcoded rgb() or rgba() color calls.

        Pre-conditions:
            - components.css loaded as string.
        Post-conditions:
            - No literal rgba(...) or rgb(...) calls exist in components.css.
        """
        rgba_calls: List[str] = re.findall(r"\brgba?\([^)]+\)", self.components_text)
        self.assertEqual(
            len(rgba_calls),
            0,
            f"Hardcoded rgba calls prohibited in components.css: {rgba_calls}",
        )

    def test_balanced_curly_braces(self) -> None:
        """Verify all CSS block opening braces match closing braces exactly.

        Pre-conditions:
            - tokens.css and components.css loaded.
        Post-conditions:
            - open brace count == close brace count for both files.
        """
        for fname, text in [("tokens.css", self.tokens_text), ("components.css", self.components_text)]:
            open_count: int = text.count("{")
            close_count: int = text.count("}")
            self.assertEqual(
                open_count,
                close_count,
                f"Mismatched curly braces in {fname}: {open_count} open vs {close_count} close",
            )
            self.assertGreater(open_count, 0, f"Expected non-zero rules in {fname}")

    def test_tokens_contract_coverage(self) -> None:
        """Verify tokens.css defines all required design token contract variables.

        Pre-conditions:
            - tokens.css loaded.
        Post-conditions:
            - Every canonical token from DESIGN_SYSTEM.md Section 2.2 is defined.
        """
        required_tokens: List[str] = [
            "--bg-canvas",
            "--bg-inset",
            "--bg-surface",
            "--bg-surface-hover",
            "--bg-elevated",
            "--bg-overlay",
            "--bg-glass",
            "--border-subtle",
            "--border-default",
            "--border-strong",
            "--border-focus",
            "--text-primary",
            "--text-secondary",
            "--text-muted",
            "--text-inverse",
            "--accent-primary",
            "--accent-primary-hover",
            "--accent-primary-bg",
            "--accent-telemetry",
            "--accent-telemetry-bg",
            "--status-excellent",
            "--status-excellent-bg",
            "--status-excellent-border",
            "--status-info",
            "--status-info-bg",
            "--status-info-border",
            "--status-cut",
            "--status-cut-bg",
            "--status-cut-border",
            "--status-warn",
            "--status-warn-bg",
            "--status-warn-border",
            "--status-danger",
            "--status-danger-bg",
            "--status-danger-border",
            "--font-sans",
            "--font-mono",
            "--text-2xs",
            "--text-xs",
            "--text-sm",
            "--text-base",
            "--text-lg",
            "--text-xl",
            "--text-2xl",
            "--space-1",
            "--space-2",
            "--space-3",
            "--space-4",
            "--space-5",
            "--space-6",
            "--space-8",
            "--space-10",
            "--space-12",
            "--radius-sm",
            "--radius-md",
            "--radius-lg",
            "--radius-pill",
            "--container-max",
            "--shadow-elevated",
            "--shadow-drawer",
            "--shadow-tray",
            "--z-base",
            "--z-sticky",
            "--z-tray",
            "--z-overlay",
            "--z-drawer",
            "--z-tooltip",
            "--ease-telemetry",
            "--duration-fast",
            "--duration-normal",
            "--duration-drawer",
            "--chart-ols",
            "--chart-p25",
            "--chart-p50",
            "--chart-gridline",
            "--chart-axis",
            "--chart-buyzone-bg",
            "--chart-node-excellent",
            "--chart-node-good",
            "--chart-node-fair",
            "--chart-node-overpriced",
        ]
        for token in required_tokens:
            self.assertIn(token, self.tokens_text, f"Mandatory token missing from tokens.css: {token}")

    def test_tabular_numerals_and_accessibility_utilities(self) -> None:
        """Verify tabular numeral rules, focus-visible outlines, and accessibility utilities.

        Pre-conditions:
            - tokens.css and components.css loaded.
        Post-conditions:
            - .tabular-nums, .mono-readout, .sr-only, .skip-link, and :focus-visible exist.
        """
        self.assertIn(".tabular-nums", self.tokens_text)
        self.assertIn("font-variant-numeric: tabular-nums", self.tokens_text)
        self.assertIn(".mono-readout", self.tokens_text)
        self.assertIn(".sr-only", self.tokens_text)
        self.assertIn(".skip-link", self.tokens_text)
        self.assertIn(":focus-visible", self.tokens_text)
        self.assertIn("outline: 2px solid var(--border-focus)", self.tokens_text)
        self.assertIn("overflow-x: clip", self.tokens_text)
        self.assertIn(".num-col", self.components_text)

    def test_topbar_and_navigation_selectors(self) -> None:
        """Verify topbar, console header, and workspace navigation tabs.

        Pre-conditions:
            - components.css loaded.
        Post-conditions:
            - Styles exist for .topbar, .console-header, all 4 tab IDs, and ARIA attributes.
        """
        required_selectors: List[str] = [
            ".topbar",
            ".console-header",
            "#console-header",
            ".brand-emblem",
            ".scope-chip",
            ".provenance-pill",
            "#tab-workbench",
            "#tab-market",
            "#tab-arbitrage",
            "#tab-compare",
            '.workspace-nav [role="tablist"]',
            '[role="tab"]',
            '[aria-selected="true"]',
            ".workspace-tab__count",
        ]
        for sel in required_selectors:
            self.assertIn(sel, self.components_text, f"Missing topbar/navigation selector: {sel}")

    def test_all_workspace_container_ids_present(self) -> None:
        """Verify all 4 analytical workspace panels are styled and support [hidden].

        Pre-conditions:
            - components.css loaded.
        Post-conditions:
            - IDs for workbench, market, arbitrage, and compare workspaces exist.
        """
        workspace_ids: List[str] = [
            "#workspace-workbench",
            "#workspace-market",
            "#workspace-arbitrage",
            "#workspace-compare",
        ]
        for wid in workspace_ids:
            self.assertIn(wid, self.components_text, f"Missing workspace container ID: {wid}")
            self.assertIn(f"{wid}[hidden]", self.components_text, f"Missing hidden selector for: {wid}")

    def test_banners_and_compare_tray(self) -> None:
        """Verify degraded banner, scan status banner, and bottom compare tray.

        Pre-conditions:
            - components.css loaded.
        Post-conditions:
            - #degraded-banner, #scan-status-banner, and #compare-tray exist with required states.
        """
        banner_selectors: List[str] = [
            "#degraded-banner",
            ".degraded-banner",
            "#scan-status-banner",
            ".scan-banner",
            ".scan-banner--running",
            ".scan-banner--completed",
            ".scan-banner--error",
            ".scan-banner--unavailable",
            "#compare-tray",
            ".compare-tray",
            ".compare-slots",
            ".compare-slot--filled",
            ".compare-slot--empty",
        ]
        for sel in banner_selectors:
            self.assertIn(sel, self.components_text, f"Missing banner or compare tray selector: {sel}")

    def test_deal_workbench_components(self) -> None:
        """Verify Deal Workbench KPI strip, filter controls, cards grid, and table view.

        Pre-conditions:
            - components.css loaded.
        Post-conditions:
            - Selectors for cards, media, badges, precision table, and cohort range bar exist.
        """
        workbench_selectors: List[str] = [
            ".kpi-strip",
            ".kpi-card",
            ".kpi-card--excellent",
            ".kpi-label",
            ".kpi-value",
            ".kpi-sub",
            "#filter-form",
            ".filter-bar",
            ".filter-grid",
            ".view-toggle",
            ".view-toggle-btn",
            ".triage-bar",
            ".triage-tabs",
            ".triage-tab",
            ".deals-grid",
            ".deal-card",
            ".deal-card__media",
            ".deal-card__overlay-tl",
            ".deal-card__overlay-tr",
            ".deal-card__price",
            ".deal-card__delta",
            ".vin-chip",
            ".precision-table",
            ".table-scroll",
            "aria-sort",
            ".cohort-range-bar",
            ".cohort-track",
            ".cohort-buyzone",
            ".cohort-iqr",
            ".cohort-median",
            ".cohort-marker",
            ".market-badge",
            ".market-badge--excellent",
            ".market-badge--cut",
            ".market-badge--warn",
            ".market-badge--info",
            ".score-pill",
            ".safety-badge",
        ]
        for sel in workbench_selectors:
            self.assertIn(sel, self.components_text, f"Missing Deal Workbench selector: {sel}")

    def test_market_intelligence_and_arbitrage_selectors(self) -> None:
        """Verify Market Intelligence frontier SVG chart, panels, and Arbitrage selectors.

        Pre-conditions:
            - components.css loaded.
        Post-conditions:
            - Frontier chart, OLS lines, nodes, tooltips, and arbitrage cards exist.
        """
        market_selectors: List[str] = [
            "#frontier-chart",
            ".frontier-panel",
            "#frontier-svg",
            ".frontier-gridline",
            ".frontier-axis",
            ".frontier-buyzone",
            ".frontier-p25-line",
            ".frontier-p50-line",
            ".frontier-ols-line",
            ".frontier-node",
            ".frontier-point",
            "#frontier-tooltip",
            ".chart-tooltip",
            ".chart-tick",
            ".frontier-legend",
            "#cohort-leaderboard",
            "#momentum-feed",
            "#platform-comparison",
            ".platform-grid",
            ".platform-card",
            ".arbitrage-callout",
            "#distance-bands",
            ".distance-bands-grid",
            ".band-card",
            ".band-bar-track",
            ".band-bar-fill",
            "#dealer-matrix",
        ]
        for sel in market_selectors:
            self.assertIn(sel, self.components_text, f"Missing Market/Arbitrage selector: {sel}")

    def test_comparator_and_drawer_modal_parity(self) -> None:
        """Verify Side-by-Side Comparator, slide-over drawer, and legacy modal parity.

        Pre-conditions:
            - components.css loaded.
        Post-conditions:
            - #workspace-compare, #analysis-drawer, and #detail-modal selectors exist.
        """
        compare_drawer_selectors: List[str] = [
            "#workspace-compare",
            ".compare-toolbar",
            ".compare-matrix-wrap",
            ".compare-table",
            ".compare-slot-header",
            ".compare-slot-empty",
            ".compare-cell--winner",
            ".compare-winner-pill",
            "#analysis-drawer",
            ".valuation-drawer",
            ".drawer-backdrop",
            ".drawer-header",
            "#drawer-title",
            ".drawer-body",
            ".drawer-footer",
            ".price-sparkline",
            ".leverage-grid",
            ".tco-grid",
            ".tax-credit-card",
            ".recall-card",
            ".complaint-card",
            "#detail-modal",
            ".modal-dialog",
            "#modal-body",
        ]
        for sel in compare_drawer_selectors:
            self.assertIn(sel, self.components_text, f"Missing Compare/Drawer/Modal selector: {sel}")

    def test_5_state_matrix_and_cls_skeleton_classes(self) -> None:
        """Verify 5-state matrix empty/error states and CLS=0 geometry-matched skeletons.

        Pre-conditions:
            - components.css loaded.
        Post-conditions:
            - Empty/error states and skeleton classes (.skeleton-kpi, .skeleton-card, etc.) exist.
        """
        state_selectors: List[str] = [
            ".empty-state",
            ".error-state",
            ".skeleton",
            ".skeleton-kpi",
            ".skeleton-card",
            ".skeleton-card__media",
            ".skeleton-table-row",
            ".skeleton-chart",
        ]
        for sel in state_selectors:
            self.assertIn(sel, self.components_text, f"Missing 5-state/skeleton selector: {sel}")

        # Check CLS=0 height reservations
        self.assertIn("height: 176px", self.components_text, "Missing media height reservation (176px)")
        self.assertIn("min-height: 92px", self.components_text, "Missing KPI skeleton min-height (92px)")
        self.assertIn("min-height: 468px", self.components_text, "Missing card skeleton min-height (468px)")
        self.assertIn("height: 48px", self.components_text, "Missing table row skeleton height (48px)")

    def test_responsive_breakpoints_and_reduced_motion(self) -> None:
        """Verify responsive breakpoint media queries and reduced-motion contract.

        Pre-conditions:
            - tokens.css and components.css loaded.
        Post-conditions:
            - Breakpoint queries and prefers-reduced-motion block are present in both files.
        """
        breakpoints: List[str] = [
            "@media (min-width: 768px)",
            "@media (min-width: 1024px)",
            "@media (min-width: 1280px)",
            "@media (min-width: 1600px)",
            "@media (prefers-reduced-motion: reduce)",
        ]
        for bp in breakpoints:
            self.assertIn(bp, self.components_text, f"Missing responsive breakpoint in components.css: {bp}")

        self.assertIn(
            "@media (prefers-reduced-motion: reduce)",
            self.tokens_text,
            "Missing reduced motion query in tokens.css",
        )


if __name__ == "__main__":
    unittest.main()
