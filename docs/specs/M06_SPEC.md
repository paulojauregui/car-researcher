# Milestone M06 Specification: Semantic HTML5 Shell & Modular SSR Renderer (`index.html` & `templates.py`)

## Target Files
- `src/dashboard/templates/index.html`
- `src/dashboard/templates.py`
- `tests/test_templates_v2_unittest.py`

## Non-Negotiable Constraints
- Eliminate the 840-line inline HTML f-string page monolith in `src/dashboard/templates.py` by loading `src/dashboard/templates/index.html` and delegating UI hydration/interactivity to local static CSS/ES modules (`/static/tokens.css`, `/static/components.css`, `/static/app.js`).
- Strictly ZERO external CDN `<script>` or `<link>` tags (`cdn.tailwindcss.com`, `unpkg.com/htmx.org` completely removed).
- Strictly ZERO hardcoded `http://localhost:8080` anywhere in `index.html` or `templates.py`. Only render an external Temporal UI anchor when `settings.temporal_ui_url` is configured (non-empty).
- Strictly ZERO emojis anywhere in `index.html`, `templates.py`, or tests. All icons use clean inline geometric `<svg aria-hidden="true">` elements or monospaced labels.
- Preserve ALL v1 test-asserted strings and SSR hooks so `tests/test_dashboard_unittest.py` passes 100%:
  - `GET /` includes `"Bay Area EV Deal Surveillance"`, `"Scan Marketplace"`, all rendered active vehicle titles, `#kpi-bar`, `#filter-form`, `#search-input`, `#tab-input`, `#view-input`, `#deals-container`, `#scan-status-banner`.
  - `GET /partials/deals` renders `render_deals_section(deals, kpis, filters)` (with `<table` when `view == "table"`).
  - `GET /partials/kpis` renders `render_kpis_partial(kpis)`.
  - `GET /partials/listing/{id}/history` renders `render_listing_history_modal(history_data)` containing `"TimescaleDB Price Snapshots"`, VIN, price, delta.
  - `GET /partials/model-profile` renders `render_model_profile_modal(profile)`.
  - `render_scan_status_banner(workflow_id, summary)` renders `#active-scan-poller` when running and completion status when done (using optional `settings.temporal_ui_url`, never `localhost:8080`).
- Every new/modified function in `templates.py` MUST have `"""..."""` docstrings with `Pre-conditions:` and `Post-conditions:`, full static type annotations, and absolute imports only.

---

## 1. `src/dashboard/templates/index.html` Layout & IDs
Must implement the exact semantic HTML5 structure from `docs/UX_SPEC.md`:
1. `<link rel="stylesheet" href="/static/tokens.css" />` and `<link rel="stylesheet" href="/static/components.css" />`
2. `<a class="skip-link" href="#main-content">Skip to main content</a>`
3. `<div id="live-announcer" class="sr-only" aria-live="polite" aria-atomic="true"></div>`
4. `<header id="console-header" class="console-header">` with:
   - Brand SVG emblem + `<h1>Bay Area EV Deal Surveillance</h1>` + Subtitle `Market Intelligence & Quantitative Valuation Console`
   - Scope pill (`ZIP {{SEARCH_ZIP}} | {{SEARCH_RADIUS}} mi`) + Provenance pill (`{{PROVENANCE_BADGE}}`)
   - Scan trigger form (`<form id="scan-trigger-form" action="/api/scan" method="post">`) with explicit `<label for="scan-target-select">`, `<select id="scan-target-select" name="target">{{SCAN_OPTIONS_HTML}}</select>`, and `<button id="scan-submit-btn" type="submit">Scan Marketplace</button>`
   - `{{TEMPORAL_ACTION_HTML}}` (empty string when `TEMPORAL_UI_URL` unset; safe anchor when set)
