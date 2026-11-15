from datetime import datetime
from typing import Any, Dict, List, Set
import unittest

import src.workflows  # noqa: F401 - ensures workflows package is loaded before activities to avoid circular import
from src.activities.market_analytics import (
    compute_dealer_and_platform_arbitrage,
    compute_market_overview,
    enrich_collection_with_analytics,
)
from src.activities.scoring import BAY_AREA_ZIP_COORDS, BayAreaGeoLookup
from src.config.settings import DEFAULT_TARGET_MODELS
from src.dashboard.sample_data import get_offline_sample_deals


class TestOfflineSampleData(unittest.TestCase):
    """
    Unit test suite verifying the multi-snapshot Bay Area offline sample dataset.

    Pre-conditions:
        - src.dashboard.sample_data and all domain activities are importable.

    Post-conditions:
        - Validates all invariants specified in docs/specs/M02_SPEC.md.
    """

    def setUp(self) -> None:
        """
        Set up test fixture by retrieving a fresh sample deals dataset.

        Pre-conditions:
            - None.

        Post-conditions:
            - self.deals contains 24 vehicle listing dictionaries.
        """
        self.deals: List[Dict[str, Any]] = get_offline_sample_deals()

    def test_dataset_size_and_deepcopy_isolation(self) -> None:
        """
        Verify dataset contains at least 24 listings and returns isolated deep copies.

        Pre-conditions:
            - get_offline_sample_deals is callable.

        Post-conditions:
            - Confirms count is >= 24.
            - Confirms mutating one dataset copy does not leak into subsequent calls.
        """
        self.assertGreaterEqual(len(self.deals), 24)

        # Mutate first deal in current copy
        original_price = self.deals[0]["price"]
        self.deals[0]["price"] = 999999
        self.deals[0]["raw_data"]["tampered"] = True
        self.deals[0]["price_history"][0]["price"] = 999999

        # Request fresh copy and verify isolation
        fresh_deals = get_offline_sample_deals()
        self.assertEqual(fresh_deals[0]["price"], original_price)
        self.assertNotIn("tampered", fresh_deals[0]["raw_data"])
        self.assertNotEqual(fresh_deals[0]["price_history"][0]["price"], 999999)

    def test_target_models_watchlist_coverage(self) -> None:
        """
        Verify all 14 target models in DEFAULT_TARGET_MODELS appear in the sample dataset.

        Pre-conditions:
            - DEFAULT_TARGET_MODELS is populated with 14 models.

        Post-conditions:
            - Every target model is represented by at least one listing.
            - Key models (EQS, i4, Ioniq 5, Model Y) each have count >= 3.
        """
        model_counts: Dict[str, int] = {}
        for d in self.deals:
            key = f"{d['make'].strip().lower()}:{d['model'].strip().lower()}"
            model_counts[key] = model_counts.get(key, 0) + 1

        for tm in DEFAULT_TARGET_MODELS:
            key = f"{tm['make'].strip().lower()}:{tm['model'].strip().lower()}"
            self.assertIn(
                key,
                model_counts,
                f"Target model {tm['make']} {tm['model']} missing from sample dataset",
            )
            self.assertGreaterEqual(model_counts[key], 1)

        # Verify key models have n >= 3 for rich cohorts
        self.assertGreaterEqual(model_counts.get("mercedes-benz:eqs", 0), 3)
        self.assertGreaterEqual(model_counts.get("bmw:i4", 0), 3)
        self.assertGreaterEqual(model_counts.get("hyundai:ioniq 5", 0), 3)
        self.assertGreaterEqual(model_counts.get("tesla:model y", 0), 3)

    def test_platform_distribution(self) -> None:
        """
        Verify both carscom and cargurus platforms are present and evenly distributed.

        Pre-conditions:
            - self.deals is loaded.

        Post-conditions:
            - Exactly 12 carscom and 12 cargurus listings exist.
        """
        platforms: Dict[str, int] = {}
        for d in self.deals:
            plat = d["platform"].lower()
            platforms[plat] = platforms.get(plat, 0) + 1

        self.assertIn("carscom", platforms)
        self.assertIn("cargurus", platforms)
        self.assertEqual(platforms["carscom"], 12)
        self.assertEqual(platforms["cargurus"], 12)

    def test_geographic_and_dealer_integrity(self) -> None:
        """
        Verify Bay Area ZIP codes resolve properly and shared dealerships exist.

        Pre-conditions:
            - self.deals contains seller_zip in raw_data.

        Post-conditions:
            - All ZIP codes are valid entries in BAY_AREA_ZIP_COORDS.
            - distance_miles matches BayAreaGeoLookup resolution.
            - Listings populate 0-15, 15-30, and 30-60 mi bands.
            - Multiple dealers represent multiple listings.
        """
        distance_bands: Dict[str, int] = {"0-15": 0, "15-30": 0, "30-60": 0}
        dealer_counts: Dict[str, int] = {}

        for d in self.deals:
            seller_zip = d["raw_data"]["seller_zip"]
            self.assertIn(seller_zip, BAY_AREA_ZIP_COORDS)

            exp_dist, exp_city = BayAreaGeoLookup.resolve_zip(seller_zip)
            self.assertEqual(d["distance_miles"], exp_dist)
            self.assertEqual(d["location_city"], exp_city)

            dist = float(d["distance_miles"])
            if dist <= 15.0:
                distance_bands["0-15"] += 1
            elif dist <= 30.0:
                distance_bands["15-30"] += 1
            elif dist <= 60.0:
                distance_bands["30-60"] += 1

            s_name = d["seller_name"]
            dealer_counts[s_name] = dealer_counts.get(s_name, 0) + 1

        self.assertGreaterEqual(distance_bands["0-15"], 1)
        self.assertGreaterEqual(distance_bands["15-30"], 1)
        self.assertGreaterEqual(distance_bands["30-60"], 1)

        # Check multi-listing shared dealerships
        multi_dealers = [name for name, count in dealer_counts.items() if count >= 2]
        self.assertGreaterEqual(len(multi_dealers), 5)
        self.assertIn("Mercedes-Benz of Stevens Creek", dealer_counts)
        self.assertIn("Autobahn Motors", dealer_counts)
        self.assertIn("BMW of San Francisco", dealer_counts)
        self.assertIn("Putnam Hyundai", dealer_counts)
        self.assertIn("Oakland Kia", dealer_counts)
        self.assertIn("Fremont Tesla Hub", dealer_counts)

    def test_price_history_snapshots_and_dom_chronology(self) -> None:
        """
        Verify multi-snapshot price history, monotonically increasing timestamps, and DOM.

        Pre-conditions:
            - self.deals contains price_history and days_on_market.

        Post-conditions:
            - At least 14 listings have >= 2 snapshots.
            - All snapshot timestamps parse as valid ISO 8601 strings and increase monotonically.
            - Listing price, price_change, days_on_market, and snapshot_count match the latest snapshot.
            - Overall DOM spans between 4 and 78 days.
        """
        multi_snapshot_count = 0
        all_doms: List[int] = []

        for d in self.deals:
            history = d["price_history"]
            self.assertIsInstance(history, list)
            self.assertGreaterEqual(len(history), 1)

            if len(history) >= 2:
                multi_snapshot_count += 1

            # Check snapshot timestamp monotonicity
            parsed_times: List[datetime] = []
            dom_progression: List[int] = []
            for snap in history:
                self.assertIn("time", snap)
                self.assertIn("price", snap)
                self.assertIn("days_on_market", snap)
                self.assertIn("price_change", snap)

                # Parse ISO 8601 string
                t_str = snap["time"].replace("Z", "+00:00")
                dt = datetime.fromisoformat(t_str)
                parsed_times.append(dt)
                dom_progression.append(snap["days_on_market"])

            # Strict chronological ordering
            for i in range(len(parsed_times) - 1):
                self.assertLess(
                    parsed_times[i],
                    parsed_times[i + 1],
                    f"Timestamps not strictly increasing in deal {d['id']}",
                )
                self.assertLessEqual(
                    dom_progression[i],
                    dom_progression[i + 1],
                    f"DOM not non-decreasing in deal {d['id']}",
                )

            # Verification of synchronization with latest snapshot
            latest_snap = history[-1]
            self.assertEqual(d["price"], latest_snap["price"])
            self.assertEqual(d["price_change"], latest_snap["price_change"])
            self.assertEqual(d["days_on_market"], latest_snap["days_on_market"])
            self.assertEqual(d["snapshot_count"], len(history))

            all_doms.append(d["days_on_market"])

        self.assertGreaterEqual(multi_snapshot_count, 14)
        self.assertLessEqual(min(all_doms), 4)
        self.assertGreaterEqual(max(all_doms), 78)

    def test_used_ev_tax_credit_and_score_spectrum(self) -> None:
        """
        Verify used EV tax credit criteria and full recommendation tier spectrum.

        Pre-conditions:
            - self.deals contains scored listings.

        Post-conditions:
            - At least 2 clean-title listings are <= $25,000 and year <= 2024.
            - All four recommendation tiers (EXCELLENT_DEAL, GOOD_VALUE, FAIR_MARKET,
              OVERPRICED_OR_HIGH_RISK) are represented.
            - estimated_msrp is stored in score_breakdown.
        """
        tax_credit_candidates = [
            d
            for d in self.deals
            if d["price"] <= 25000 and d["year"] <= 2024 and d["title_status"].upper() == "CLEAN"
        ]
        self.assertGreaterEqual(len(tax_credit_candidates), 2)

        tiers: Set[str] = set()
        for d in self.deals:
            rec = d["recommendation"]
            tiers.add(rec)
            self.assertIn("estimated_msrp", d["score_breakdown"])
            self.assertGreater(d["score_breakdown"]["estimated_msrp"], 0)
            self.assertIn("price_score", d["score_breakdown"])
            self.assertIn("history_score", d["score_breakdown"])
            self.assertIn("leverage_score", d["score_breakdown"])
            self.assertIn("proximity_score", d["score_breakdown"])

        self.assertIn("EXCELLENT_DEAL", tiers)
        self.assertIn("GOOD_VALUE", tiers)
        self.assertIn("FAIR_MARKET", tiers)
        self.assertIn("OVERPRICED_OR_HIGH_RISK", tiers)

    def test_market_analytics_integration(self) -> None:
        """
        Verify compatibility with market_analytics enrichment, arbitrage, and overview.

        Pre-conditions:
            - market_analytics module functions are importable.

        Post-conditions:
            - enrich_collection_with_analytics enriches all 24 deals cleanly.
            - USED_EV_TAX_CREDIT badge is present on qualifying listings.
            - compute_dealer_and_platform_arbitrage computes dealers, platforms, and bands.
            - compute_market_overview produces complete KPIs and leaderboard.
        """
        enriched, cohorts_data = enrich_collection_with_analytics(self.deals)
        self.assertEqual(len(enriched), 24)

        # Verify tax credit badges
        tax_credit_badges = [
            d for d in enriched if "USED_EV_TAX_CREDIT" in d.get("market_badges", [])
        ]
        self.assertGreaterEqual(len(tax_credit_badges), 2)

        # Arbitrage computation
        arbitrage = compute_dealer_and_platform_arbitrage(enriched)
        self.assertIn("dealers", arbitrage)
        self.assertIn("platforms", arbitrage)
        self.assertIn("distance_bands", arbitrage)
        self.assertGreaterEqual(len(arbitrage["dealers"]), 5)

        band_counts = {b["band"]: b["listing_count"] for b in arbitrage["distance_bands"]}
        self.assertGreater(band_counts.get("0-15 mi", 0), 0)
        self.assertGreater(band_counts.get("15-30 mi", 0), 0)
        self.assertGreater(band_counts.get("30-60 mi", 0), 0)

        # Overview computation
        overview = compute_market_overview(enriched, cohorts_data)
        self.assertIn("kpis", overview)
        self.assertEqual(overview["kpis"]["total_active"], 24)
        self.assertGreaterEqual(overview["kpis"]["tax_credit_eligible_count"], 2)
        self.assertGreaterEqual(overview["kpis"]["price_drops_count"], 14)
        self.assertIn("leaderboard", overview)
        self.assertEqual(len(overview["leaderboard"]), len(DEFAULT_TARGET_MODELS))

    def test_deterministic_id_and_vin_structure(self) -> None:
        """
        Verify UUID format IDs and 17-character unique synthetic VINs.

        Pre-conditions:
            - self.deals is loaded.

        Post-conditions:
            - Every listing has unique ID matching 00000000-0000-4000-8000-0000000000xx.
            - Every listing has unique 17-character VIN.
        """
        seen_ids: Set[str] = set()
        seen_vins: Set[str] = set()

        for idx, d in enumerate(self.deals, start=1):
            expected_id = f"00000000-0000-4000-8000-{idx:012d}"
            self.assertEqual(d["id"], expected_id)
            self.assertNotIn(d["id"], seen_ids)
            seen_ids.add(d["id"])

            vin = d["vin"]
            self.assertEqual(len(vin), 17)
            self.assertNotIn(vin, seen_vins)
            seen_vins.add(vin)


if __name__ == "__main__":
    unittest.main()
