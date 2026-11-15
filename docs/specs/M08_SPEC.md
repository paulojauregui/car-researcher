# Milestone M08 Specification: Client Workspace Renderers, Dossier Drawer & Comparator (`views.js`)

## Target Files
- `src/dashboard/static/views.js`
- `tests/test_views_js_unittest.py`

## Non-Negotiable Constraints
- Vanilla ES module importing helpers from `./charts.js` only (zero CDNs).
- Strictly ZERO emojis in strings, labels, or comments.
- All dynamic values escaped cleanly via `escapeHtml(...)`.
- Enforces `tabular-nums` on every numeric price, delta, percentile, `$/1k mi`, score, DOM, leverage, TCO, EPA, and VIN readout.
- Enforces complete 5-State Matrix (`Empty`, `Loading` with `CLS = 0` skeletons, `Nominal`, `Degraded`, `Error` with Retry preserving filters/pins).

---

## 1. `src/dashboard/static/views.js` Exports
1. `escapeHtml(value)`, `formatCurrency(val)`, `formatSignedCurrency(val)`, `formatNumber(val)`
2. `renderBadgesHtml(badges, deal, limit = 4)`: Maps `BELOW_P25_COHORT`, `FRESH_PRICE_CUT`, `STALE_INVENTORY_30D`, `HIGH_LEVERAGE`, `USED_EV_TAX_CREDIT` cleanly with inline 10px SVGs.
3. `renderKpiStripHtml(kpis)`: 4 KPI tiles matching `#kpi-bar` structure.
4. `renderDealsSectionHtml(deals, kpis, filters, pinnedIds)`: Renders `#kpi-bar`, triage sub-tabs (`all`, `excellent`, `good`, `drops`, `saved`, `dismissed`), dynamic filter-preserving `/api/export/csv?...` and `/api/export/markdown?...` links, and either Empty state, Grid cards (`.deals-grid`), or Sortable Precision Table (`.precision-table` with `<th scope="col">` and `aria-sort`).
5. `renderWorkbenchLoadingHtml(viewMode)`: `CLS = 0` geometry-matched KPI + card/table skeletons.
6. `renderWorkspaceErrorHtml(message, retryAction)`: State-preserving inline error alert with `Retry` button (`data-retry-action`).
7. `renderMarketWorkspaceHtml(overview, cohortsData, selectedCohortKey, pinnedIds)`:
   - Populates `#cohort-select` options (`ALL` + all cohorts with `n` & `confidence_tier`), telemetry summary pills (`Sample Size`, `Confidence`, `Scope`, `OLS Slope`, `R^2`, `p25`, `Median p50`), accessible `<details>` data table fallback beneath `#frontier-chart`.
   - Renders `#cohort-leaderboard` showing all 14 watchlist models (including `0 listings` gap models) with `Plot Frontier` and `Filter Workbench` action buttons.
   - Renders `#momentum-feed` dual panels (`Fresh Price-Cut Movers` and `Stale High-Leverage Inventory >= 30d`).
8. `renderArbitrageWorkspaceHtml(arbitrageData)`:
   - Renders `#platform-comparison` (`CARSCOM` vs `CARGURUS` cards + spread callout).
   - Renders `#distance-bands` (`0-15 mi`, `15-30 mi`, `30-60 mi`, `60+ mi` + 1-click `Filter <= X mi`).
   - Renders sortable `#dealer-matrix` with `Inspect Best Deal` and `Filter Dealer` actions.
9. `renderComparatorWorkspaceHtml(compareData, pinnedIds)`:
   - Empty state when `pinnedIds.length === 0` (`Browse Deal Workbench` CTA).
   - 3-slot comparison matrix comparing 10 normalized dimensions with `Best` winner cell highlights (`.compare-cell--winner`), empty slot placeholders, Unpin buttons, Copy Markdown summary button, and footer actions (`Analyze`, `Save`, `Open`).
10. `renderAnalysisDrawerHtml(analysisData, pinnedIds)`:
    - Renders all 7 sections inside `#analysis-drawer`: Sticky header, Cohort Valuation & Percentile Range Bar, TimescaleDB Price History Sparkline & Ledger, 4-Factor Deal Breakdown, Negotiation Leverage & Offer Strategy, 3-Yr Depreciation/TCO + `$4,000` Used EV Tax Credit checklist, NHTSA Safety Posture & EPA Telemetry + Recalls/Complaints.
11. `renderCompareTrayHtml(dealsById, pinnedIds)`, `renderDegradedBannerHtml(provenance)`, `renderScanStatusBannerHtml(scanState, temporalUiUrl)`.

---

## 2. `tests/test_views_js_unittest.py` Specification
Verify:
- `src/dashboard/static/views.js` exists, exports all required render functions, imports `./charts.js`.
- Zero emojis, zero CDN URLs, zero `localhost:8080`.
- Contains `escapeHtml`, `tabular-nums`, `aria-sort`, `role="dialog"` / drawer sections, all 5 `market_badges` labels, and all 5-state renderers (`Loading`, `Empty`, `Error`, `Degraded`, `Nominal`).
