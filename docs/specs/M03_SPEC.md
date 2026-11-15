# Milestone M03 Specification: Repository Analytics Integration, Provenance & Enriched Exports

## Target Files
- `src/dashboard/queries.py`
- `tests/test_queries_v2_unittest.py`

## Non-Negotiable Constraints
- Strictly zero emojis anywhere in code, docstrings, comments, or tests.
- Preserve Zero-Dependency Fallback (`HAS_SQLALCHEMY` try/except guard).
- Absolute imports exclusively (`from src.... import ...`).
- Every new/modified class, method, and function MUST have `"""..."""` docstrings with `Pre-conditions:` and `Post-conditions:` and full static type annotations.
- Preserve all existing public method names (`fetch_all_Normalized_deals`, `_normalize_record`, `filter_and_sort_deals`, `compute_kpis`, `get_listing_history`, `toggle_user_flag`, `get_model_intelligence`, `export_deals_csv`, `export_deals_markdown`) and existing dict keys so `tests/test_dashboard_unittest.py` passes 100% unmodified.

---

## 1. `src/dashboard/queries.py` Updates

### 1.1 Data Source & Provenance Tracking
- In `DashboardRepository.__init__(self, fallback_deals: Optional[List[Dict[str, Any]]] = None)`:
  - Keep `self._fallback_deals: Optional[List[Dict[str, Any]]] = fallback_deals`. (Important: distinguish `None` vs `[]`! When `fallback_deals is None`, `DashboardRepository` operates in production/auto mode; when `fallback_deals` is an explicit list like `_sample_deals()` or `[]`, use that explicit fixture!).
  - Track `self.data_source_mode: str = "fixture" if fallback_deals is not None else "timescaledb"` and `self.data_source_detail: str = ...`.
  - Expose `get_provenance(self) -> Dict[str, Any]` returning:
    ```python
    {
        "mode": self.data_source_mode,  # "timescaledb" | "offline-sample" | "fixture"
        "detail": self.data_source_detail,
        "temporal_available": bool(HAS_TEMPORAL),
        "temporal_ui_url": settings.temporal_ui_url,
    }
    ```
- In `fetch_all_Normalized_deals(self) -> List[Dict[str, Any]]`:
  - If `self._fallback_deals is not None`:
    - `self.data_source_mode = "fixture"`
    - `self.data_source_detail = "In-memory test or custom fixture dataset."`
    - Normalize each row with `_normalize_record(d)`.
  - Else if `not HAS_SQLALCHEMY`:
    - Lazily initialize `self._offline_sample_cache` via `get_offline_sample_deals()` (so bookmark/dismiss toggles persist across requests in memory during an offline session!).
    - `self.data_source_mode = "offline-sample"`
    - `self.data_source_detail = "SQLAlchemy/PostgreSQL driver not installed; displaying representative Bay Area EV sample dataset."`
    - Normalize each row with `_normalize_record(d)`.
  - Else try querying PostgreSQL/TimescaleDB:
    - If query succeeds and returns rows: `self.data_source_mode = "timescaledb"`, `self.data_source_detail = "Live PostgreSQL + TimescaleDB market telemetry."`
    - If connection/query raises exception OR returns 0 rows when DB is offline/unseeded: fall back to `self._offline_sample_cache` (`get_offline_sample_deals()`), set `self.data_source_mode = "offline-sample"`, and set an honest `self.data_source_detail` message explaining why offline-sample mode is active!
  - **Enrichment Pass**:
    - Before returning, enrich the normalized deals list via `enrich_collection_with_analytics(records)` (from `src.activities.market_analytics`), storing the resulting `cohorts_data` on `self._last_cohorts_data` (or computing synchronously cleanly) and returning the enriched `List[Dict[str, Any]]`!
    - Note: if `records` is empty (`[]`), return `[]` safely.

### 1.2 `_normalize_record` Preservation
- Keep `price_history` if present on `row` (e.g., `normalized["price_history"] = list(row.get("price_history") or [])`) so `get_listing_history` works seamlessly in offline/fixture mode!
- Keep all existing normalized keys (`id`, `vin`, `platform`, `platform_id`, `url`, `title`, `make`, `model`, `year`, `trim_detail`, `price`, `mileage`, `exterior_color`, `seller_name`, `location_city`, `distance_miles`, `title_status`, `accident_count`, `owner_count`, `thumbnail`, `market_value`, `price_delta`, `pct_savings`, `deal_score`, `recommendation`, `score_breakdown`, `price_change`, `days_on_market`, `snapshot_count`, `is_bookmarked`, `is_dismissed`, `drivetrain`, `cpo`, `first_seen`, `last_seen`).

