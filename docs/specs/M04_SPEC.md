# Milestone M04 Specification: HTTP/ASGI Router, v2 Market Intelligence APIs & Safe Static Serving

## Target Files
- `src/dashboard/app.py`
- `tests/test_dashboard_api_v2_unittest.py`

## Non-Negotiable Constraints
- Strictly zero emojis anywhere in `src/dashboard/app.py` or tests (remove the existing emojis on lines 196 and 318!).
- Strictly NO hardcoded `http://localhost:8080` anywhere.
- Zero external dependencies (Python stdlib + `src.dashboard.*`, `src.config.settings`, `src.workflows.temporal_compat`).
- Absolute imports exclusively (`from src.... import ...`).
- Every class, method, and function MUST have `"""..."""` docstrings with `Pre-conditions:` and `Post-conditions:` and full static type annotations.
- Keep `handle_request(self, method, path, query_params=None, body_params=None, headers=None)` backward-compatible with callers passing only `(method, path, query_params, body_params)`.

---

## 1. `src/dashboard/app.py` Updates

### 1.1 Path-Safe Static File Serving
- Define `STATIC_DIR = Path(__file__).resolve().parent / "static"`.
- Handle `GET /static/<rel_path>` (and `HEAD /static/<rel_path>`):
  - Reject null bytes, leading slashes, or `..` traversal attempts cleanly (`403 Forbidden` or `404 Not Found` after checking `resolved.is_relative_to(STATIC_DIR.resolve())`).
  - Map extensions to MIME types:
    - `.css`: `"text/css; charset=utf-8"`
    - `.js`: `"application/javascript; charset=utf-8"`
    - `.svg`: `"image/svg+xml; charset=utf-8"`
    - `.json`: `"application/json; charset=utf-8"`
    - `.html`: `"text/html; charset=utf-8"`
  - Return `200` with `Cache-Control: no-cache` (or `404` if file missing).

### 1.2 Preserved & Alias Legacy Endpoints
Keep ALL existing endpoints working accurately:
1. `GET /`, `HEAD /`: Renders full SSR dashboard page (`deals`, `kpis`, `filters`, `provenance=self.repo.get_provenance()`, `market_overview=...`).
2. `GET /partials/deals`: Renders `render_deals_section(deals, kpis, filters)`.
3. `GET /partials/kpis`: Renders `render_kpis_partial(kpis)` (`200`, `text/html`).
4. `GET /partials/listing/{id}/history`: Renders `render_listing_history_modal(history_data)`.
5. `GET /partials/model-profile`: Renders `render_model_profile_modal(profile)`.
6. `POST /api/listing/{id}/bookmark` and `POST /api/listing/{id}/dismiss`:
   - Toggle flag on `self.repo`.
   - If `Accept: application/json` or `q_params.get("format") == "json"`: return `200` JSON `{"id": listing_id, "flag": flag_key, "value": new_val, "kpis": kpis}` (or `404` JSON if listing not found).
   - Otherwise preserve exact v1 contract: return `200` `render_deals_section(deals, kpis, filters)`.
7. `POST /api/listings/{id}/flag/{key}`:
   - Accepts `key` in `("user_bookmarked", "user_dismissed", "bookmark", "dismiss")` (normalizing `"bookmark"` -> `"user_bookmarked"`, `"dismiss"` -> `"user_dismissed"`). Returns `400` JSON on invalid key, `404` JSON if listing missing, else `200` JSON `{"id": listing_id, "flag": norm_key, "value": new_val, "kpis": kpis}`.
8. `POST /api/scan`:
   - Track latest workflow id on `self._last_scan_workflow_id`.
   - Accept optional JSON body or form/query `target`.
   - If `Accept: application/json` or `q_params.get("format") == "json"`: return `200` JSON `{"started": bool, "workflow_id": wf_id, "error": err, "temporal_available": HAS_TEMPORAL, "temporal_ui_url": settings.temporal_ui_url}`.
   - Otherwise return `200` clean HTML banner (`render_scan_status_banner(...)` or clean non-emoji error banner).
