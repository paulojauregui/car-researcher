# Market Analysis & Quantitative Valuation Specification (`v2-market-intelligence`)

## 1. Objective & Architectural Placement

This specification defines the quantitative market intelligence layer for `car-researcher`. All analytics logic is pure, deterministic, zero-dependency Python 3.14/3.15 compatible, and strictly isolated outside Temporal workflow code (`src/workflows/`) to uphold `AGENTS.md` Rule 1 (Temporal Determinism) and Rule 2 (Zero-Dependency Fallback Pattern).

### Module Allocation
- **`src/activities/market_analytics.py`**: Pure statistical, depreciation, price velocity, negotiation leverage, tax-credit, safety posture, cohort aggregation, and dealer/platform arbitrage functions.
- **`src/dashboard/sample_data.py`**: Rich Bay Area EV representative offline-sample dataset (`24` multi-model listings across all `14` target watchlist EVs, spanning both `carscom` and `cargurus`, Bay Area ZIPs/dealers, varied DOM, and multi-snapshot `price_history`).
- **`src/dashboard/queries.py`**: Database integration (`DashboardRepository`), cohort enrichment pipeline, provenance tracking (`timescaledb` vs `offline-sample` vs `fixture`), and enriched CSV/Markdown exports.
- **`src/dashboard/app.py`**: Backward-compatible HTTP/ASGI endpoints plus new v2 JSON analytics endpoints and path-safe static asset serving.

---

## 2. Empirical Cohort Distribution & Valuation Bands

Active (non-dismissed, `price > 0`) inventory is partitioned into valuation cohorts:

1. **Cohort Key Resolution**:
   - Primary cohort key: `"{make}|{model}|{year}"`.
   - Fallback cohort key: When `sample_size < 3` for an exact `(make, model, year)` group, fall back to `"{make}|{model}|ALL"` across model years and set `cohort_scope = "model_fallback"`; otherwise `cohort_scope = "exact_year"`.
2. **Confidence Tier**:
   - `HIGH`: `sample_size >= 8`
   - `MEDIUM`: `3 <= sample_size < 8`
   - `LOW`: `sample_size < 3`
3. **Distribution Statistics** (computed via deterministic linear-interpolated `_percentile(sorted_prices, p)`):
   - `min_price`, `p10`, `p25` (Buy-Zone cutoff), `p50` (Median), `p75`, `max_price`
   - `iqr = p75 - p25`
   - `mean_price`, `std_dev` (population standard deviation across cohort)
   - `fair_band = [p25, p50, p75]`
   - `median_price_per_1k_miles` (`price / max(1.0, mileage / 1000.0)`)
   - `avg_msrp`, `avg_msrp_discount_pct` (`((avg_msrp - p50) / avg_msrp) * 100`)
   - `avg_dom`, `price_cut_count`, `price_cut_share_pct`
4. **Per-Listing Cohort Metrics**:
   - `cohort_percentile` (`0.0` to `100.0`, percentage of cohort peers priced at or below listing)
   - `cohort_z_score` (`round((price - mean_price) / std_dev, 2)` when `std_dev > 0`, else `0.0`)
   - `price_per_1k_miles` (`round(price / max(1.0, mileage / 1000.0), 1)`)
   - `estimated_msrp`: Resolved via `DealScorer.get_estimated_original_msrp(...)` or `score_breakdown["estimated_msrp"]`
   - `msrp_discount_pct`: `round(((estimated_msrp - price) / max(1, estimated_msrp)) * 100.0, 1)`

---

## 3. Temporal Liquidity, Price Velocity & Negotiation Leverage

Using TimescaleDB `price_snapshots` (ordered chronologically) combined with `days_on_market` (`DOM`):

1. **Price Velocity Metrics**:
   - `initial_price`: Earliest recorded snapshot price (or `price - price_change` when only 1 snapshot with a recorded `price_change` exists).
   - `price_drop_total`: `max(0, initial_price - current_price)` (or `abs(price_change)` if `price_change < 0` and no older snapshot exists).
   - `price_drop_pct`: `round((price_drop_total / max(1, initial_price)) * 100.0, 1)`.
   - `price_drop_count`: Number of negative price steps across snapshots (minimum `1` if `price_change < 0`).
   - `price_velocity_per_week`: `round(price_drop_total / max(1.0, days_on_market / 7.0), 2)` USD reduced per week on market.
2. **Negotiation Leverage Score (`0.0` to `100.0`)**:
   - **DOM Stale Inventory Component (max 40 pts)**: `min(40.0, days_on_market * 0.65)` (peaks around 62+ days).
   - **Price-Cut Momentum Component (max 25 pts)**: `min(25.0, price_drop_count * 9.0 + price_drop_pct * 1.5)`.
   - **Pricing / Cohort Headroom Component (max 20 pts)**:
     - If priced above `p25`: `min(20.0, max(5.0, ((price - p25) / max(1.0, p25)) * 80.0))` (more room for dealer concession).
     - If already below `p25`: `10.0` (seller already aggressively discounted; moderate room for closing fee concessions).
   - **Channel & Carrying Friction Component (max 15 pts)**: `+10.0` if non-CPO dealer inventory with `DOM >= 21`, `+5.0` if multiple snapshots recorded.
   - `leverage_tier`: `HIGH` (`>= 70`), `MODERATE` (`45..69.9`), `LOW` (`< 45`).
   - `suggested_offer_low`, `suggested_offer_target`: Actionable buyer opening & target offer bounds anchored around `min(price, p25)` and discounted by `2%..6%` scaled by leverage.
