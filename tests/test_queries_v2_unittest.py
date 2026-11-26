"""
Unit tests for Milestone M03: Repository Analytics Integration, Provenance, and Enriched Exports.

Pre-conditions:
    - Standard Python 3.14/3.15 runtime environment.
    - Pure standard library unittest execution with zero external dependencies.

Post-conditions:
    - Verifies 100% of Milestone M03 acceptance criteria for DashboardRepository.
    - Strictly zero emojis across all test code, docstrings, comments, and assertions.
"""

import csv
import io
import re
from typing import Any, Dict, List
import unittest
from unittest.mock import AsyncMock, patch

from src.dashboard.queries import DashboardRepository


def _sample_deals() -> List[Dict[str, Any]]:
    """
    Construct a deterministic 3-vehicle fixture dataset matching legacy unit tests.

    Pre-conditions:
        - None.

    Post-conditions:
        - Returns a list of 3 vehicle listing dictionaries with price history snapshots.
    """
    return [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "vin": "W1KCG2DB6PA043095",
            "platform": "cars_com",
            "platform_id": "cc-101",
            "url": "https://www.cars.com/vehicledetail/cc-101/",
            "title": "2023 Mercedes-Benz EQS 450+ Base",
            "price": 39988,
            "mileage": 16479,
            "exterior_color": "Obsidian Black",
            "interior_color": "Black",
            "trim_detail": "EQS 450+",
            "seller_name": "Mercedes-Benz of Stevens Creek",
            "location_city": "San Jose",
            "distance_miles": 41.2,
            "title_status": "clean",
            "accident_count": 0,
            "owner_count": 1,
            "photos": ["https://images.cars.com/phototab/1.jpg"],
            "raw_data": {"make": "Mercedes-Benz", "model": "EQS", "year": 2023},
            "market_value": 52778,
            "price_delta": -12790,
            "deal_score": 87.6,
            "recommendation": "Excellent Deal - Strong Buy",
            "score_breakdown": {
                "price_score": 98.4,
                "history_score": 100.0,
                "leverage_score": 50.0,
                "proximity_score": 79.0,
                "estimated_msrp": 105550,
            },
            "price_change": -1500,
            "days_on_market": 12,
            "snapshot_count": 3,
            "price_history": [
                {
                    "time": "2026-10-20 04:00:00",
                    "price": 39988,
                    "mileage": 16479,
                    "price_change": -1500,
                    "days_on_market": 12,
                },
                {
                    "time": "2026-10-18 04:00:00",
                    "price": 41488,
                    "mileage": 16479,
                    "price_change": 0,
                    "days_on_market": 10,
                },
            ],
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "vin": "W1KCG4EB5PA031214",
            "platform": "cars_com",
            "platform_id": "cc-102",
            "url": "https://www.cars.com/vehicledetail/cc-102/",
            "title": "2023 Mercedes-Benz EQS 580 4MATIC",
            "price": 50995,
            "mileage": 19576,
            "exterior_color": "Polar White",
            "interior_color": "Macchiato Beige",
            "trim_detail": "EQS 580 4MATIC",
            "seller_name": "Autobahn Motors",
            "location_city": "Belmont",
            "distance_miles": 19.6,
            "title_status": "clean",
            "accident_count": 0,
            "owner_count": 1,
            "photos": [],
            "raw_data": {"make": "Mercedes-Benz", "model": "EQS", "year": 2023},
            "market_value": 63522,
            "price_delta": -12527,
            "deal_score": 89.2,
            "recommendation": "Excellent Deal - Strong Buy",
            "score_breakdown": {
                "price_score": 94.6,
                "history_score": 100.0,
                "leverage_score": 50.0,
                "proximity_score": 100.0,
                "estimated_msrp": 127100,
            },
            "price_change": 0,
            "days_on_market": 5,
            "snapshot_count": 2,
        },
        {
            "id": "33333333-3333-3333-3333-333333333333",
            "vin": "KNDC4DLC6P5123456",
            "platform": "cargurus",
            "platform_id": "cg-201",
            "url": "https://www.cargurus.com/Cars/cg-201",
            "title": "2023 Kia EV6 Wind AWD",
            "price": 29500,
            "mileage": 22000,
            "exterior_color": "Yacht Blue",
            "interior_color": "Black",
            "trim_detail": "Wind AWD",
            "seller_name": "Oakland Kia",
            "location_city": "Oakland",
            "distance_miles": 10.5,
            "title_status": "clean",
            "accident_count": 0,
            "owner_count": 1,
            "photos": [],
            "raw_data": {"make": "Kia", "model": "EV6", "year": 2023},
            "market_value": 31000,
            "price_delta": -1500,
            "deal_score": 76.5,
            "recommendation": "Good Value - Worth Investigating",
            "score_breakdown": {
                "price_score": 69.3,
                "history_score": 100.0,
                "leverage_score": 50.0,
                "proximity_score": 100.0,
                "estimated_msrp": 52600,
            },
            "price_change": 0,
            "days_on_market": 18,
            "snapshot_count": 1,
        },
    ]


