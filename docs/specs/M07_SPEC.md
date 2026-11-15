# Milestone M07 Specification: Client Pure SVG Charts & Visualizations (`charts.js`)

## Target Files
- `src/dashboard/static/charts.js`
- `tests/test_js_modules_unittest.py`

## Non-Negotiable Constraints
- Vanilla ES module (`export function ...`) with zero external libraries or CDNs.
- Strictly ZERO emojis in strings, comments, or SVG labels.
- Strictly pure SVG geometry and CSS variable tokens (`var(--accent-telemetry)`, `var(--status-excellent)`, etc.).

---

## 1. `src/dashboard/static/charts.js` Exports
1. `escapeSvgText(value)`: Safe XML/HTML entity escaping for dynamic SVG `<text>` and `aria-label` strings.
2. `renderFrontierChart(containerEl, tooltipEl, cohortData, options)`:
   - Parameters: `containerEl` (hosts `#frontier-svg`), `tooltipEl` (`#frontier-tooltip`), `cohortData` (object with `sample_size`, `p25`, `p50`, `ols_trendline`, `scatter_points`), `options` (`{ pinnedIds: Set<string>, onSelectListing: (id) => void }`).
   - Empty state (`!points.length`): renders structured `.empty-state` inside `containerEl` (hiding `#frontier-tooltip`).
   - Renders responsive `<svg id="frontier-svg" viewBox="0 0 880 420" role="img" aria-labelledby="frontier-title" aria-describedby="frontier-desc">` with `<title>`, `<desc>`, `<defs><clipPath id="frontier-plot-clip">`, X/Y axes (`Odometer (miles)` & `Listed Price (USD)`), dashed gridlines, Buy-Zone shaded region (`y >= p25`), dashed `p50` Median horizontal line, solid `p25` Buy-Zone boundary line, clipped OLS trendline (rendered cleanly when `sample_size >= 3` and finite slope; when `sample_size < 3`, renders a crisp SVG note `"Insufficient sample (n < 3) for OLS regression"`).
   - Plots each point as focusable `<g class="frontier-node" tabindex="0" role="button" data-listing-id="..." aria-label="...">` with a `14px` transparent hit circle + `5.5px` visible circle colored by score/tier (`>=85` excellent, `>=75` info, else cut/danger) + outer ring if pinned.
   - Binds pointer hover, click, `focus`/`blur`, `ArrowLeft`/`ArrowRight` (sorted by mileage x-coordinate), and `Enter`/`Space` inspection calling `options.onSelectListing(id)`.
   - Positions `tooltipEl` clamped cleanly inside `containerEl` bounds (never overflowing right/left/top/bottom).
3. `renderPriceSparkline(snapshots, options)`:
   - Options: `{ width = 560, height = 110, compact = false }`.
   - Returns clean inline SVG markup (`class="price-sparkline"`).
   - Handles `0` snapshots (clean muted baseline), `1` snapshot (dashed baseline + single centered terminal dot + `"1 snapshot recorded"` label), and `>= 2` chronological snapshots (polyline + translucent area polygon + data nodes colored by price drop vs rise + terminal circle).
4. `renderCohortRangeBarHtml(deal)`:
   - Generates pure HTML/CSS `.cohort-range-bar` markup (`p10..p25..p50..p75` scale across `[min_price, max_price]`, Buy-Zone fill, IQR box, `p50` tick, rotated diamond `.cohort-marker` positioned accurately and clamped `2%..98%`, plus tabular scale labels).

---

## 2. `tests/test_js_modules_unittest.py` Specification
Verify:
- `src/dashboard/static/charts.js` exists, exports `renderFrontierChart`, `renderPriceSparkline`, `renderCohortRangeBarHtml`, `escapeSvgText`.
- Zero emojis, zero external HTTP imports, zero `localhost:8080`.
- Balanced braces/parentheses and proper `aria-label` / `tabindex` / `ArrowLeft` / `ArrowRight` / `Enter` support.
