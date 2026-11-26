import os
import unittest
from typing import Any, Dict, List

from src.activities.market_analytics import (
    MODEL_EPA_DEFAULTS,
    LUXURY_MAKE_PREFIXES,
    build_compare_payload,
    compute_cohort_stats,
    compute_dealer_and_platform_arbitrage,
    compute_market_overview,
    compute_ols_regression,
    compute_percentile,
    enrich_collection_with_analytics,
    enrich_listing_analytics,
    get_model_epa_baseline,
)
from src.config.settings import DEFAULT_TARGET_MODELS, Settings


class TestMarketAnalyticsUnit(unittest.TestCase):
    """
    Unit test suite for settings extension, quantitative market analytics, and cohort statistics.

    Pre-conditions:
        - Python 3.11+ standard library environment without third-party pip dependencies.
        - All modules in src.activities.market_analytics and src.config.settings are importable.

    Post-conditions:
        - All statistical and financial formulas match specified invariants.
        - Settings properly load temporal_ui_url defaults and environment overrides.
    """

    def test_temporal_ui_url_settings(self) -> None:
        """
        Verify temporal_ui_url defaults to None and correctly honors non-empty environment overrides.

        Pre-conditions:
            - TEMPORAL_UI_URL environment variable may or may not be set in process environment.

        Post-conditions:
            - Settings instances without environment override resolve temporal_ui_url to None.
            - Setting TEMPORAL_UI_URL to a valid URL string resolves cleanly.
            - Blank or whitespace-only TEMPORAL_UI_URL normalizes to None.
        """
        old_val = os.environ.get("TEMPORAL_UI_URL")
        try:
            # 1. Unset environment variable -> None
            if "TEMPORAL_UI_URL" in os.environ:
                del os.environ["TEMPORAL_UI_URL"]
            s_default = Settings()
            self.assertIsNone(s_default.temporal_ui_url)

            # 2. Valid URL override
            os.environ["TEMPORAL_UI_URL"] = "https://temporal.example.com"
            s_custom = Settings()
            self.assertEqual(s_custom.temporal_ui_url, "https://temporal.example.com")

            # 3. Whitespace-only string -> normalizes to None
            os.environ["TEMPORAL_UI_URL"] = "   "
            s_blank = Settings()
            self.assertIsNone(s_blank.temporal_ui_url)

            # 4. Direct parameter initialization
            s_param = Settings(temporal_ui_url="  https://temporal-direct.test  ")
            self.assertEqual(s_param.temporal_ui_url, "https://temporal-direct.test")
        finally:
            if old_val is not None:
                os.environ["TEMPORAL_UI_URL"] = old_val
            elif "TEMPORAL_UI_URL" in os.environ:
                del os.environ["TEMPORAL_UI_URL"]

    def test_percentile_computation(self) -> None:
        """
        Verify linear interpolation percentile calculations across odd, even, and edge-case inputs.

        Pre-conditions:
            - Sorted float lists of lengths 0, 1, 2, and 5.

        Post-conditions:
            - Empty list returns 0.0.
            - Single element returns value regardless of percentile.
            - Linear interpolation computes exact medians and quartile values.
            - Percentiles outside [0, 100] are clamped without throwing exceptions.
        """
        self.assertEqual(compute_percentile([], 50.0), 0.0)
        self.assertEqual(compute_percentile([42.5], 25.0), 42.5)

        data = [10.0, 20.0, 30.0, 40.0, 50.0]
        self.assertEqual(compute_percentile(data, 0.0), 10.0)
        self.assertEqual(compute_percentile(data, 50.0), 30.0)
        self.assertEqual(compute_percentile(data, 100.0), 50.0)
        self.assertEqual(compute_percentile(data, 25.0), 20.0)
        self.assertEqual(compute_percentile(data, 75.0), 40.0)

        two_items = [10.0, 20.0]
        self.assertEqual(compute_percentile(two_items, 50.0), 15.0)

        # Clamping
        self.assertEqual(compute_percentile(data, -10.0), 10.0)
        self.assertEqual(compute_percentile(data, 120.0), 50.0)

    def test_ols_regression(self) -> None:
        """
        Verify ordinary least squares regression slope, intercept, and r2 calculations.

        Pre-conditions:
            - Coordinate points representing (mileage_k, price).

        Post-conditions:
            - Degenerate cases (n < 2, zero x variance) return slope 0.0 and r2 0.0 with mean y intercept.
            - Linearly dependent points return exact expected slope, intercept, and r2 of 1.0.
        """
        # Empty
        res_empty = compute_ols_regression([])
        self.assertEqual(res_empty, {"slope_per_1k_miles": 0.0, "intercept": 0.0, "r2": 0.0})

        # Single point
        res_one = compute_ols_regression([(15.0, 30000.0)])
        self.assertEqual(res_one, {"slope_per_1k_miles": 0.0, "intercept": 30000.0, "r2": 0.0})

        # Zero variance in x
        res_zero_var = compute_ols_regression([(10.0, 25000.0), (10.0, 35000.0)])
        self.assertEqual(res_zero_var, {"slope_per_1k_miles": 0.0, "intercept": 30000.0, "r2": 0.0})

        # Linear line: y = 32000 - 200 * x
        points = [(10.0, 30000.0), (20.0, 28000.0), (30.0, 26000.0)]
        res_linear = compute_ols_regression(points)
        self.assertEqual(res_linear["slope_per_1k_miles"], -200.0)
        self.assertEqual(res_linear["intercept"], 32000.0)
        self.assertEqual(res_linear["r2"], 1.0)

    def test_epa_baseline_resolution(self) -> None:
        """
        Verify live EPA extraction, static watchlist lookup, and generic fallback behavior.

        Pre-conditions:
            - Live model profile payload, watchlist model strings, and unknown models.

        Post-conditions:
            - Returns live_epa when model_profile epa_specs are present.
            - Returns watchlist_baseline with 14-model defaults when model_profile is absent.
            - Returns conservative generic fallback for unknown makes.
        """
        # Live EPA
        profile = {"epa_specs": [{"range_miles": 312, "comb_mpge": 99.0, "annual_fuel_cost": 700}]}
        res_live = get_model_epa_baseline("Tesla", "Model Y", profile)
        self.assertEqual(res_live["source"], "live_epa")
        self.assertEqual(res_live["range_miles"], 312)

        # Exact watchlist lookup
        res_bmw = get_model_epa_baseline("BMW", "i4")
        self.assertEqual(res_bmw["source"], "watchlist_baseline")
        self.assertEqual(res_bmw["range_miles"], 301)
        self.assertEqual(res_bmw["comb_mpge"], 109.0)

        # Fuzzy substring lookup
        res_eqs = get_model_epa_baseline("Mercedes-Benz", "EQS 450+ 4MATIC")
        self.assertEqual(res_eqs["source"], "watchlist_baseline")
        self.assertEqual(res_eqs["range_miles"], 350)

        # Generic fallback
        res_generic = get_model_epa_baseline("UnknownMake", "UnknownModel")
        self.assertEqual(res_generic["source"], "watchlist_baseline")
        self.assertEqual(res_generic["range_miles"], 270)
        self.assertEqual(res_generic["comb_mpge"], 102.0)

    def test_cohort_stats_and_fallback(self) -> None:
        """
        Verify cohort partitioning, exact-year vs model-fallback assignment, and confidence tiers.

        Pre-conditions:
            - Synthetic listings across multiple models and years.

        Post-conditions:
            - Exact year cohort is assigned when sample size >= 3.
            - Model fallback cohort is assigned when exact year sample size < 3.
            - Confidence tiers HIGH (>=8), MEDIUM (3-7), and LOW (<3) are assigned accurately.
            - Dismissed listings and zero-priced items are filtered from cohort statistics.
        """
        listings: List[Dict[str, Any]] = [
            # 3x Tesla Model 3 2023 -> exact year cohort (sample_size 3 -> MEDIUM)
            {"id": "t3_1", "make": "Tesla", "model": "Model 3", "year": 2023, "price": 31000, "mileage": 15000},
            {"id": "t3_2", "make": "Tesla", "model": "Model 3", "year": 2023, "price": 33000, "mileage": 18000},
            {"id": "t3_3", "make": "Tesla", "model": "Model 3", "year": 2023, "price": 35000, "mileage": 22000},
            # 2x Tesla Model Y 2022 + 1x Tesla Model Y 2023 -> exact year < 3, but model total is 3
            {"id": "ty_1", "make": "Tesla", "model": "Model Y", "year": 2022, "price": 36000, "mileage": 25000},
            {"id": "ty_2", "make": "Tesla", "model": "Model Y", "year": 2022, "price": 38000, "mileage": 28000},
            {"id": "ty_3", "make": "Tesla", "model": "Model Y", "year": 2023, "price": 42000, "mileage": 12000},
            # 1x Rare car -> LOW confidence
            {"id": "rare_1", "make": "Lucid", "model": "Air", "year": 2023, "price": 65000, "mileage": 8000},
            # Dismissed and invalid items
            {"id": "dis_1", "make": "Tesla", "model": "Model 3", "year": 2023, "price": 20000, "is_dismissed": True},
            {"id": "zero_1", "make": "Tesla", "model": "Model 3", "year": 2023, "price": 0},
        ]

        cohorts_res = compute_cohort_stats(listings)
        cohorts = cohorts_res["cohorts"]
        mapping = cohorts_res["listing_cohort_map"]

        # Exact year assignment for Model 3 2023
        self.assertEqual(mapping["t3_1"], "Tesla|Model 3|2023")
        self.assertEqual(cohorts["Tesla|Model 3|2023"]["sample_size"], 3)
        self.assertEqual(cohorts["Tesla|Model 3|2023"]["cohort_scope"], "exact_year")
        self.assertEqual(cohorts["Tesla|Model 3|2023"]["confidence_tier"], "MEDIUM")
        self.assertEqual(cohorts["Tesla|Model 3|2023"]["min_price"], 31000)
        self.assertEqual(cohorts["Tesla|Model 3|2023"]["max_price"], 35000)
        self.assertEqual(cohorts["Tesla|Model 3|2023"]["fair_median"], 33000.0)

        # Model fallback assignment for Model Y 2022
        self.assertEqual(mapping["ty_1"], "Tesla|Model Y|ALL")
        self.assertEqual(cohorts["Tesla|Model Y|ALL"]["sample_size"], 3)
        self.assertEqual(cohorts["Tesla|Model Y|ALL"]["cohort_scope"], "model_fallback")

        # Rare car assignment
        self.assertEqual(mapping["rare_1"], "Lucid|Air|ALL")
        self.assertEqual(cohorts["Lucid|Air|ALL"]["confidence_tier"], "LOW")

        # Overarching aggregate
        self.assertIn("ALL", cohorts)
        self.assertEqual(cohorts["ALL"]["sample_size"], 7)

    def test_listing_enrichment_and_leverage(self) -> None:
        """
        Verify negotiation leverage scoring, price velocity tracking, and deterministic market badges.

        Pre-conditions:
            - Listing with multiple price drops and high days on market.

        Post-conditions:
            - Leverage score is computed within [0.0, 100.0] bounds.
            - HIGH_LEVERAGE badge is generated when score >= 70.0.
            - FRESH_PRICE_CUT and STALE_INVENTORY_30D badges are triggered appropriately.
            - Suggested offer target and low are bounded positive integers <= current price.
        """
        cohort = {
            "cohort_key": "Hyundai|Ioniq 5|2022",
            "cohort_scope": "exact_year",
            "sample_size": 10,
            "confidence_tier": "HIGH",
            "min_price": 28000,
            "p10": 29000.0,
            "p25": 31000.0,
            "p50": 34000.0,
            "p75": 37000.0,
            "max_price": 40000,
            "mean_price": 34000.0,
            "std_dev": 3500.0,
            "prices": [28000.0, 29000.0, 31000.0, 32000.0, 34000.0, 35000.0, 36000.0, 37000.0, 39000.0, 40000.0],
        }

        snapshots = [
            {"time": "2026-01-01", "price": 36000},
            {"time": "2026-01-15", "price": 34000},
            {"time": "2026-02-01", "price": 30000},
        ]

        listing = {
            "id": "hi5_test",
            "make": "Hyundai",
            "model": "Ioniq 5",
            "year": 2022,
            "price": 30000,
            "mileage": 28000,
            "days_on_market": 45,
            "title_status": "CLEAN",
            "accident_count": 0,
            "cpo": False,
        }

        enriched = enrich_listing_analytics(listing, cohort, snapshots=snapshots, current_year=2026)

        self.assertEqual(enriched["initial_price"], 36000)
        self.assertEqual(enriched["price_drop_total"], 6000)
        self.assertEqual(enriched["price_drop_count"], 2)
        self.assertGreater(enriched["price_velocity_per_week"], 0.0)

        # Leverage score should be high: dom=45 (29.2 pts) + velocity (25.0 pts) + headroom (10.0 pts) + friction (15.0 pts)
        self.assertGreaterEqual(enriched["negotiation_leverage_score"], 70.0)
        self.assertEqual(enriched["leverage_tier"], "HIGH")
        self.assertIn("HIGH_LEVERAGE", enriched["market_badges"])
        self.assertIn("FRESH_PRICE_CUT", enriched["market_badges"])
        self.assertIn("STALE_INVENTORY_30D", enriched["market_badges"])
        self.assertIn("BELOW_P25_COHORT", enriched["market_badges"])

        # Newest-first snapshot order must also yield accurate positive price_drop_total
        reversed_snaps = list(reversed(snapshots))
        enriched_rev = enrich_listing_analytics(listing, cohort, snapshots=reversed_snaps, current_year=2026)
        self.assertEqual(enriched_rev["initial_price"], 36000)
        self.assertEqual(enriched_rev["price_drop_total"], 6000)
        self.assertEqual(enriched_rev["price_drop_count"], 2)
        self.assertIn("dom_component", enriched_rev["leverage_breakdown"])
        self.assertIn("range_miles", enriched_rev["epa"])

        # Suggested offers
        self.assertLessEqual(enriched["suggested_offer_target"], 30000)
        self.assertLessEqual(enriched["suggested_offer_low"], enriched["suggested_offer_target"])
        self.assertGreater(enriched["suggested_offer_low"], 1000)

    def test_depreciation_and_tax_credit_eligibility(self) -> None:
        """
        Verify 3-year depreciation projection and Used EV Tax Credit boundary criteria.

        Pre-conditions:
            - Listings at $24,500 (eligible) vs $25,500 (over limit), and clean vs salvage title.

        Post-conditions:
            - Used EV Tax credit evaluates potential_credit_usd of 4000 strictly when price <= 25000,
              year <= current_year - 2, and clean title.
            - Total 3-year ownership delta reflects energy cost, depreciation, and tax credit deduction.
        """
        cohort = {"p25": 24000.0, "mean_price": 25000.0, "prices": [22000.0, 24000.0, 26000.0]}

        # Eligible listing
        deal_ok = {
            "make": "Chevrolet",
            "model": "Bolt EUV",
            "year": 2023,
            "price": 23500,
            "mileage": 20000,
            "title_status": "CLEAN",
        }
        res_ok = enrich_listing_analytics(deal_ok, cohort, current_year=2026)
        self.assertTrue(res_ok["used_ev_tax_credit"]["eligible"])
        self.assertEqual(res_ok["used_ev_tax_credit"]["potential_credit_usd"], 4000)
        self.assertIn("USED_EV_TAX_CREDIT", res_ok["market_badges"])
        self.assertGreater(res_ok["projected_3yr_depreciation"], 0)
        self.assertEqual(
            res_ok["total_3yr_ownership_delta"],
            res_ok["projected_3yr_depreciation"] + res_ok["energy_cost_3yr"] - 4000,
        )

        # Ineligible due to price > $25,000
        deal_price = dict(deal_ok, price=25500)
        res_price = enrich_listing_analytics(deal_price, cohort, current_year=2026)
        self.assertFalse(res_price["used_ev_tax_credit"]["eligible"])
        self.assertEqual(res_price["used_ev_tax_credit"]["potential_credit_usd"], 0)
        self.assertNotIn("USED_EV_TAX_CREDIT", res_price["market_badges"])

        # Ineligible due to salvage title
        deal_salvage = dict(deal_ok, title_status="SALVAGE")
        res_salvage = enrich_listing_analytics(deal_salvage, cohort, current_year=2026)
        self.assertFalse(res_salvage["used_ev_tax_credit"]["eligible"])
        self.assertEqual(res_salvage["safety_posture"], "ELEVATED")

        # Ineligible due to model year too new (< 2 calendar years old)
        deal_new = dict(deal_ok, year=2025)
        res_new = enrich_listing_analytics(deal_new, cohort, current_year=2026)
        self.assertFalse(res_new["used_ev_tax_credit"]["eligible"])

    def test_dealer_and_platform_arbitrage(self) -> None:
        """
        Verify dealer, platform, and distance-band market arbitrage aggregations.

        Pre-conditions:
            - Collection of enriched active deals across different dealers, platforms, and locations.

        Post-conditions:
            - Dealers are grouped by seller name and sorted by listing count.
            - Platforms include CARSCOM and CARGURUS with listing counts.
            - Distance bands correctly partition listings into 0-20, 21-40, 41-60, and >60 mile tiers.
        """
        deals = [
            {
                "id": "d1",
                "seller_name": "Stevens Creek BMW",
                "platform": "CARSCOM",
                "distance_miles": 12.0,
                "price": 38000,
                "deal_score": 88.0,
                "days_on_market": 20,
            },
            {
                "id": "d2",
                "seller_name": "Stevens Creek BMW",
                "platform": "CARGURUS",
                "distance_miles": 12.0,
                "price": 37000,
                "deal_score": 90.0,
                "days_on_market": 35,
            },
            {
                "id": "d3",
                "seller_name": "San Francisco Toyota",
                "platform": "CARSCOM",
                "distance_miles": 28.0,
                "price": 28000,
                "deal_score": 82.0,
                "days_on_market": 15,
            },
            {
                "id": "d4",
                "seller_name": "Sacramento EV Hub",
                "platform": "CARGURUS",
                "distance_miles": 75.0,
                "price": 24000,
                "deal_score": 79.0,
                "days_on_market": 40,
            },
            {
                "id": "d5_dis",
                "seller_name": "Hidden Dealer",
                "platform": "CARSCOM",
                "distance_miles": 10.0,
                "price": 30000,
                "is_dismissed": True,
            },
        ]

        enriched, _ = enrich_collection_with_analytics(deals)
        arbitrage = compute_dealer_and_platform_arbitrage(enriched)

        # Dealer checks
        dealers = arbitrage["dealers"]
        self.assertEqual(dealers[0]["seller_name"], "Stevens Creek BMW")
        self.assertEqual(dealers[0]["listing_count"], 2)
        self.assertEqual(dealers[0]["top_deal_score"], 90.0)

        # Platform checks
        platforms = {p["platform"]: p for p in arbitrage["platforms"]}
        self.assertIn("CARSCOM", platforms)
        self.assertIn("CARGURUS", platforms)
        self.assertEqual(platforms["CARSCOM"]["listing_count"], 2)
        self.assertEqual(platforms["CARGURUS"]["listing_count"], 2)

        # Distance bands checks (0-15 mi, 15-30 mi, 30-60 mi, 60+ mi)
        bands = {b["band"]: b for b in arbitrage["distance_bands"]}
        self.assertEqual(bands["0-15 mi"]["listing_count"], 2)
        self.assertEqual(bands["15-30 mi"]["listing_count"], 1)
        self.assertEqual(bands["30-60 mi"]["listing_count"], 0)
        self.assertEqual(bands["60+ mi"]["listing_count"], 1)
        self.assertEqual(dealers[0]["best_deal_id"], "d2")

    def test_market_overview_leaderboard_gap_coverage(self) -> None:
        """
        Verify compute_market_overview builds complete watchlist leaderboard including 0-count gap models.

        Pre-conditions:
            - Active deals covering only a subset of DEFAULT_TARGET_MODELS.

        Post-conditions:
            - Leaderboard list length matches total count of DEFAULT_TARGET_MODELS (14 models).
            - Unmatched models display sample_size 0 with best_deal_id None.
            - High-level KPIs correctly count total_active, excellent_count, and high_leverage_count.
        """
        deals = [
            {
                "id": "hi5_deal",
                "make": "Hyundai",
                "model": "Ioniq 5",
                "year": 2023,
                "price": 35000,
                "mileage": 15000,
                "deal_score": 88.5,
                "days_on_market": 25,
            },
            {
                "id": "eqs_deal",
                "make": "Mercedes-Benz",
                "model": "EQS",
                "year": 2022,
                "price": 54000,
                "mileage": 22000,
                "deal_score": 92.0,
                "days_on_market": 45,
            },
        ]

        enriched, cohorts = enrich_collection_with_analytics(deals)
        overview = compute_market_overview(enriched, cohorts, target_models=DEFAULT_TARGET_MODELS)

        kpis = overview["kpis"]
        self.assertEqual(kpis["total_active"], 2)
        self.assertEqual(kpis["excellent_count"], 2)

        leaderboard = overview["leaderboard"]
        self.assertEqual(len(leaderboard), len(DEFAULT_TARGET_MODELS))

        # Check matched models
        matched_models = {f"{m['make']}:{m['model']}": m for m in leaderboard if m["sample_size"] > 0}
        self.assertIn("Hyundai:Ioniq 5", matched_models)
        self.assertIn("Mercedes-Benz:EQS", matched_models)
        self.assertEqual(matched_models["Mercedes-Benz:EQS"]["best_deal_id"], "eqs_deal")

        # Check gap models
        gap_models = [m for m in leaderboard if m["sample_size"] == 0]
        self.assertEqual(len(gap_models), len(DEFAULT_TARGET_MODELS) - 2)
        self.assertIsNone(gap_models[0]["best_deal_id"])

    def test_build_compare_payload(self) -> None:
        """
        Verify side-by-side comparison payload highlights winner criteria for up to 3 listings.

        Pre-conditions:
            - 4 enriched deals with distinct characteristics (score, discount, leverage, range, distance).

        Post-conditions:
            - Limits returned deals to first 3 requested identifiers preserving requested order.
            - Deterministically selects winner identifiers for each highlight metric.
        """
        deals = [
            {
                "id": "deal_a",
                "make": "Tesla",
                "model": "Model 3",
                "year": 2023,
                "price": 28000,
                "price_delta": -4000,
                "msrp_discount_pct": 35.0,
                "deal_score": 91.0,
                "negotiation_leverage_score": 55.0,
                "total_3yr_ownership_delta": 11000,
                "distance_miles": 8.5,
                "days_on_market": 20,
                "title_status": "CLEAN",
                "safety_posture": "LOW",
                "used_ev_tax_credit": {"eligible": False},
            },
            {
                "id": "deal_b",
                "make": "Hyundai",
                "model": "Ioniq 6",
                "year": 2023,
                "price": 24000,
                "price_delta": -2500,
                "msrp_discount_pct": 45.0,
                "deal_score": 86.0,
                "negotiation_leverage_score": 82.0,
                "total_3yr_ownership_delta": 7500,
                "distance_miles": 22.0,
                "days_on_market": 60,
                "title_status": "CLEAN",
                "safety_posture": "LOW",
                "used_ev_tax_credit": {"eligible": True},
            },
            {
                "id": "deal_c",
                "make": "Mercedes-Benz",
                "model": "EQS",
                "year": 2022,
                "price": 52000,
                "price_delta": -8000,
                "msrp_discount_pct": 52.0,
                "deal_score": 94.0,
                "negotiation_leverage_score": 75.0,
                "total_3yr_ownership_delta": 16000,
                "distance_miles": 35.0,
                "days_on_market": 45,
                "title_status": "CLEAN",
                "safety_posture": "LOW",
                "used_ev_tax_credit": {"eligible": False},
            },
            {
                "id": "deal_d",
                "make": "Ford",
                "model": "Mustang Mach-E",
                "year": 2022,
                "price": 31000,
                "deal_score": 78.0,
            },
        ]

        res = build_compare_payload(deals, ["deal_c", "deal_a", "deal_b", "deal_d"])

        # Enforces max 3 limit
        self.assertEqual(res["count"], 3)
        self.assertEqual(len(res["items"]), 3)
        self.assertEqual(len(res["deals"]), 3)
        self.assertEqual([d["id"] for d in res["deals"]], ["deal_c", "deal_a", "deal_b"])

        highlights = res["highlights"]
        self.assertEqual(highlights["lowest_vs_fmv_id"], "deal_c")  # delta -8000
        self.assertEqual(highlights["highest_msrp_discount_id"], "deal_c")  # 52.0%
        self.assertEqual(highlights["highest_score_id"], "deal_c")  # 94.0
        self.assertEqual(highlights["highest_leverage_id"], "deal_b")  # 82.0
        self.assertEqual(highlights["lowest_3yr_tco_id"], "deal_b")  # 7500
        self.assertEqual(highlights["tax_credit_ids"], ["deal_b"])
        self.assertEqual(highlights["highest_range_id"], "deal_b")  # Ioniq 6: 361 mi vs EQS: 350 mi
        self.assertEqual(highlights["highest_dom_id"], "deal_b")  # 60 days
        self.assertEqual(highlights["closest_distance_id"], "deal_a")  # 8.5 mi
        self.assertCountEqual(highlights["lowest_risk_ids"], ["deal_c", "deal_a", "deal_b"])


if __name__ == "__main__":
    unittest.main()