5. `<nav class="workspace-nav" aria-label="Primary Workspaces">` containing `<div role="tablist" aria-label="Console Workspaces">` with 4 workspace tabs (`tab-workbench`, `tab-market`, `tab-arbitrage`, `tab-compare`) controlling `workspace-workbench`, `workspace-market`, `workspace-arbitrage`, `workspace-compare` using roving `tabindex` (`0` on active, `-1` on others).
6. `<main id="main-content" tabindex="-1">`:
   - `{{DEGRADED_BANNER_HTML}}` (`<div id="degraded-banner" role="status" aria-live="polite" ...>`)
   - `<div id="scan-status-banner" role="status" aria-live="polite" hidden></div>`
   - **Section 1: `<section id="workspace-workbench" role="tabpanel" aria-labelledby="tab-workbench">`**
     - `<form id="filter-form" class="filter-bar" ...>` with explicit `<label for="...">` for `#search-input`, `#make-select`, `#max-price-select`, `#max-mileage-select`, `#max-distance-select`, `#sort-select`, View Mode buttons (`#view-grid-btn`, `#view-table-btn`), and `#reset-filters-btn`.
     - `<div id="deals-container">{{INITIAL_DEALS_HTML}}</div>`
   - **Section 2: `<section id="workspace-market" role="tabpanel" aria-labelledby="tab-market" hidden>`**
     - Cohort selector (`<label for="cohort-select">` + `<select id="cohort-select">`), frontier telemetry pills, `#frontier-chart` container (`<svg id="frontier-svg">`), `#frontier-tooltip`, `#cohort-leaderboard`, `#momentum-feed`.
   - **Section 3: `<section id="workspace-arbitrage" role="tabpanel" aria-labelledby="tab-arbitrage" hidden>`**
     - `#platform-comparison`, `#distance-bands`, `#dealer-matrix`.
   - **Section 4: `<section id="workspace-compare" role="tabpanel" aria-labelledby="tab-compare" hidden>`**
     - Comparator toolbar + `#compare-matrix-container`.
7. `<div id="compare-tray" role="region" aria-label="Comparison Queue" hidden></div>`
8. `<aside id="analysis-drawer" class="valuation-drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title" hidden>` (with backdrop `.drawer-backdrop`, close button `#drawer-close-btn`, `#drawer-body`, and `#detail-modal` / `#modal-body` compatibility wrapper or synced drawer).
9. `<footer role="contentinfo" class="console-footer">...</footer>`
10. `<script id="initial-state" type="application/json">{{INITIAL_STATE_JSON}}</script>` (escaping `</script` safely!)
11. `<script type="module" src="/static/app.js"></script>`

---

## 2. `src/dashboard/templates.py` Clean Refactoring
Keep `templates.py` compact (~350-450 lines), modular, and well-typed:
- `render_full_dashboard_page(deals, kpis, filters, provenance=None)`
- `render_deals_section(deals, kpis, filters)`
- `render_kpis_partial(kpis)`
- `render_listing_history_modal(history_data)`
- `render_model_profile_modal(profile)`
- `render_scan_status_banner(workflow_id, summary)`
- `render_degraded_banner(provenance)`
Using clean component classes (`kpi-card`, `deal-card`, `precision-table`, `cohort-range-bar`, `market-badge`, `vin-chip`), `tabular-nums`, inline geometric SVGs, and zero emojis.

---

## 3. `tests/test_templates_v2_unittest.py` Specification
Verify:
- Zero emojis across `templates.py` and `index.html`.
- Zero external CDN links (`tailwindcss`, `htmx.org`).
- Zero `localhost:8080` occurrences; verify `TEMPORAL_UI_URL` conditionally renders when configured and omits link when `None`.
- Presence of all required semantic landmarks and UX spec IDs (`skip-link`, `live-announcer`, `degraded-banner`, `scan-status-banner`, `workspace-workbench`, `workspace-market`, `workspace-arbitrage`, `workspace-compare`, `analysis-drawer`, `frontier-chart`, `cohort-select`, `cohort-leaderboard`, `momentum-feed`, `dealer-matrix`, `platform-comparison`, `distance-bands`, `search-input`, `compare-tray`).
- Every `<input>` and `<select>` (non-hidden) has a matching `<label for="...">`.
- Safe escaping in `<script id="initial-state">` when titles contain `</script>`.
