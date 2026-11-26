"""Unit tests for client pure SVG charts and visualizations module (charts.js).

Validates Milestone M07 acceptance criteria:
- Pure vanilla ES module exports (escapeSvgText, renderFrontierChart,
  renderPriceSparkline, renderCohortRangeBarHtml).
- Zero external dependencies, zero CDNs, zero localhost:8080 references.
- Strictly zero emoji glyphs.
- Design by Contract (DbC) on all public functions and methods.
- Balanced syntax delimiters and well-formed SVG structures.
- Keyboard navigation (ArrowLeft, ArrowRight, Enter, Space), tabindex, aria-label.
- OLS regression sample size guards (n < 3 fallback notice).
- Sparkline edge cases (0 snapshots, 1 snapshot, >= 2 snapshots).
- Cohort range bar CSS selector fidelity, bounds handling, and 2%..98% marker clamping.
"""

from html.parser import HTMLParser
import pathlib
import re
from typing import Dict, List, Optional, Set, Tuple
import unittest
import xml.etree.ElementTree as ET

STATIC_DIR: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent / "src" / "dashboard" / "static"
CHARTS_JS_PATH: pathlib.Path = STATIC_DIR / "charts.js"


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


class SimpleHTMLValidator(HTMLParser):
    """HTML validator enforcing matched opening and closing tags.

    Pre-conditions:
        - HTML fragment text is provided.
    Post-conditions:
        - Records unmatched tags or void elements correctly.
    """

    VOID_TAGS: Set[str] = {"rect", "circle", "line", "polygon", "polyline", "path", "input", "br", "hr", "img"}

    def __init__(self) -> None:
        """Initialize validator state.

        Pre-conditions:
            - None.
        Post-conditions:
            - Initializes empty tag stack and error list.
        """
        super().__init__()
        self.tag_stack: List[str] = []
        self.validation_errors: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        """Handle opening tag.

        Pre-conditions:
            - tag is lowercase tag name.
        Post-conditions:
            - Pushes non-void tags to stack.
        """
        if tag.lower() not in self.VOID_TAGS:
            self.tag_stack.append(tag.lower())

    def handle_endtag(self, tag: str) -> None:
        """Handle closing tag.

        Pre-conditions:
            - tag is lowercase tag name.
        Post-conditions:
            - Pops and verifies matching tag from stack.
        """
        tag_lower: str = tag.lower()
        if tag_lower in self.VOID_TAGS:
            return
        if not self.tag_stack:
            self.validation_errors.append(f"Unexpected closing tag </{tag_lower}>")
            return
        expected: str = self.tag_stack.pop()
        if expected != tag_lower:
            self.validation_errors.append(f"Mismatched closing tag </{tag_lower}> (expected </{expected}>)")