9. `GET /api/scan/status` AND `GET /api/scan/{wf_id}/status`:
   - For `GET /api/scan/status`: accepts optional `?workflow_id=...` (falling back to `self._last_scan_workflow_id`). Returns JSON `{"temporal_available": HAS_TEMPORAL, "temporal_ui_url": settings.temporal_ui_url, "active_workflow_id": target_wf_id, "summary": summary}` (or HTML if `format=html`).
   - For `GET /api/scan/{wf_id}/status`: if `Accept: application/json` or `format=json` return JSON; else preserve HTML banner `render_scan_status_banner(wf_id, summary)`.
10. `GET /api/export/csv`, `GET /api/export/markdown`: Preserve exact headers and behavior.
11. `GET /api/deals`: Returns JSON `{"provenance": self.repo.get_provenance(), "kpis": kpis, "filters": filters, "count": len(deals), "deals": deals}`.
12. `GET /api/health`: Returns JSON `{"status": "ok", "service": "car-researcher-dashboard", "provenance": self.repo.get_provenance()}`.

### 1.3 New v2 Quantitative Market Intelligence JSON Endpoints
1. `GET /api/market/overview`:
   - Returns `200` JSON from `await self.repo.get_market_overview()`.
2. `GET /api/market/cohorts`:
   - Accepts optional `?cohort=`, `?make=`, `?model=`. Returns `200` JSON from `await self.repo.get_market_cohorts(...)`.
3. `GET /api/market/dealers`:
   - Returns `200` JSON from `await self.repo.get_dealer_arbitrage()`.
4. `GET /api/listings/{id}/history`:
   - Returns `200` JSON `{deal, snapshots}` (or `404` JSON `{"error": "Listing not found"}`).
5. `GET /api/listings/{id}/analysis`:
   - Returns `200` JSON full 7-section dossier from `await self.repo.get_listing_analysis(listing_id)` (or `404` JSON if missing).
6. `GET /api/models/{make}/{model}/{year}`:
   - Unquotes `make`, `model`, validates `year` integer (`400` if non-int), calls `await self.repo.get_model_intelligence(make, model, year)`, returns `200` JSON.
7. `GET /api/compare`:
   - Parses comma-separated `?ids=id1,id2,id3` (max 3; if >3 IDs passed, returns `400` JSON `{"error": "Maximum 3 listings can be compared simultaneously"}` or caps cleanly — let's return `400` when `len(raw_ids) > 3` with clear message, and `200` JSON for `0..3` IDs!).

### 1.4 HTTP Request Parsing Enhancement (`_handle_client`)
- Collect lowercased request headers (`Dict[str, str]`) and pass `headers=req_headers` to `app.handle_request(...)`.
- Parse `application/json` request body cleanly into `body_params` if `Content-Type` contains `application/json`.
- Map `400`, `403`, `404`, `500` status texts accurately in `_handle_client`.

---

## 2. `tests/test_dashboard_api_v2_unittest.py` Specification
Verify:
- Static file serving for valid path & path traversal rejection (`/../` -> `403` or `404`).
- `HEAD /`, `GET /partials/kpis`, `GET /api/health`, `GET /api/deals` (with `provenance`).
- `GET /api/market/overview`, `GET /api/market/cohorts`, `GET /api/market/dealers`.
- `GET /api/listings/{id}/history`, `GET /api/listings/{id}/analysis` (including `404` on unknown ID).
- `GET /api/models/{make}/{model}/{year}` (with mocked `GovAPIClient` / no real network call!).
- `GET /api/compare?ids=...` (`0`, `2`, `3` IDs -> `200`, `4` IDs -> `400`).
- `POST /api/listings/{id}/flag/user_bookmarked` JSON toggle & invalid flag `400`.
- `POST /api/scan` JSON & HTML modes + `GET /api/scan/status` graceful Temporal-unavailable handling.
- Zero emojis and zero `"localhost:8080"` inside `src/dashboard/app.py`.