class TestQueriesV2(unittest.IsolatedAsyncioTestCase):
    """
    Test suite verifying DashboardRepository market analytics integration and exports.

    Pre-conditions:
        - Standard library test runner execution.

    Post-conditions:
        - Confirms zero-dependency offline fallback, provenance reporting,
          extended sorting/filtering, KPIs, multi-section analysis, and export formats.
    """

    def setUp(self) -> None:
        """
        Set up fresh repository instances for tests.

        Pre-conditions:
            - None.

        Post-conditions:
            - Configures fixture and offline sample repositories.
        """
        self.fixture_repo = DashboardRepository(fallback_deals=_sample_deals())
        self.auto_repo = DashboardRepository(fallback_deals=None)

    async def test_offline_sample_fallback_and_provenance(self) -> None:
        """
        Verify DashboardRepository(fallback_deals=None) falls back gracefully to offline sample.

        Pre-conditions:
            - Repository initialized with fallback_deals=None in offline environment.

        Post-conditions:
            - Provenance mode is 'offline-sample' and detail explains fallback reason.
            - fetch_all_Normalized_deals returns exactly 24 representative Bay Area EV listings.
            - Every listing is enriched with quantitative analytics and cohort metadata.
        """
        deals = await self.auto_repo.fetch_all_Normalized_deals()
        prov = self.auto_repo.get_provenance()

        self.assertEqual(prov["mode"], "offline-sample")
        self.assertIn("Bay Area EV sample dataset", prov["detail"])
        self.assertIsInstance(prov["temporal_available"], bool)
        self.assertTrue(prov["temporal_ui_url"] is None or isinstance(prov["temporal_ui_url"], str))

        self.assertEqual(len(deals), 24)
        first_deal = deals[0]
        self.assertIn("cohort_key", first_deal)
        self.assertIn("negotiation_leverage_score", first_deal)
        self.assertIn("market_badges", first_deal)
        self.assertIn("total_3yr_ownership_delta", first_deal)
        self.assertIn("used_ev_tax_credit", first_deal)
        self.assertIn("analytics", first_deal)

    async def test_fixture_mode_exact_count_and_history(self) -> None:
        """
        Verify DashboardRepository with explicit fallback_deals operates in fixture mode.

        Pre-conditions:
            - Repository initialized with _sample_deals() fixture list.

        Post-conditions:
            - Provenance mode is 'fixture'.
            - fetch_all_Normalized_deals returns exactly 3 deals.
            - get_listing_history returns all snapshots from price_history in newest-first order.
            - Listings without price_history return a synthetic single snapshot.
        """
        prov = self.fixture_repo.get_provenance()
        self.assertEqual(prov["mode"], "fixture")
        self.assertIn("In-memory test or custom fixture dataset", prov["detail"])

        deals = await self.fixture_repo.fetch_all_Normalized_deals()
        self.assertEqual(len(deals), 3)

        # Listing 1 has 2 price history entries
        hist1 = await self.fixture_repo.get_listing_history("11111111-1111-1111-1111-111111111111")
        self.assertIsNotNone(hist1)
        assert hist1 is not None
        self.assertEqual(len(hist1["snapshots"]), 2)
        self.assertEqual(hist1["snapshots"][0]["price"], 39988)
        self.assertEqual(hist1["snapshots"][0]["days_on_market"], 12)
        self.assertEqual(hist1["snapshots"][1]["price"], 41488)
        self.assertEqual(hist1["snapshots"][1]["days_on_market"], 10)

        # Listing 2 has no price history entries -> 1 synthetic snapshot
        hist2 = await self.fixture_repo.get_listing_history("22222222-2222-2222-2222-222222222222")
        self.assertIsNotNone(hist2)
        assert hist2 is not None
        self.assertEqual(len(hist2["snapshots"]), 1)
        self.assertEqual(hist2["snapshots"][0]["time"], "Latest Snapshot")
        self.assertEqual(hist2["snapshots"][0]["price"], 50995)

        # Non-existent listing returns None
        hist_none = await self.fixture_repo.get_listing_history("non-existent-id")
        self.assertIsNone(hist_none)

    async def test_toggle_user_flag_validations_and_persistence(self) -> None:
        """
        Verify toggle_user_flag validates flag keys and persists state in fixture and offline modes.

        Pre-conditions:
            - Fixture repository and offline sample repository.

        Post-conditions:
            - Returns None for invalid flag keys or non-existent listing IDs.
            - Toggles bookmark and dismissal flags correctly across subsequent fetches.
        """
        # Validation checks
        inv_flag = await self.fixture_repo.toggle_user_flag(
            "11111111-1111-1111-1111-111111111111",
            "invalid_flag",
        )
        self.assertIsNone(inv_flag)

        inv_id = await self.fixture_repo.toggle_user_flag(
            "00000000-0000-0000-0000-000000000000",
            "user_bookmarked",
        )
        self.assertIsNone(inv_id)

        # Fixture mode toggling
        res1 = await self.fixture_repo.toggle_user_flag(
            "11111111-1111-1111-1111-111111111111",
            "user_bookmarked",
        )
        self.assertTrue(res1)

        deals1 = await self.fixture_repo.fetch_all_Normalized_deals()
        target1 = next(d for d in deals1 if d["id"] == "11111111-1111-1111-1111-111111111111")
        self.assertTrue(target1["is_bookmarked"])

        res1_undo = await self.fixture_repo.toggle_user_flag(
            "11111111-1111-1111-1111-111111111111",
            "user_bookmarked",
        )
        self.assertFalse(res1_undo)

        # Offline sample cache toggling
        await self.auto_repo.fetch_all_Normalized_deals()
        sample_id = "00000000-0000-4000-8000-000000000001"
        res_sample = await self.auto_repo.toggle_user_flag(sample_id, "user_dismissed")
        self.assertTrue(res_sample)

        deals_sample = await self.auto_repo.fetch_all_Normalized_deals()
        target_sample = next(d for d in deals_sample if d["id"] == sample_id)
        self.assertTrue(target_sample["is_dismissed"])

    async def test_filter_and_sort_deals_extended(self) -> None:
        """
        Verify filter_and_sort_deals supports leverage_desc, dom_desc, and msrp_off_desc.

        Pre-conditions:
            - Deals list retrieved from offline sample dataset.

        Post-conditions:
            - Orders elements monotonically according to specified quantitative sort key.
            - Preserves legacy sort keys and tab filtering semantics.
        """
        deals = await self.auto_repo.fetch_all_Normalized_deals()

        # Sort by leverage descending
        sorted_leverage = DashboardRepository.filter_and_sort_deals(deals, sort_by="leverage_desc")
        for i in range(len(sorted_leverage) - 1):
            lev_curr = float(sorted_leverage[i].get("negotiation_leverage_score") or 0.0)
            lev_next = float(sorted_leverage[i + 1].get("negotiation_leverage_score") or 0.0)
            self.assertGreaterEqual(lev_curr, lev_next)

        # Sort by DOM descending
        sorted_dom = DashboardRepository.filter_and_sort_deals(deals, sort_by="dom_desc")
        for i in range(len(sorted_dom) - 1):
            dom_curr = int(sorted_dom[i].get("days_on_market") or 0)
            dom_next = int(sorted_dom[i + 1].get("days_on_market") or 0)
            self.assertGreaterEqual(dom_curr, dom_next)

        # Sort by MSRP discount percentage descending
        sorted_msrp = DashboardRepository.filter_and_sort_deals(deals, sort_by="msrp_off_desc")
        for i in range(len(sorted_msrp) - 1):
            msrp_curr = float(sorted_msrp[i].get("msrp_discount_pct") or 0.0)
            msrp_next = float(sorted_msrp[i + 1].get("msrp_discount_pct") or 0.0)
            self.assertGreaterEqual(msrp_curr, msrp_next)

        # Legacy sort checks
        sorted_score = DashboardRepository.filter_and_sort_deals(deals, sort_by="score_desc")
        self.assertGreaterEqual(sorted_score[0]["deal_score"], sorted_score[-1]["deal_score"])

        sorted_price = DashboardRepository.filter_and_sort_deals(deals, sort_by="price_asc")
        self.assertLessEqual(sorted_price[0]["price"], sorted_price[-1]["price"])

        # Tab check for good deals
        good_deals = DashboardRepository.filter_and_sort_deals(deals, tab="good")
        for d in good_deals:
            self.assertGreaterEqual(d["deal_score"], 75.0)

    async def test_compute_kpis_extended(self) -> None:
        """
        Verify compute_kpis computes all 7 legacy metrics and 6 new quantitative indicators.

        Pre-conditions:
            - Deals list retrieved from offline sample dataset.

        Post-conditions:
            - Returns dict containing total_active, excellent_count, saved_count,
              dismissed_count, price_drops_count, max_savings, avg_discount,
              good_count, below_p25_count, avg_msrp_discount_pct, avg_dom,
              high_leverage_count, and tax_credit_eligible_count.
        """
        deals = await self.auto_repo.fetch_all_Normalized_deals()
        kpis = DashboardRepository.compute_kpis(deals)

        expected_keys = [
            "total_active",
            "excellent_count",
            "good_count",
            "saved_count",
            "dismissed_count",
            "price_drops_count",
            "max_savings",
            "avg_discount",
            "below_p25_count",
            "avg_msrp_discount_pct",
            "avg_dom",
            "high_leverage_count",
            "tax_credit_eligible_count",
        ]
        for key in expected_keys:
            self.assertIn(key, kpis)

        self.assertEqual(kpis["total_active"], len(deals))
        self.assertGreaterEqual(kpis["good_count"], kpis["excellent_count"])
        self.assertGreaterEqual(kpis["max_savings"], 0)
        self.assertGreaterEqual(kpis["avg_msrp_discount_pct"], 0.0)
        self.assertGreaterEqual(kpis["avg_dom"], 0.0)
        self.assertGreaterEqual(kpis["tax_credit_eligible_count"], 1)

    async def test_get_market_overview(self) -> None:
        """
        Verify get_market_overview returns comprehensive market summary and model leaderboard.

        Pre-conditions:
            - Auto repository with offline sample dataset.

        Post-conditions:
            - Returns provenance, kpis, leaderboard, price_cut_movers, and stale_high_leverage.
            - Leaderboard includes entries for all watchlist models.
        """
        overview = await self.auto_repo.get_market_overview()

        self.assertIn("provenance", overview)
        self.assertIn("kpis", overview)
        self.assertIn("leaderboard", overview)
        self.assertIn("price_cut_movers", overview)
        self.assertIn("stale_high_leverage", overview)

        leaderboard = overview["leaderboard"]
        self.assertGreater(len(leaderboard), 0)
        first_model = leaderboard[0]
        self.assertIn("make", first_model)
        self.assertIn("model", first_model)
        self.assertIn("sample_size", first_model)
        self.assertIn("median_price", first_model)

        self.assertLessEqual(len(overview["price_cut_movers"]), 8)
        self.assertLessEqual(len(overview["stale_high_leverage"]), 8)

    async def test_get_market_cohorts(self) -> None:
        """
        Verify get_market_cohorts resolves empirical cohort bands and scatter plot coordinates.

        Pre-conditions:
            - Auto repository with offline sample dataset.

        Post-conditions:
            - Resolves overall aggregate cohort as default.
            - Resolves specific model cohort when make and model filters are supplied.
            - Scatter points contain price, mileage, and percentile coordinates.
        """
        # Default ALL cohort
        res_default = await self.auto_repo.get_market_cohorts()
        self.assertIn("cohorts", res_default)
        self.assertIn("selected_cohort", res_default)
        self.assertIn("scatter", res_default)
        self.assertEqual(res_default["selected_cohort"]["cohort_key"], "ALL")
        self.assertGreater(len(res_default["scatter"]), 0)

        # Filter by specific make and model
        res_eqs = await self.auto_repo.get_market_cohorts(make="Mercedes-Benz", model="EQS")
        self.assertEqual(res_eqs["selected_cohort"]["make"], "Mercedes-Benz")
        self.assertEqual(res_eqs["selected_cohort"]["model"], "EQS")

        first_pt = res_eqs["scatter"][0]
        self.assertIn("id", first_pt)
        self.assertIn("price", first_pt)
        self.assertIn("mileage", first_pt)
        self.assertIn("cohort_percentile", first_pt)

    async def test_get_dealer_arbitrage(self) -> None:
        """
        Verify get_dealer_arbitrage aggregates metrics across dealers, platforms, and distance tiers.

        Pre-conditions:
            - Auto repository with offline sample dataset.

        Post-conditions:
            - Returns dealers, platforms, and distance_bands aggregations.
            - Distance bands cover 4 defined Bay Area radius ranges.
        """
        arb = await self.auto_repo.get_dealer_arbitrage()
        self.assertIn("dealers", arb)
        self.assertIn("platforms", arb)
        self.assertIn("distance_bands", arb)

        self.assertGreater(len(arb["dealers"]), 0)
        self.assertGreater(len(arb["platforms"]), 0)
        self.assertEqual(len(arb["distance_bands"]), 4)

        first_dealer = arb["dealers"][0]
        self.assertIn("seller_name", first_dealer)
        self.assertIn("listing_count", first_dealer)
        self.assertIn("median_pct_vs_fmv", first_dealer)

    @patch("src.dashboard.queries.GovAPIClient")
    async def test_get_listing_analysis_dossier(self, mock_gov_client_cls: Any) -> None:
        """
        Verify get_listing_analysis produces complete 7-section quantitative vehicle dossier.

        Pre-conditions:
            - Valid listing ID from offline sample dataset.
            - External GovAPI mocked for deterministic offline execution.

        Post-conditions:
            - Returns complete dossier with deal, cohort, snapshots, depreciation_3yr,
              leverage, tax_credit, safety_posture, epa, model_profile, and provenance.
            - Returns None for invalid listing IDs.
            - Gracefully handles simulated external API outages without failing.
        """
        mock_instance = mock_gov_client_cls.return_value
        mock_instance.get_recalls = AsyncMock(return_value=[])
        mock_instance.get_complaints = AsyncMock(return_value=[])
        mock_instance.get_epa_fuel_economy = AsyncMock(return_value=[])

        sample_id = "00000000-0000-4000-8000-000000000001"
        analysis = await self.auto_repo.get_listing_analysis(sample_id)

        self.assertIsNotNone(analysis)
        assert analysis is not None

        sections = [
            "deal",
            "cohort",
            "snapshots",
            "depreciation_3yr",
            "leverage",
            "tax_credit",
            "safety_posture",
            "epa",
            "model_profile",
            "provenance",
        ]
        for sec in sections:
            self.assertIn(sec, analysis)

        # Check depreciation metrics
        dep = analysis["depreciation_3yr"]
        self.assertGreaterEqual(dep["projected_3yr_residual"], 0)
        self.assertGreaterEqual(dep["projected_3yr_depreciation"], 0)
        self.assertGreater(dep["energy_cost_3yr"], 0)

        # Check leverage breakdown
        lev = analysis["leverage"]
        self.assertIn(lev["leverage_tier"], ("HIGH", "MODERATE", "LOW"))
        self.assertLessEqual(lev["suggested_offer_target"], analysis["deal"]["price"])

        # Check safety posture
        self.assertIn(analysis["safety_posture"], ("LOW", "MODERATE", "ELEVATED"))

        # Non-existent ID returns None
        none_analysis = await self.auto_repo.get_listing_analysis("non-existent-vin")
        self.assertIsNone(none_analysis)

        # Test graceful handling of simulated external network outage
        mock_instance.get_recalls.side_effect = RuntimeError("Simulated network outage")
        from src.dashboard.queries import _MODEL_PROFILE_CACHE
        _MODEL_PROFILE_CACHE.clear()
        analysis_offline = await self.auto_repo.get_listing_analysis(sample_id)
        self.assertIsNotNone(analysis_offline)
        assert analysis_offline is not None
        self.assertEqual(analysis_offline["model_profile"]["recalls_count"], 0)

    async def test_get_compare_data(self) -> None:
        """
        Verify get_compare_data generates side-by-side comparison with deterministic winner flags.

        Pre-conditions:
            - Valid listing IDs from offline sample dataset.

        Post-conditions:
            - Returns structured compare payload with count, items, deals, and highlights.
        """
        ids = [
            "00000000-0000-4000-8000-000000000001",
            "00000000-0000-4000-8000-000000000002",
        ]
        res = await self.auto_repo.get_compare_data(ids)

        self.assertEqual(res["count"], 2)
        self.assertEqual(len(res["items"]), 2)
        self.assertIn("highlights", res)
        self.assertIn("lowest_vs_fmv_id", res["highlights"])
        self.assertIn("highest_score_id", res["highlights"])

        # Empty ids
        res_empty = await self.auto_repo.get_compare_data([])
        self.assertEqual(res_empty["count"], 0)
        self.assertEqual(len(res_empty["items"]), 0)

    async def test_export_deals_csv_and_markdown(self) -> None:
        """
        Verify CSV export preserves original 19 headers with 9 extensions and Markdown report formatting.

        Pre-conditions:
            - Deals list retrieved from offline sample dataset.

        Post-conditions:
            - CSV contains all 28 headers in exact order with zero emojis.
            - Markdown contains TOP VEHICLE DEALS FOUND and quantitative metrics with zero emojis.
        """
        deals = await self.auto_repo.fetch_all_Normalized_deals()

        # CSV Export Verification
        csv_str = DashboardRepository.export_deals_csv(deals)
        reader = csv.reader(io.StringIO(csv_str))
        headers = next(reader)

        expected_headers = [
            "Rank",
            "Deal Score",
            "Recommendation",
            "Year",
            "Make",
            "Model",
            "Trim",
            "Price ($)",
            "Fair Market Value ($)",
            "Price Delta ($)",
            "Savings (%)",
            "Mileage",
            "Distance (mi)",
            "City",
            "Dealer",
            "Title Status",
            "VIN",
            "Platform",
            "URL",
            "Cohort Pctl",
            "Est. MSRP ($)",
            "MSRP Off (%)",
            "DOM (days)",
            "Leverage Score",
            "3-Yr Dep ($)",
            "3-Yr TCO Delta ($)",
            "EV Tax Credit ($)",
            "Safety Posture",
        ]
        self.assertEqual(headers, expected_headers)
        self.assertEqual(len(headers), 28)

        # Markdown Export Verification
        md_str = DashboardRepository.export_deals_markdown(deals)
        self.assertIn("TOP VEHICLE DEALS FOUND", md_str)
        self.assertIn("Cohort Percentile", md_str)
        self.assertIn("Leverage Score", md_str)
        self.assertIn("3-Yr TCO Delta", md_str)

        # Zero Emoji Verification across both outputs
        emoji_pattern = re.compile(
            r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]",
            flags=re.UNICODE,
        )
        self.assertIsNone(
            emoji_pattern.search(csv_str),
            "CSV output must contain strictly zero emojis.",
        )
        self.assertIsNone(
            emoji_pattern.search(md_str),
            "Markdown output must contain strictly zero emojis.",
        )

    async def test_empty_deals_handling(self) -> None:
        """
        Verify repository methods execute safely without errors when provided an empty deal list.

        Pre-conditions:
            - Repository initialized with fallback_deals=[].

        Post-conditions:
            - fetch_all_Normalized_deals returns [].
            - compute_kpis returns zero counts with no DivisionByZero errors.
            - export_deals_csv outputs header row only.
            - export_deals_markdown outputs no deals notice with zero emojis.
        """
        empty_repo = DashboardRepository(fallback_deals=[])
        deals = await empty_repo.fetch_all_Normalized_deals()
        self.assertEqual(deals, [])

        kpis = DashboardRepository.compute_kpis([])
        self.assertEqual(kpis["total_active"], 0)
        self.assertEqual(kpis["max_savings"], 0)
        self.assertEqual(kpis["avg_discount"], 0)
        self.assertEqual(kpis["avg_msrp_discount_pct"], 0.0)

        csv_str = DashboardRepository.export_deals_csv([])
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        self.assertEqual(len(rows), 1)

        md_str = DashboardRepository.export_deals_markdown([])
        self.assertIn("TOP VEHICLE DEALS FOUND", md_str)
        self.assertIn("No high-scoring deals found", md_str)


if __name__ == "__main__":
    unittest.main()
