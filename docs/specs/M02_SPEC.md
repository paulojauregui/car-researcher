# Milestone M02 Specification: Representative Multi-Snapshot Offline Bay Area Sample Dataset

## Target Files
- `src/dashboard/sample_data.py`
- `tests/test_sample_data_unittest.py`

## Non-Negotiable Constraints
- Strictly zero emojis anywhere in code, docstrings, comments, sample data strings, or tests.
- Zero external pip dependencies (Python stdlib + `src.activities.scoring` + `src.models.domain` + `src.config.settings` only).
- Absolute imports exclusively (`from src.... import ...`).
- Every class, method, and function MUST have `"""..."""` docstrings with `Pre-conditions:` and `Post-conditions:` and full static type annotations.

---

## 1. `src/dashboard/sample_data.py` Specification
Create `get_offline_sample_deals() -> List[Dict[str, Any]]` returning a fresh deep copy (`copy.deepcopy`) of a deterministic, realistic `24`-vehicle Bay Area EV sample dataset when PostgreSQL/TimescaleDB is unavailable:

### Required Coverage & Realism Rules
1. **Full 14-Model Watchlist Coverage**:
   - Include at least 1 listing for **every single model** in `DEFAULT_TARGET_MODELS` (`Hyundai Ioniq 5`, `Hyundai Ioniq 6`, `Kia EV6`, `Tesla Model Y`, `Tesla Model 3`, `Ford Mustang Mach-E`, `Chevrolet Bolt EUV`, `BMW i4`, `Mercedes-Benz EQS`, `Mercedes-Benz EQE`, `Cadillac Lyriq`, `Genesis GV60`, `Polestar 2`, `Audi Q4 e-tron`), with multiple listings (`n >= 3`) on key models (e.g., `Mercedes-Benz EQS`, `BMW i4`, `Hyundai Ioniq 5`, `Tesla Model Y`) so both exact-year (`n >= 3`) AND model-fallback / low-sample (`n < 3`) cohorts appear realistically!
2. **Both Platforms**:
   - Mix of `"carscom"` and `"cargurus"` across the `24` listings (`12` and `12` or `13` and `11`).
3. **Diverse Bay Area Dealerships & Valid ZIPs**:
   - Use real ZIPs present in `BAY_AREA_ZIP_COORDS` (`94103` SF, `94010` Burlingame, `94401` San Mateo, `94063` Redwood City, `94040` Mountain View, `95050` Santa Clara, `95128` San Jose, `94612` Oakland, `94596` Walnut Creek, `94538` Fremont, `94901` San Rafael, `94568` Dublin) stored inside `raw_data["seller_zip"]` so `BayAreaGeoLookup.resolve_zip` resolves dynamic distances across `0-15`, `15-30`, and `30-60` mi bands.
   - Include multiple listings at shared dealerships (e.g., `Mercedes-Benz of Stevens Creek`, `Autobahn Motors`, `BMW of San Francisco`, `Putnam Hyundai`, `Oakland Kia`, `Fremont Tesla Hub`) so Dealer Arbitrage aggregation shows rich multi-listing dealer averages.
4. **Realistic Multi-Snapshot `price_history` & Varied DOM**:
   - At least `14` listings must include `2` to `5` chronological `price_history` snapshots (`time`, `price`, `days_on_market`, `price_change`) showing realistic price drops over `14` to `78` days on market.
   - Remaining newer listings (`DOM` `3` to `12` days) include `1` or `2` snapshots.
   - Ensure `price_change` on the listing matches the latest snapshot's `price_change`, and `snapshot_count` matches `len(price_history)`.
5. **Used EV Tax Credit & Score Spectrum**:
   - Include at least `2` clean-title `<= $25,000` EVs (`model_year <= 2024`, e.g., `2023 Chevrolet Bolt EUV` at `$22,900` and `2022 Tesla Model 3` at `$24,490`) so the `$4,000` Used Clean Vehicle Credit eligibility signal (`USED_EV_TAX_CREDIT`) triggers deterministically.
   - Include high-conviction `EXCELLENT_DEAL` (`>= 85`), `GOOD_VALUE` (`75..84.9`), `FAIR_MARKET` (`60..74.9`), and at least one `OVERPRICED_OR_HIGH_RISK` (`< 60` or `1` accident / higher price) listing so every triage tab and score color tier is meaningfully exercised.
6. **Empirical Scoring Consistency**:
   - Compute `market_value`, `price_delta`, `deal_score`, `recommendation`, `score_breakdown` (plus `estimated_msrp`) dynamically or via `DealScorer.score_listing(...)` inside a cached helper (`_build_sample_deals()`) so `score_breakdown` and `market_value` are mathematically consistent with `src/activities/scoring.py`!
   - Every listing has deterministic UUID-format `id` (`"00000000-0000-4000-8000-000000000001"` .. `"00000000-0000-4000-8000-000000000024"`), realistic 17-character synthetic `vin`, `platform`, `platform_id`, `url`, `title`, `make`, `model`, `year`, `trim_detail`, `price`, `mileage`, `exterior_color`, `interior_color`, `seller_name`, `location_city`, `distance_miles`, `title_status`, `accident_count`, `owner_count`, `photos: []`, `raw_data`, `price_change`, `days_on_market`, `snapshot_count`, `price_history`.

---

## 2. `tests/test_sample_data_unittest.py` Specification
Verify:
- `len(get_offline_sample_deals()) >= 24` and mutations to returned dicts do not leak across calls (`copy.deepcopy` freshness).
- Every `(make, model)` in `DEFAULT_TARGET_MODELS` appears in the sample set.
- Both `carscom` and `cargurus` platforms appear.
- Multi-snapshot `price_history` arrays exist with valid monotonically ordered timestamps and accurate `price_change`/`snapshot_count`.
- At least `2` listings qualify for `USED_EV_TAX_CREDIT` and multiple score tiers exist.
- Passing the sample deals through `enrich_collection_with_analytics` produces valid cohorts, dealer arbitrage, and zero exceptions.
