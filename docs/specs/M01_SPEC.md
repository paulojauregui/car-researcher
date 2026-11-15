# Milestone M01 Specification: Settings Extension & Quantitative Market Analytics Engine

## Target Files
- `src/config/settings.py`
- `src/activities/market_analytics.py`
- `tests/test_market_analytics_unittest.py`

## Non-Negotiable Constraints
- Strictly zero emojis anywhere in code, docstrings, comments, or tests.
- Zero external pip dependencies in `src/activities/market_analytics.py` (Python 3.11+ standard library only: `math`, `statistics`, `typing`, `datetime`).
- Absolute imports exclusively (`from src.... import ...`).
- Every new/modified class, method, and function MUST have `"""..."""` docstrings containing explicit `Pre-conditions:` and `Post-conditions:`, plus complete static type annotations.
- Preserve existing `HAS_PYDANTIC` / `dataclass` fallback in `src/config/settings.py`.

---

## 1. `src/config/settings.py` Changes
Add optional `temporal_ui_url` setting to `Settings` (both `HAS_PYDANTIC` branch and `else` dataclass fallback branch):
- `HAS_PYDANTIC` branch:
  ```python
  temporal_ui_url: Optional[str] = None
  ```
  (Reads `TEMPORAL_UI_URL` automatically via `pydantic-settings`).
- Fallback dataclass branch:
  ```python
  temporal_ui_url: Optional[str] = field(default_factory=lambda: (os.environ.get("TEMPORAL_UI_URL") or "").strip() or None)
  ```
- Also ensure `Settings` has a docstring with `Pre-conditions:` and `Post-conditions:`. No hardcoded `http://localhost:8080` anywhere.

---

## 2. `src/activities/market_analytics.py` Specification

### 2.1 Reference Lookup Constants
- `MODEL_EPA_DEFAULTS: Dict[str, Dict[str, Any]]` covering all 14 watchlist models (keyed by lowercase `"make:model"`, e.g. `"mercedes-benz:eqs"`, `"mercedes-benz:eqe"`, `"cadillac:lyriq"`, `"genesis:gv60"`, `"bmw:i4"`, `"audi:q4 e-tron"`, `"polestar:2"`, `"tesla:model y"`, `"tesla:model 3"`, `"ford:mustang mach-e"`, `"hyundai:ioniq 5"`, `"hyundai:ioniq 6"`, `"kia:ev6"`, `"chevrolet:bolt euv"`):
  Each value dict contains: `range_miles: int`, `comb_mpge: float`, `annual_fuel_cost: int`.
- `LUXURY_MAKE_PREFIXES: Tuple[str, ...] = ("mercedes", "bmw", "cadillac", "audi", "genesis", "porsche", "polestar")`

### 2.2 Pure Math Helpers
1. `compute_percentile(sorted_values: List[float], percentile: float) -> float`
   - Linear interpolation across sorted numeric list (`0.0 <= percentile <= 100.0`).
   - Returns `0.0` if `sorted_values` is empty.
2. `compute_ols_regression(points: List[Tuple[float, float]]) -> Dict[str, float]`
   - Input points `(x_k_miles, y_price)`.
   - Returns `{"slope_per_1k_miles": float, "intercept": float, "r2": float}`.
   - Handles `len(points) < 2` or zero x-variance gracefully by returning `0.0` slope and `0.0` r2 (intercept = mean y if non-empty else 0.0).
3. `get_model_epa_baseline(make: str, model: str, model_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]`
   - Uses live `model_profile["epa_specs"][0]` if present, otherwise looks up `MODEL_EPA_DEFAULTS` (exact or fuzzy substring match), falling back to `{"range_miles": 270, "comb_mpge": 102.0, "annual_fuel_cost": 750}` with `source: "live_epa" | "watchlist_baseline"`.