### 1.3 Filtering, Sorting & Extended KPIs
- `filter_and_sort_deals(...)`:
  - Preserve existing tabs (`all`, `excellent`, `good`, `drops`/`price_drops`, `saved`/`bookmarked`, `dismissed`) and existing sort keys (`score_desc`, `savings_asc`, `price_asc`, `mileage_asc`, `distance_asc`).
  - Add new sort keys:
    - `leverage_desc`: `x.get("negotiation_leverage_score", 0.0)` descending (tie-break `deal_score`)
    - `dom_desc`: `x.get("days_on_market", 0)` descending (tie-break `deal_score`)
    - `msrp_off_desc`: `x.get("msrp_discount_pct", 0.0)` descending
- `compute_kpis(all_deals: List[Dict[str, Any]]) -> Dict[str, Any]`:
  - Preserve all 7 existing keys (`total_active`, `excellent_count`, `saved_count`, `dismissed_count`, `price_drops_count`, `max_savings`, `avg_discount`).
  - Add new quantitative KPI keys:
    - `good_count`: count of active with `deal_score >= 75.0`
    - `below_p25_count`: count of active with `"BELOW_P25_COHORT"` in `market_badges`
    - `avg_msrp_discount_pct`: rounded mean `msrp_discount_pct` across active
    - `avg_dom`: rounded mean `days_on_market` across active
    - `high_leverage_count`: count of active with `negotiation_leverage_score >= 70.0`
    - `tax_credit_eligible_count`: count of active with `used_ev_tax_credit.get("eligible") == True`

### 1.4 New Repository Methods
- `async def get_market_overview(self) -> Dict[str, Any]`
- `async def get_market_cohorts(self, cohort_key: Optional[str] = None, make: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]`
- `async def get_dealer_arbitrage(self) -> Dict[str, Any]`
- `async def get_listing_analysis(self, listing_id: str) -> Optional[Dict[str, Any]]` (builds complete 7-section dossier: `deal`, `cohort`, `snapshots`, `depreciation_3yr`, `leverage`, `tax_credit`, `safety_posture`, `epa`, `model_profile` — fetching cached/best-effort NHTSA/EPA profile only without blocking indefinitely or failing if offline!)
- `async def get_compare_data(self, ids: List[str]) -> Dict[str, Any]`
- Update `get_listing_history(self, listing_id: str)`:
  - When `HAS_SQLALCHEMY` is False or `self._fallback_deals is not None` or DB fails/empty, use `target.get("price_history")` (newest first or formatted cleanly with `time`, `price`, `days_on_market`, `price_change`) before falling back to single synthetic snapshot!
- Update `toggle_user_flag(self, listing_id: str, flag_key: str)`:
  - Validate `flag_key in ("user_bookmarked", "user_dismissed")` (raise `ValueError` or return `None` if invalid).
  - Support toggling in `self._offline_sample_cache` when operating in `offline-sample` mode!

### 1.5 Enriched Exports
- `export_deals_csv(deals: List[Dict[str, Any]]) -> str`:
  - Keep all 19 original CSV headers in their exact names & positions (or append new columns after `"URL"` so any column-header checks pass cleanly: append `"Cohort Pctl"`, `"Est. MSRP ($)"`, `"MSRP Off (%)"`, `"DOM (days)"`, `"Leverage Score"`, `"3-Yr Dep ($)"`, `"3-Yr TCO Delta ($)"`, `"EV Tax Credit ($)"`, `"Safety Posture"`).
- `export_deals_markdown(deals: List[Dict[str, Any]]) -> str`:
  - Preserve `"TOP VEHICLE DEALS FOUND"` header and include cohort percentile, leverage score, 3-yr TCO, and EV credit highlights when present.

---

## 2. `tests/test_queries_v2_unittest.py` Specification
Verify:
- `DashboardRepository(fallback_deals=None)` falls back gracefully to 24 offline sample deals when DB/SQLAlchemy unavailable, reporting `provenance["mode"] == "offline-sample"`.
- `DashboardRepository(fallback_deals=_sample_deals())` keeps exact count & fixture provenance, and `get_listing_history` returns all multi-snapshot entries from `price_history`.
- `toggle_user_flag` toggles bookmarks/dismissals cleanly in both fixture and offline-sample modes.
- `filter_and_sort_deals` supports `leverage_desc` and `dom_desc`.
- `get_market_overview`, `get_market_cohorts`, `get_dealer_arbitrage`, `get_listing_analysis`, and `get_compare_data` return expected shapes and accurate math.
- `export_deals_csv` and `export_deals_markdown` preserve original fields and include new quantitative columns.