3. **Deterministic Market Badges** (`market_badges: List[str]`):
   - `BELOW_P25_COHORT`: `price <= p25` (when cohort `sample_size >= 2`) or `pct_savings <= -8.0`
   - `FRESH_PRICE_CUT`: `price_change < 0` or `price_drop_total > 0`
   - `STALE_INVENTORY_30D`: `days_on_market >= 30`
   - `HIGH_LEVERAGE`: `negotiation_leverage_score >= 70.0`
   - `USED_EV_TAX_CREDIT`: Eligible for federal Clean Vehicle Credit signal

---

## 4. 3-Year Depreciation Curve, Carrying Cost & Used EV Tax Credit

1. **3-Year Depreciation Projection**:
   - Uses `DealScorer._interpolate_retention` with `LUXURY_RETENTION_ANCHORS` (Mercedes-Benz, BMW, Cadillac, Audi, Genesis, Porsche, Polestar) or `STANDARD_RETENTION_ANCHORS`.
   - `age_now = max(0.5, float(current_year - year))`, `age_3yr = age_now + 3.0`.
   - `projected_3yr_residual = DealScorer.calculate_fair_market_value(estimated_msrp, age_3yr, mileage + 36000, is_luxury=is_luxury)`.
   - `projected_3yr_depreciation = max(0, price - projected_3yr_residual)`.
2. **EPA Range & 3-Year Energy Cost**:
   - Uses cached/live EPA `EPAFuelEconomy` when available, falling back to `MODEL_EPA_DEFAULTS` lookup across all 14 target models (`range_miles`, `comb_mpge`, `annual_fuel_cost`).
   - `energy_cost_3yr = annual_fuel_cost * 3`.
3. **Used Clean Vehicle Credit Eligibility Signal** (`used_ev_tax_credit`):
   - `eligible = (price <= 25000) and (year <= current_year - 2) and (title_status.lower() == "clean")`.
   - `potential_credit_usd = 4000 if eligible else 0`.
   - `note`: Informational disclaimer stating IRS AGI, point-of-sale dealer registration, and single-transfer rules apply.
4. **3-Year Total Ownership Delta**:
   - `total_3yr_ownership_delta = projected_3yr_depreciation + energy_cost_3yr - potential_credit_usd`.

---

## 5. Price-vs-Mileage Frontier & Dealer/Platform Arbitrage

1. **OLS Linear Trendline (`_ols_regression`)**:
   - For any cohort (or overall dataset), computes `slope`, `intercept`, `r2` across `(mileage / 1000.0, price)` pairs.
   - Emits `slope_per_1k_miles`, `intercept`, `r2`, `p25_line`, `p50_line`, and `scatter_points`.
2. **Dealer Arbitrage Matrix (`compute_dealer_and_platform_arbitrage`)**:
   - Aggregates active inventory per `seller_name` (`listing_count`, `city`, `distance_miles`, `median_pct_vs_fmv`, `avg_price_delta`, `avg_dom`, `avg_deal_score`, `price_cut_count`, `price_cut_pct`, `best_deal_id`).
3. **Platform Spread (`CARSCOM` vs `CARGURUS`)**:
   - Compares channel pricing efficiency (`listing_count`, `median_pct_vs_fmv`, `avg_price`, `avg_dom`, `avg_deal_score`, `price_cut_pct`).
4. **Bay Area Distance-Tier Summary**:
   - Groups into `0-15 mi`, `15-30 mi`, `30-60 mi`, `60+ mi` buckets.

---

## 6. Consolidated Safety & Provenance Posture

- `safety_posture`:
  - `ELEVATED`: non-clean title (`SALVAGE`/`REBUILT`/`LEMON`), `accident_count >= 2`, `fire_count > 0`, `crash_count > 0`, or `recalls_count >= 3`.
  - `MODERATE`: `accident_count == 1`, `owner_count >= 3`, or `1 <= recalls_count <= 2`.
  - `LOW`: clean title, `0` accidents, `< 3` owners, `0` unmitigated high-risk flags.

---

## 7. REST JSON & Export API Contracts

### Existing Preserved Endpoints
- `GET /`, `HEAD /`
- `GET /partials/deals`, `GET /partials/kpis`
- `GET /partials/listing/{id}/history`, `GET /partials/model-profile`
- `POST /api/listing/{id}/bookmark`, `POST /api/listing/{id}/dismiss`, `POST /api/listings/{id}/flag/{key}`
- `POST /api/scan`, `GET /api/scan/status`, `GET /api/scan/{wf_id}/status`
- `GET /api/export/csv`, `GET /api/export/markdown`
- `GET /api/deals`, `GET /api/health`

### New v2 Market Intelligence Endpoints
- `GET /api/market/overview`: Returns `{provenance, kpis, leaderboard, price_cut_movers, stale_high_leverage, target_models}`.
- `GET /api/market/cohorts`: Accepts optional `?cohort=<key>` or `?make=<make>&model=<model>`. Returns `{provenance, cohorts, selected_cohort, scatter}`.
- `GET /api/market/dealers`: Returns `{provenance, dealers, platforms, distance_bands}`.
- `GET /api/listings/{id}/history`: Returns JSON `{deal, snapshots}`.
- `GET /api/listings/{id}/analysis`: Returns JSON `{deal, cohort, snapshots, depreciation_3yr, leverage, tax_credit, safety_posture, epa, model_profile}`.
- `GET /api/models/{make}/{model}/{year}`: Returns JSON NHTSA recalls, ODI complaints, and EPA fuel economy profile.
- `GET /api/compare?ids=a,b,c`: Returns JSON `{count, items, highlights}` normalizing up to `3` listings with best-in-category winner flags.
