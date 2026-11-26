# Milestone M09 Specification: Client Controller, Keyboard Accessibility & E2E Integration (`app.js` & `test_e2e_v2_unittest.py`)

## Target Files
- `src/dashboard/static/app.js`
- `tests/test_e2e_v2_unittest.py`

## Non-Negotiable Constraints
- Vanilla ES module importing `./views.js` and `./charts.js` with zero external libraries/CDNs.
- Strictly ZERO emojis and ZERO `localhost:8080` anywhere.
- Preserve v1 inline helper signatures if referenced (`window.setFilterTab`, `window.toggleViewMode`, `window.openModal`, `window.closeModal`).

---

## 1. `src/dashboard/static/app.js` Behavior Contract
1. **Bootstrap & State Hydration**:
   - Reads `<script id="initial-state" type="application/json">` on `DOMContentLoaded` (deals, kpis, filters, provenance, pinned IDs restored from `localStorage` under `"car_researcher_compare_pins"` capped at 3).
   - Reads optional `?workspace=workbench|market|arbitrage|compare` query param and activates that workspace cleanly.
   - Binds all delegated event listeners (no reliance on fragile inline `onclick` for new v2 workspaces).
2. **Primary Workspace Tab Roving `tabindex` & Lazy Data Fetching**:
   - Supports click + `ArrowLeft` / `ArrowRight` / `Home` / `End` across `#tab-workbench`, `#tab-market`, `#tab-arbitrage`, `#tab-compare`.
   - Syncs `?workspace=<key>` via `window.history.replaceState` and announces switch in `#live-announcer`.
   - Hydrates `/api/market/overview` + `/api/market/cohorts` for Market Intelligence, `/api/market/dealers` for Arbitrage, and `/api/compare?ids=...` for Comparator, showing `CLS = 0` skeletons during load and state-preserving Retry alerts on error.
3. **Workbench Filtering, Sorting & Optimistic Triage**:
   - Debounced `250ms` search (`#search-input`) + immediate change handler on `#make-select`, `#max-price-select`, `#max-mileage-select`, `#max-distance-select`, `#sort-select`.
   - Updates Grid/Table view, sub-tabs (`all`, `excellent`, `good`, `drops`, `saved`, `dismissed`), `#reset-filters-btn`, and export links.
   - Optimistic Bookmark/Dismiss via `POST /api/listing/{id}/bookmark` and `/dismiss` with `Accept: application/json`, immediate UI + counter update, `#live-announcer` announcement, and automatic rollback + retry alert on failure.
4. **Compare Pinning & Tray (`<= 3` limit)**:
   - Pin/unpin updates `#compare-tray`, tab badge (`N/3`), card/row button `aria-pressed`, `localStorage`, and Workspace 4 when active.
   - Attempting a 4th pin announces limit warning in `#live-announcer` and tray without failing silently.
5. **Slide-Over Valuation Drawer (`#analysis-drawer`) Focus Trap & Restoration**:
   - Opening stores `lastFocusedTrigger = document.activeElement`, renders `CLS = 0` loading skeleton, fetches `/api/listings/{id}/analysis`, renders all 7 sections + sparkline, moves focus to drawer close button (`#drawer-close-btn`), and traps `Tab`/`Shift+Tab` inside `#analysis-drawer`.
   - `Escape`, close button, or backdrop click closes drawer and restores focus to `lastFocusedTrigger`.
6. **Global Keyboard Shortcuts**:
   - `/` (when not inside `<input>`, `<textarea>`, `<select>`) or `Cmd/Ctrl+K`: switches to `workbench` if needed, focuses `#search-input` and selects text.
   - `Escape`: closes `#analysis-drawer` (or `#frontier-tooltip` if open).
7. **Scan Trigger & `2000ms` Poller (`#scan-trigger-form`)**:
   - Submits `POST /api/scan?format=json` with `Accept: application/json`, handles Temporal-unavailable gracefully, polls `GET /api/scan/{wf_id}/status?format=json` every `2000ms` until `is_completed`, then re-hydrates active workspace while preserving filters/pins.

---

## 2. `tests/test_e2e_v2_unittest.py` Specification
End-to-end verification tests covering:
- `DashboardApp` initialized with default `DashboardRepository()` (`fallback_deals=None`, proving offline-sample 24-EV mode works out of the box!).
- `GET /`, `HEAD /`, `/static/tokens.css`, `/static/components.css`, `/static/app.js`, `/static/views.js`, `/static/charts.js`.
- `/api/health`, `/api/deals`, `/api/market/overview`, `/api/market/cohorts`, `/api/market/dealers`, `/api/listings/{id}/analysis`, `/api/listings/{id}/history`, `/api/compare`.
- Zero emojis across `src/dashboard/` and `src/activities/market_analytics.py`.
- Zero external CDN strings and zero hardcoded `localhost:8080` across `src/dashboard/`.
- Explicit `<label for="...">` validation on every non-hidden `<input>` and `<select>` in rendered `GET /` HTML.