### 2.3 Cohort Grouping & Valuation Bands
`compute_cohort_stats(listings: List[Dict[str, Any]]) -> Dict[str, Any]`
- Filters active (`not is_dismissed` and `price > 0`) normalized listings.
- Builds primary cohorts keyed by `"{make}|{model}|{year}"` and fallback model-wide cohorts keyed by `"{make}|{model}|ALL"`.
- For each listing, assigns its effective cohort: exact `(make, model, year)` if `sample_size >= 3` (`cohort_scope = "exact_year"`), else `(make, model, ALL)` (`cohort_scope = "model_fallback"`; if even model-wide `< 3`, still assigns the cohort with `confidence_tier = "LOW"`).
- Confidence tiers: `"HIGH"` (`n >= 8`), `"MEDIUM"` (`3 <= n < 8`), `"LOW"` (`n < 3`).
- For every cohort key (both exact and model-wide) AND `"ALL"` aggregate, computes:
  - `cohort_key`, `label`, `make`, `model`, `year` (int or `"ALL"`), `cohort_scope`, `sample_size`, `confidence_tier`
  - `min_price`, `p10`, `p25`, `p50`, `p75`, `max_price`, `iqr`, `mean_price`, `std_dev`
  - `fair_low` (`p25`), `fair_median` (`p50`), `fair_high` (`p75`)
  - `avg_mileage`, `median_price_per_1k_miles`
  - `avg_msrp`, `avg_msrp_discount_pct`
  - `avg_dom`, `price_cut_count`, `price_cut_share_pct`, `below_p25_count`, `top_deal_score`
  - `ols_trendline`: `compute_ols_regression([(d["mileage"]/1000.0, d["price"]) ...])`
  - `scatter_points`: list of dicts `{id, title, trim_detail, make, model, year, mileage, price, market_value, deal_score, pct_savings, price_delta, days_on_market, price_drop_total, below_p25, cohort_percentile, seller_name, location_city, platform, price_per_1k_miles}`.
- Returns `{"cohorts": Dict[str, Dict[str, Any]], "listing_cohort_map": Dict[str, str], "all_scatter": Dict[str, Any]}`.

### 2.4 Per-Listing Quantitative Enrichment
`enrich_listing_analytics(listing: Dict[str, Any], cohort: Dict[str, Any], snapshots: Optional[List[Dict[str, Any]]] = None, model_profile: Optional[Dict[str, Any]] = None, current_year: int = 2026) -> Dict[str, Any]`
Computes and returns a structured analytics dict (also merged cleanly into enriched listings):
1. **Cohort Position**:
   - `cohort_key`, `cohort_scope`, `cohort_sample_size`, `cohort_confidence`
   - `cohort_p10`, `cohort_p25`, `cohort_p50`, `cohort_p75`, `cohort_min`, `cohort_max`, `fair_band` (`[p25, p50, p75]`)
   - `cohort_percentile`: `round(pct, 1)` (`0.0..100.0`)
   - `cohort_z_score`: `round((price - mean_price) / std_dev, 2)` (or `0.0`)
   - `price_per_1k_miles`: `round(price / max(1.0, mileage / 1000.0), 1)`
   - `estimated_msrp`: via `score_breakdown.get("estimated_msrp")` or `DealScorer.get_estimated_original_msrp(...)`
   - `msrp_discount_pct`: `round(((estimated_msrp - price) / max(1, estimated_msrp)) * 100.0, 1)`
2. **Temporal Liquidity, Velocity & Negotiation Leverage**:
   - Chronologically orders `snapshots` (or `listing.get("price_history")`):
     - `initial_price`, `price_drop_total`, `price_drop_pct`, `price_drop_count`, `price_velocity_per_week`
   - **Negotiation Leverage Score (`0.0..100.0`)**:
     - `dom_component` (max `40.0`): `min(40.0, dom * 0.65)`
     - `velocity_component` (max `25.0`): `min(25.0, price_drop_count * 9.0 + price_drop_pct * 1.5)`
     - `headroom_component` (max `20.0`): `min(20.0, max(5.0, ((price - p25) / max(1.0, p25)) * 80.0))` if `price > p25` else `10.0`
     - `friction_component` (max `15.0`): `(10.0 if (dom >= 21 and not cpo) else 4.0 if dom >= 14 else 0.0) + (5.0 if snapshot_count >= 2 else 0.0)`
     - `negotiation_leverage_score = round(min(100.0, dom_component + velocity_component + headroom_component + friction_component), 1)`
     - `leverage_tier`: `"HIGH"` (`>= 70.0`), `"MODERATE"` (`>= 45.0`), `"LOW"` (`< 45.0`)
     - `suggested_offer_low`, `suggested_offer_target` (bounded positive integers `<= price`)