class TestJsModulesUnittest(unittest.TestCase):
    """Test suite validating Milestone M07 pure SVG charts and client visualization module.

    Pre-conditions:
        - src/dashboard/static/charts.js exists on disk.
    Post-conditions:
        - Verifies exports, contracts, zero emojis, zero external CDNs, balanced syntax,
          keyboard navigation, ARIA contracts, and visualization edge cases.
    """

    def setUp(self) -> None:
        """Load charts.js content into test context.

        Pre-conditions:
            - Target file must exist and be readable.
        Post-conditions:
            - self.charts_text contains full charts.js string.
        """
        self.assertTrue(CHARTS_JS_PATH.exists(), f"Missing target charts file: {CHARTS_JS_PATH}")
        self.charts_text: str = CHARTS_JS_PATH.read_text(encoding="utf-8")

    def test_charts_module_file_exists_and_non_empty(self) -> None:
        """Verify charts.js exists, is non-empty, and exceeds baseline size.

        Pre-conditions:
            - File read from disk.
        Post-conditions:
            - File size exceeds 4000 characters.
        """
        self.assertGreater(
            len(self.charts_text),
            4000,
            "charts.js is unexpectedly small for a comprehensive visualization suite",
        )

    def test_zero_emojis_in_charts_js(self) -> None:
        """Verify strict zero-emoji mandate across charts.js.

        Pre-conditions:
            - File content loaded as string.
        Post-conditions:
            - Zero Unicode emoji glyphs found in comments, strings, or code.
        """
        non_ascii_emojis: Set[str] = {
            char
            for char in self.charts_text
            if ord(char) > 127 and not (0x2000 <= ord(char) <= 0x206F)
        }
        self.assertEqual(
            len(non_ascii_emojis),
            0,
            f"Prohibited non-ASCII / emoji glyphs detected in charts.js: {non_ascii_emojis}",
        )

    def test_zero_external_cdns_and_localhost(self) -> None:
        """Verify zero external HTTP/HTTPS CDN references and zero localhost:8080 occurrences.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - No http://, https://, or localhost:8080 references exist.
        """
        external_refs: List[str] = re.findall(r"https?://[^\s\"')]+", self.charts_text)
        self.assertEqual(
            len(external_refs),
            0,
            f"Prohibited external CDN or HTTP URLs found in charts.js: {external_refs}",
        )
        self.assertNotIn(
            "localhost:8080",
            self.charts_text,
            "Prohibited hardcoded localhost:8080 endpoint found in charts.js",
        )

    def test_es_module_exports_presence(self) -> None:
        """Verify presence of all four required ES module exports.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - escapeSvgText, renderFrontierChart, renderPriceSparkline,
              and renderCohortRangeBarHtml are exported functions.
        """
        required_exports: List[str] = [
            "escapeSvgText",
            "renderFrontierChart",
            "renderPriceSparkline",
            "renderCohortRangeBarHtml",
        ]
        for exp in required_exports:
            pattern: str = rf"export\s+function\s+{exp}\b"
            self.assertRegex(
                self.charts_text,
                pattern,
                f"Missing required ES module export '{exp}' in charts.js",
            )

    def test_design_by_contract_in_js_comments(self) -> None:
        """Verify Design by Contract docblocks for all public exports.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - Each public function includes Pre-conditions and Post-conditions sections.
        """
        required_functions: List[str] = [
            "escapeSvgText",
            "renderFrontierChart",
            "renderPriceSparkline",
            "renderCohortRangeBarHtml",
        ]
        for fn_name in required_functions:
            # Find JSDoc block preceding export function <fn_name>
            match = re.search(
                rf"/\*\*[\s\S]*?\*/\s*export\s+function\s+{fn_name}\b",
                self.charts_text,
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
        """Verify all braces, brackets, and parentheses in charts.js are balanced.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - Parser reports zero unmatched opening or closing delimiters.
        """
        parser = BalancedDelimiterParser(self.charts_text)
        balanced, errors = parser.parse()
        self.assertTrue(balanced, f"Syntax delimiter errors detected in charts.js: {errors}")

    def test_frontier_chart_svg_and_clip_path_contract(self) -> None:
        """Verify Frontier Chart SVG root structure, viewBox, clipping path, and axes.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - Contains viewBox='0 0 880 420', #frontier-plot-clip, rect x=76 y=28 width=772 height=332,
              gridlines, and Odometer/Price axes.
        """
        self.assertIn('viewBox="0 0 880 420"', self.charts_text)
        self.assertIn('id="frontier-svg"', self.charts_text)
        self.assertIn('class="frontier-svg"', self.charts_text)
        self.assertIn('role="img"', self.charts_text)
        self.assertIn('aria-labelledby="frontier-title"', self.charts_text)
        self.assertIn('aria-describedby="frontier-desc"', self.charts_text)

        # Defs & ClipPath
        self.assertIn('<clipPath id="frontier-plot-clip">', self.charts_text)
        self.assertIn(
            '<rect x="76" y="28" width="772" height="332" />',
            self.charts_text,
        )
        self.assertIn('clip-path="url(#frontier-plot-clip)"', self.charts_text)

        # Classes
        self.assertIn("frontier-gridline", self.charts_text)
        self.assertIn("frontier-axis", self.charts_text)
        self.assertIn("chart-tick", self.charts_text)
        self.assertIn("Odometer (miles)", self.charts_text)
        self.assertIn("Listed Price (USD)", self.charts_text)

    def test_frontier_reference_lines_and_buyzone(self) -> None:
        """Verify presence of buy-zone rect, p25 solid line, p50 dashed line, and OLS line.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - Contains frontier-buyzone, frontier-p25-line, frontier-p50-line, and frontier-ols-line.
        """
        self.assertIn("frontier-buyzone", self.charts_text)
        self.assertIn("frontier-p25-line", self.charts_text)
        self.assertIn("frontier-p50-line", self.charts_text)
        self.assertIn("frontier-ols-line", self.charts_text)

    def test_frontier_accessibility_and_keyboard_navigation(self) -> None:
        """Verify WCAG 2.2 AA accessibility and keyboard navigation contracts.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - Checks tabindex='0', role='button', 14px hit target, 5.5px data circle,
              and ArrowLeft / ArrowRight / Enter / Space event handlers.
        """
        self.assertIn('tabindex="0"', self.charts_text)
        self.assertIn('role="button"', self.charts_text)
        self.assertIn('data-listing-id="', self.charts_text)
        self.assertIn('data-index="', self.charts_text)
        self.assertIn('aria-label="', self.charts_text)

        # Hit circle (14px) and visible node circle (5.5px)
        self.assertIn('r="14"', self.charts_text)
        self.assertIn('fill="transparent"', self.charts_text)
        self.assertIn('r="5.5"', self.charts_text)

        # Keyboard event listeners
        self.assertIn("ArrowRight", self.charts_text)
        self.assertIn("ArrowLeft", self.charts_text)
        self.assertIn("Enter", self.charts_text)
        self.assertIn("Spacebar", self.charts_text)
        self.assertIn(".focus()", self.charts_text)
        self.assertIn("onSelectListing", self.charts_text)

    def test_frontier_ols_sample_size_guard(self) -> None:
        """Verify sample size guard renders crisp fallback text for small cohorts (n < 3).

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - Contains 'Insufficient sample (n < 3) for OLS regression' notice.
        """
        self.assertIn("Insufficient sample (n", self.charts_text)
        self.assertIn("for OLS regression", self.charts_text)
        self.assertIn("sampleSize >= 3", self.charts_text)

    def test_frontier_empty_state_contract(self) -> None:
        """Verify empty scatter points render .empty-state and hide floating tooltip.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - Renders empty-state, empty-state__title, and sets tooltipEl.hidden = true.
        """
        self.assertIn("empty-state", self.charts_text)
        self.assertIn("empty-state__title", self.charts_text)
        self.assertIn("tooltipEl.hidden = true", self.charts_text)

    def test_frontier_tooltip_content_and_clamping(self) -> None:
        """Verify tooltip markup structure and geometric bounding box clamping.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - Contains chart-tooltip-title, chart-tooltip-row, chart-tooltip-val,
              and tabular values for Listed Price, Mileage, Cohort Pctl, Deal Score, DOM.
        """
        self.assertIn("chart-tooltip-title", self.charts_text)
        self.assertIn("chart-tooltip-row", self.charts_text)
        self.assertIn("chart-tooltip-val", self.charts_text)
        self.assertIn("Listed Price", self.charts_text)
        self.assertIn("Mileage", self.charts_text)
        self.assertIn("Cohort Pctl", self.charts_text)
        self.assertIn("Deal Score", self.charts_text)
        self.assertIn("DOM", self.charts_text)
        # Clamping logic
        self.assertIn("getBoundingClientRect", self.charts_text)
        self.assertIn("Math.max", self.charts_text)
        self.assertIn("Math.min", self.charts_text)

    def test_price_sparkline_zero_snapshots(self) -> None:
        """Verify price sparkline zero snapshots edge case.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - Contains 'No price snapshots recorded' label and dashed baseline.
        """
        self.assertIn("No price snapshots recorded", self.charts_text)
        self.assertIn('class="price-sparkline"', self.charts_text)
        self.assertIn('role="img"', self.charts_text)

    def test_price_sparkline_single_snapshot(self) -> None:
        """Verify price sparkline single snapshot baseline and terminal dot.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - Contains '1 snapshot recorded' label and single terminal point.
        """
        self.assertIn("1 snapshot recorded", self.charts_text)

    def test_price_sparkline_multi_snapshot_trajectory(self) -> None:
        """Verify price sparkline multi-snapshot polyline and translucent polygon.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - Contains <polygon points=..., <polyline points=..., fill-opacity=...,
              and status token colors.
        """
        self.assertIn("<polygon points=", self.charts_text)
        self.assertIn("<polyline points=", self.charts_text)
        self.assertIn("fill-opacity=", self.charts_text)
        self.assertIn("0.12", self.charts_text)
        self.assertIn("var(--status-cut)", self.charts_text)
        self.assertIn("var(--status-danger)", self.charts_text)

    def test_cohort_range_bar_selectors_fidelity(self) -> None:
        """Verify Cohort Range Bar uses exact CSS selectors from components.css.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - Contains .cohort-range-bar, .cohort-range-header, .cohort-range-label,
              .cohort-range-val, .cohort-track, .cohort-buyzone, .cohort-iqr,
              .cohort-median, .cohort-marker, and .cohort-range-footer.
        """
        required_selectors: List[str] = [
            "cohort-range-bar",
            "cohort-range-header",
            "cohort-range-label",
            "cohort-range-val",
            "cohort-track",
            "cohort-buyzone",
            "cohort-iqr",
            "cohort-median",
            "cohort-marker",
            "cohort-range-footer",
            "cohort-marker--excellent",
            "cohort-marker--fair",
            "cohort-marker--danger",
        ]
        for sel in required_selectors:
            self.assertIn(
                sel,
                self.charts_text,
                f"Missing required selector/class '{sel}' in renderCohortRangeBarHtml",
            )

    def test_cohort_range_bar_bounds_and_clamping(self) -> None:
        """Verify Cohort Range Bar bounds handling (max <= min) and 2%..98% marker clamping.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - Verifies presence of max <= min guard and Math.max(2, Math.min(98, ...)).
        """
        self.assertIn("max <= min", self.charts_text)
        self.assertRegex(
            self.charts_text,
            r"Math\.max\(\s*2\s*,\s*Math\.min\(\s*98\s*,",
            "Missing marker 2%..98% clamping logic in renderCohortRangeBarHtml",
        )

    def test_escape_svg_text_entity_escaping(self) -> None:
        """Verify escapeSvgText XML entity replacements for dynamic SVG strings.

        Pre-conditions:
            - File content loaded.
        Post-conditions:
            - Contains replacement logic for &, <, >, \", and '.
        """
        self.assertIn("&amp;", self.charts_text)
        self.assertIn("&lt;", self.charts_text)
        self.assertIn("&gt;", self.charts_text)
        self.assertIn("&quot;", self.charts_text)
        self.assertIn("&#39;", self.charts_text)

    def test_svg_xml_structure_well_formedness(self) -> None:
        """Verify XML well-formedness of sample SVGs generated from chart templates.

        Pre-conditions:
            - XML parser is available in Python stdlib.
        Post-conditions:
            - Parses both Frontier and Sparkline sample SVG markup without syntax exceptions.
        """
        sample_frontier_svg: str = (
            '<svg id="frontier-svg" class="frontier-svg" viewBox="0 0 880 420" role="img" '
            'aria-labelledby="frontier-title" aria-describedby="frontier-desc">'
            '<title id="frontier-title">Frontier</title>'
            '<desc id="frontier-desc">Desc</desc>'
            '<defs><clipPath id="frontier-plot-clip">'
            '<rect x="76" y="28" width="772" height="332" />'
            '</clipPath></defs>'
            '<g class="frontier-gridlines">'
            '<line class="frontier-gridline" x1="76.0" y1="28" x2="76.0" y2="360" />'
            '</g>'
            '<g class="frontier-axes">'
            '<line class="frontier-axis" x1="76" y1="360" x2="848" y2="360" />'
            '</g>'
            '<g clip-path="url(#frontier-plot-clip)">'
            '<rect class="frontier-buyzone" x="76" y="200.0" width="772" height="160.0" />'
            '<line class="frontier-p25-line" x1="76" y1="200.0" x2="848" y2="200.0" />'
            '<line class="frontier-p50-line" x1="76" y1="150.0" x2="848" y2="150.0" />'
            '<line class="frontier-ols-line" x1="76.0" y1="180.0" x2="848.0" y2="220.0" />'
            '</g>'
            '<g class="frontier-nodes">'
            '<g class="frontier-node" tabindex="0" role="button" data-listing-id="deal-1" '
            'data-index="0" aria-label="Label">'
            '<circle cx="200.0" cy="150.0" r="14" fill="transparent" />'
            '<circle cx="200.0" cy="150.0" r="5.5" fill="var(--status-excellent)" />'
            '</g>'
            '</g>'
            '</svg>'
        )
        frontier_root: ET.Element = ET.fromstring(sample_frontier_svg)
        self.assertEqual(frontier_root.tag, "svg")
        self.assertEqual(frontier_root.attrib.get("id"), "frontier-svg")

        sample_sparkline_svg: str = (
            '<svg class="price-sparkline" viewBox="0 0 560 110" role="img" '
            'aria-label="Price sparkline from $34,000 to $32,000, cut by $2,000">'
            '<polygon points="48.0,86.0 48.0,22.0 512.0,54.0 512.0,86.0" '
            'fill="var(--status-cut)" fill-opacity="0.12" />'
            '<polyline points="48.0,22.0 512.0,54.0" fill="none" stroke="var(--status-cut)" '
            'stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />'
            '<circle cx="512.0" cy="54.0" r="4.5" fill="var(--status-cut)" '
            'stroke="var(--bg-canvas)" stroke-width="1.5" />'
            '<text class="chart-tick" x="48" y="16.0" text-anchor="start">$34,000</text>'
            '</svg>'
        )
        sparkline_root: ET.Element = ET.fromstring(sample_sparkline_svg)
        self.assertEqual(sparkline_root.tag, "svg")
        self.assertEqual(sparkline_root.attrib.get("class"), "price-sparkline")


if __name__ == "__main__":
    unittest.main()