3. **3-Year Depreciation, Carrying Cost & Used EV Tax Credit**:
   - `is_luxury` via `LUXURY_MAKE_PREFIXES`
   - `age_now = max(0.5, float(current_year - year))`, `age_3yr = age_now + 3.0`
   - `projected_3yr_residual = DealScorer.calculate_fair_market_value(estimated_msrp, age_3yr, mileage + 36000, is_luxury=is_luxury)`
   - `projected_3yr_depreciation = max(0, price - projected_3yr_residual)`
   - `epa = get_model_epa_baseline(make, model, model_profile)`
   - `energy_cost_3yr = int(epa["annual_fuel_cost"] * 3)`
   - `used_ev_tax_credit`:
     - `eligible: bool = (price <= 25000) and (year <= current_year - 2) and (title_status == "CLEAN")`
     - `potential_credit_usd: int = 4000 if eligible else 0`
     - `reasons: Dict[str, bool]` (`price_under_25k`, `model_year_2plus_years_old`, `clean_title`)
     - `note`: `"Informational estimate only; IRS buyer AGI limits, dealer point-of-sale registration, and first-resale VIN transfer rules apply."`
   - `total_3yr_ownership_delta = projected_3yr_depreciation + energy_cost_3yr - potential_credit_usd`
4. **Safety Posture**:
   - `safety_posture`: `"ELEVATED"` / `"MODERATE"` / `"LOW"`
5. **Deterministic Market Badges (`market_badges: List[str]`)**:
   - `"BELOW_P25_COHORT"`, `"FRESH_PRICE_CUT"`, `"STALE_INVENTORY_30D"`, `"HIGH_LEVERAGE"`, `"USED_EV_TAX_CREDIT"`

### 2.5 Collection Enrichment & Aggregations
- `enrich_collection_with_analytics(deals: List[Dict[str, Any]], current_year: int = 2026) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]`
  - Computes cohorts and attaches all enriched fields directly onto each returned deal dict copy while preserving all original keys.
- `compute_dealer_and_platform_arbitrage(enriched_deals: List[Dict[str, Any]]) -> Dict[str, Any]`
  - Returns `{"dealers": [...], "platforms": [...], "distance_bands": [...]}` across active (`not is_dismissed`) deals.
- `compute_market_overview(enriched_deals: List[Dict[str, Any]], cohorts_data: Dict[str, Any], target_models: Optional[List[Dict[str, Any]]] = None, provenance: Optional[Dict[str, Any]] = None) -> Dict[str, Any]`
  - Returns `{"provenance": ..., "kpis": ..., "leaderboard": ..., "price_cut_movers": ..., "stale_high_leverage": ...}`. Ensure `leaderboard` includes all `target_models` (with `sample_size: 0` if absent from active deals) so the 14-Model Watchlist Cohort Leaderboard renders full coverage!
- `build_compare_payload(enriched_deals: List[Dict[str, Any]], ids: List[str]) -> Dict[str, Any]`
  - Normalizes up to 3 requested IDs preserving requested order and computes deterministic `highlights` winner map (`lowest_vs_fmv_id`, `highest_msrp_discount_id`, `highest_score_id`, `highest_leverage_id`, `lowest_3yr_tco_id`, `tax_credit_ids`, `highest_range_id`, `highest_dom_id`, `closest_distance_id`, `lowest_risk_ids`).

## 3. Unit Tests (`tests/test_market_analytics_unittest.py`)
Verify:
- `TEMPORAL_UI_URL` setting read & `None` default.
- Percentile & OLS regression math (known dataset + edge cases `n=0`, `n=1`, zero variance).
- Exact cohort vs model fallback (`n < 3`), confidence tiers (`HIGH`, `MEDIUM`, `LOW`).
- Price velocity & multi-snapshot drops, Negotiation Leverage bounds `[0, 100]`, Market badges generation.
- 3-year depreciation & TCO calculation + Used EV `$4,000` Tax Credit eligibility boundary (`$25,000`, `<= current_year - 2`, clean title vs salvage/high price).
- Dealer, platform (`CARSCOM` vs `CARGURUS`), and Bay Area distance-band aggregations.
- Watchlist 14-model leaderboard including 0-count gap models.
- Side-by-side compare winner highlights for up to 3 listings.
