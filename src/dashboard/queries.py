"""
Web Dashboard Repository and Market Analytics Query Layer.

Pre-conditions:
    - Standard Python 3.14/3.15 runtime environment.
    - Optional SQLAlchemy / PostgreSQL / TimescaleDB drivers.
    - Optional Temporal SDK driver.

Post-conditions:
    - Provides zero-dependency in-memory fallback for all dashboard analytics,
      timeseries snapshot queries, cohort distributions, and export formatters.
    - Strictly zero emojis across all code, docstrings, comments, and outputs.
"""

import asyncio
import csv
from datetime import datetime
import io
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    from sqlalchemy import text
    from sqlalchemy.orm.attributes import flag_modified
    from src.db.engine import get_db_session
    from src.db.models import Listing
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

try:
    import temporalio  # noqa: F401
    HAS_TEMPORAL = True
except ImportError:
    HAS_TEMPORAL = False

import src.workflows  # noqa: F401 - ensures workflows package is loaded before activities to avoid circular import

from src.activities.gov_apis import GovAPIClient
from src.activities.market_analytics import (
    build_compare_payload,
    compute_cohort_stats,
    compute_dealer_and_platform_arbitrage,
    compute_market_overview,
    enrich_collection_with_analytics,
    enrich_listing_analytics,
)
from src.activities.scoring import BayAreaGeoLookup
from src.config.settings import settings
from src.dashboard.sample_data import get_offline_sample_deals

logger = logging.getLogger(__name__)

# In-memory cache for NHTSA/EPA model profiles so modal opens instantaneously on repeat views
_MODEL_PROFILE_CACHE: Dict[str, Dict[str, Any]] = {}


def _infer_make_model_year(title: str, raw_data: Dict[str, Any]) -> Tuple[str, str, int]:
    """
    Extract make, model, and year from raw_data or listing title.

    Pre-conditions:
        - title is a string representing the listing title.
        - raw_data is a dictionary representing the raw listing metadata.

    Post-conditions:
        - Returns a tuple of (make, model, year) as strings and integer.
    """
    year = int(raw_data.get("year") or 0)
    make = str(raw_data.get("make") or "").strip()
    model = str(raw_data.get("model") or "").strip()

    if not year:
        m_yr = re.search(r"\b(202\d)\b", title or "")
        year = int(m_yr.group(1)) if m_yr else 2023

    if not make or not model:
        title_clean = re.sub(r"^\b202\d\b\s*", "", (title or "").strip())
        for target in settings.search_target_models:
            tgt_make = str(getattr(target, "make", "") or (target.get("make") if isinstance(target, dict) else ""))
            tgt_model = str(getattr(target, "model", "") or (target.get("model") if isinstance(target, dict) else ""))
            if tgt_make and title_clean.lower().startswith(tgt_make.lower()):
                make = make or tgt_make
                rem = title_clean[len(tgt_make):].strip()
                model = model or (rem.split()[0] if rem else tgt_model)
                break
        if not make and title_clean:
            parts = title_clean.split()
            make = parts[0]
            model = parts[1] if len(parts) > 1 else ""

    return make, model, year


class DashboardRepository:
    """
    Data access layer for Web Dashboard and quantitative market analytics.

    Pre-conditions:
        - fallback_deals is an optional list of raw or normalized listing dictionaries.
          If None, repository operates in auto/production mode (TimescaleDB or offline-sample).
          If an explicit list (e.g. [] or sample fixtures), operates in fixture mode.

    Post-conditions:
        - Provides normalized deal retrieval, cohort analytics enrichment,
          timeseries snapshot queries, user bookmark/dismiss flag persistence,
          and quantitative CSV/Markdown export generation.
    """

    def __init__(self, fallback_deals: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Initialize the dashboard repository with optional fixture fallback.

        Pre-conditions:
            - fallback_deals is None or a list of listing dictionaries.

        Post-conditions:
            - Sets up data_source_mode, data_source_detail, and in-memory caches.
        """
        self._fallback_deals: Optional[List[Dict[str, Any]]] = fallback_deals
        self._offline_sample_cache: Optional[List[Dict[str, Any]]] = None
        self._last_cohorts_data: Optional[Dict[str, Any]] = None

        if self._fallback_deals is not None:
            self.data_source_mode: str = "fixture"
            self.data_source_detail: str = "In-memory test or custom fixture dataset."
        elif not HAS_SQLALCHEMY:
            self.data_source_mode = "offline-sample"
            self.data_source_detail = (
                "SQLAlchemy/PostgreSQL driver not installed; "
                "displaying representative Bay Area EV sample dataset."
            )
        else:
            self.data_source_mode = "timescaledb"
            self.data_source_detail = "Live PostgreSQL + TimescaleDB market telemetry."

    def get_provenance(self) -> Dict[str, Any]:
        """
        Retrieve current data source mode and pipeline telemetry provenance.

        Pre-conditions:
            - Repository instance is initialized.

        Post-conditions:
            - Returns a dictionary with mode, detail, temporal_available, and temporal_ui_url.
        """
        return {
            "mode": self.data_source_mode,
            "detail": self.data_source_detail,
            "temporal_available": bool(HAS_TEMPORAL),
            "temporal_ui_url": settings.temporal_ui_url,
        }

    async def fetch_all_Normalized_deals(self) -> List[Dict[str, Any]]:
        """
        Fetch all active listings joined with analytics and cohort metrics.

        Pre-conditions:
            - None.

        Post-conditions:
            - Returns a list of standardized deal dictionaries enriched with quantitative analytics.
            - Updates self.data_source_mode, self.data_source_detail, and self._last_cohorts_data.
            - Returns an empty list if no listings are available.
        """
        if self._fallback_deals is not None:
            self.data_source_mode = "fixture"
            self.data_source_detail = "In-memory test or custom fixture dataset."
            records = [self._normalize_record(d) for d in self._fallback_deals]
        elif not HAS_SQLALCHEMY:
            if self._offline_sample_cache is None:
                self._offline_sample_cache = get_offline_sample_deals()
            self.data_source_mode = "offline-sample"
            self.data_source_detail = (
                "SQLAlchemy/PostgreSQL driver not installed; "
                "displaying representative Bay Area EV sample dataset."
            )
            records = [self._normalize_record(d) for d in self._offline_sample_cache]
        else:
            sql = text("""
                SELECT
                    l.id::text AS id,
                    l.vin,
                    l.platform,
                    l.platform_id,
                    l.url,
                    l.title,
                    l.price,
                    l.mileage,
                    l.exterior_color,
                    l.interior_color,
                    l.trim_detail,
                    l.seller_name,
                    l.location_city,
                    l.distance_miles,
                    l.title_status,
                    l.accident_count,
                    l.owner_count,
                    l.photos,
                    l.raw_data,
                    l.first_seen,
                    l.last_seen,
                    ds.market_value,
                    ds.price_delta,
                    ds.deal_score,
                    ds.recommendation,
                    ds.score_breakdown,
                    ps.price_change,
                    ps.days_on_market,
                    ps.snapshot_count
                FROM listings l
                LEFT JOIN LATERAL (
                    SELECT market_value, price_delta, deal_score, recommendation, score_breakdown
                    FROM deal_scores
                    WHERE listing_id = l.id
                    ORDER BY scored_at DESC
                    LIMIT 1
                ) ds ON true
                LEFT JOIN LATERAL (
                    SELECT
                        price_change,
                        days_on_market,
                        (SELECT COUNT(*) FROM price_snapshots WHERE listing_id = l.id) AS snapshot_count
                    FROM price_snapshots
                    WHERE listing_id = l.id
                    ORDER BY time DESC
                    LIMIT 1
                ) ps ON true
                WHERE l.is_active = true
            """)
            records = []
            db_failed = False
            try:
                async with get_db_session() as session:
                    res = await session.execute(sql)
                    for row in res.mappings():
                        records.append(self._normalize_record(dict(row)))
            except Exception as e:
                logger.warning(f"Dashboard DB query fallback: {e}")
                db_failed = True

            if db_failed or not records:
                if self._offline_sample_cache is None:
                    self._offline_sample_cache = get_offline_sample_deals()
                self.data_source_mode = "offline-sample"
                if db_failed:
                    self.data_source_detail = (
                        "PostgreSQL connection unavailable; "
                        "displaying representative Bay Area EV sample dataset."
                    )
                else:
                    self.data_source_detail = (
                        "Database active but returned 0 rows; "
                        "displaying representative Bay Area EV sample dataset."
                    )
                records = [self._normalize_record(d) for d in self._offline_sample_cache]
            else:
                self.data_source_mode = "timescaledb"
                self.data_source_detail = "Live PostgreSQL + TimescaleDB market telemetry."

        if not records:
            return []

        enriched_deals, cohorts_data = enrich_collection_with_analytics(records)
        self._last_cohorts_data = cohorts_data
        return enriched_deals

    @staticmethod
    def _normalize_record(row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardize a DB, fallback, or offline-sample dictionary into a unified dashboard deal item.

        Pre-conditions:
            - row is a dictionary containing vehicle listing fields.

        Post-conditions:
            - Returns a standardized deal dictionary preserving all legacy keys,
              dynamic Bay Area geo-lookup metrics, and price history snapshots.
        """
        raw = row.get("raw_data") or {}
        if isinstance(raw, str):
            import json
            try:
                raw = json.loads(raw)
            except Exception:
                raw = {}
        elif not isinstance(raw, dict):
            raw = {}

        title = row.get("title") or "Vehicle Listing"
        make, model, year = _infer_make_model_year(title, raw)
        if row.get("make"):
            make = row["make"]
        if row.get("model"):
            model = row["model"]
        if row.get("year"):
            year = int(row["year"])

        price = int(row.get("price") or 0)
        market_value = int(row.get("market_value") or price)
        price_delta = int(row.get("price_delta") if row.get("price_delta") is not None else (price - market_value))
        deal_score = float(row.get("deal_score") or 0.0)
        recommendation = row.get("recommendation") or "FAIR_MARKET"
        breakdown = row.get("score_breakdown") or {}

        photos = row.get("photos") or []
        thumb = photos[0] if photos else raw.get("primaryThumbnail")

        pct_savings = round((price_delta / market_value) * 100, 1) if market_value > 0 else 0.0

        seller_zip = raw.get("seller_zip")
        if not seller_zip and isinstance(raw.get("seller"), dict):
            seller_zip = raw["seller"].get("zip")
        if not seller_zip and row.get("seller_zip"):
            seller_zip = row.get("seller_zip")

        dyn_dist, dyn_city = BayAreaGeoLookup.resolve_zip(seller_zip) if seller_zip else (None, None)
        if dyn_dist is not None:
            dist = dyn_dist
            if dist <= 20.0:
                prox_score = 100.0
            elif dist <= 40.0:
                prox_score = 85.0
            elif dist <= 60.0:
                prox_score = 70.0
            else:
                prox_score = max(20.0, 70.0 - (dist - 60.0))

            if breakdown and "price_score" in breakdown:
                price_s = float(breakdown.get("price_score", 70.0))
                hist_s = float(breakdown.get("history_score", 100.0))
                lev_s = float(breakdown.get("leverage_score", 65.0))
                deal_score = round(0.50 * price_s + 0.25 * hist_s + 0.15 * lev_s + 0.10 * prox_score, 1)
        else:
            dist = float(row["distance_miles"]) if row.get("distance_miles") is not None else None
            prox_score = float(breakdown.get("proximity_score", 85.0))

        city = row.get("location_city") or dyn_city or "Bay Area"
        price_history = list(row.get("price_history") or row.get("snapshots") or [])
        is_bookmarked = bool(row.get("is_bookmarked") or raw.get("user_bookmarked", False))
        is_dismissed = bool(row.get("is_dismissed") or raw.get("user_dismissed", False))

        return {
            "id": str(row.get("id") or row.get("platform_id") or ""),
            "vin": row.get("vin") or "N/A",
            "platform": (row.get("platform") or "carscom").upper(),
            "platform_id": row.get("platform_id") or "",
            "url": row.get("url") or "#",
            "title": title,
            "make": make,
            "model": model,
            "year": year,
            "trim_detail": row.get("trim_detail") or raw.get("trim") or "",
            "price": price,
            "mileage": int(row.get("mileage") or 0),
            "exterior_color": row.get("exterior_color") or raw.get("exteriorColor") or "Unknown",
            "interior_color": row.get("interior_color") or raw.get("interiorColor") or "Unknown",
            "seller_name": row.get("seller_name") or "Bay Area Dealer",
            "location_city": city,
            "distance_miles": dist,
            "title_status": (row.get("title_status") or "clean").upper(),
            "accident_count": int(row.get("accident_count") or 0),
            "owner_count": row.get("owner_count"),
            "thumbnail": thumb,
            "market_value": market_value,
            "price_delta": price_delta,
            "pct_savings": pct_savings,
            "deal_score": round(deal_score, 1),
            "recommendation": recommendation,
            "score_breakdown": {
                "price_score": float(breakdown.get("price_score", 75.0)),
                "history_score": float(breakdown.get("history_score", 100.0)),
                "leverage_score": float(breakdown.get("leverage_score", 65.0)),
                "proximity_score": prox_score,
            },
            "price_change": int(row.get("price_change") or 0),
            "days_on_market": int(row.get("days_on_market") or raw.get("days_on_market") or 1),
            "snapshot_count": int(row.get("snapshot_count") or len(price_history) or 1),
            "is_bookmarked": is_bookmarked,
            "is_dismissed": is_dismissed,
            "drivetrain": raw.get("drivetrain") or "",
            "cpo": bool(row.get("cpo") or raw.get("cpoIndicator", False)),
            "first_seen": row.get("first_seen"),
            "last_seen": row.get("last_seen"),
            "price_history": price_history,
            "raw_data": raw,
        }

    @staticmethod
    def filter_and_sort_deals(
        all_deals: List[Dict[str, Any]],
        tab: str = "all",
        make_filter: str = "",
        search_query: str = "",
        max_price: Optional[int] = None,
        max_mileage: Optional[int] = None,
        max_distance: Optional[float] = None,
        sort_by: str = "score_desc",
    ) -> List[Dict[str, Any]]:
        """
        Filter and sort normalized deals in-memory.

        Pre-conditions:
            - all_deals is a list of deal dictionaries.
            - tab is one of 'all', 'excellent', 'good', 'drops', 'price_drops',
              'saved', 'bookmarked', or 'dismissed'.
            - sort_by is one of 'score_desc', 'savings_asc', 'price_asc', 'mileage_asc',
              'distance_asc', 'leverage_desc', 'dom_desc', or 'msrp_off_desc'.

        Post-conditions:
            - Returns a filtered, ordered list of deal dictionaries.
        """
        filtered: List[Dict[str, Any]] = []
        q = (search_query or "").strip().lower()
        mf = (make_filter or "").strip().lower()

        for d in all_deals:
            is_dismissed = bool(d.get("is_dismissed") or d.get("raw_data", {}).get("user_dismissed", False))
            is_bookmarked = bool(d.get("is_bookmarked") or d.get("raw_data", {}).get("user_bookmarked", False))
            deal_score = float(d.get("deal_score") or 0.0)
            price_change = int(d.get("price_change") or 0)
            price_drop = int(d.get("price_drop_total") or d.get("analytics", {}).get("price_drop_total") or 0)

            if tab == "dismissed":
                if not is_dismissed:
                    continue
            else:
                if is_dismissed:
                    continue
                if tab in ("saved", "bookmarked") and not is_bookmarked:
                    continue
                elif tab == "excellent" and deal_score < 85.0:
                    continue
                elif tab == "good" and deal_score < 75.0:
                    continue
                elif tab in ("drops", "price_drops") and (price_change >= 0 and price_drop <= 0):
                    continue

            if mf:
                hay = f"{d.get('make', '')} {d.get('model', '')} {d.get('title', '')}".lower()
                if mf not in hay:
                    continue

            if q:
                hay = (
                    f"{d.get('title', '')} {d.get('vin', '')} {d.get('seller_name', '')} "
                    f"{d.get('location_city', '')} {d.get('exterior_color', '')} {d.get('trim_detail', '')}"
                ).lower()
                if q not in hay:
                    continue

            price = int(d.get("price") or 0)
            mileage = int(d.get("mileage") or 0)
            dist_val = d.get("distance_miles")

            if max_price and price > max_price:
                continue
            if max_mileage and mileage > max_mileage:
                continue
            if max_distance and dist_val is not None and float(dist_val) > max_distance:
                continue

            filtered.append(d)

        if sort_by in ("savings_asc", "savings_desc"):
            filtered.sort(
                key=lambda x: (int(x.get("price_delta") or 0), -float(x.get("deal_score") or 0.0)),
                reverse=(sort_by == "savings_desc"),
            )
        elif sort_by in ("price_asc", "price_desc"):
            filtered.sort(
                key=lambda x: (int(x.get("price") or 0), -float(x.get("deal_score") or 0.0)),
                reverse=(sort_by == "price_desc"),
            )
        elif sort_by in ("mileage_asc", "mileage_desc"):
            filtered.sort(
                key=lambda x: (int(x.get("mileage") or 0), -float(x.get("deal_score") or 0.0)),
                reverse=(sort_by == "mileage_desc"),
            )
        elif sort_by in ("distance_asc", "distance_desc"):
            filtered.sort(
                key=lambda x: (
                    float(x["distance_miles"]) if x.get("distance_miles") is not None else 999.0,
                    -float(x.get("deal_score") or 0.0),
                ),
                reverse=(sort_by == "distance_desc"),
            )
        elif sort_by in ("leverage_desc", "leverage_asc"):
            filtered.sort(
                key=lambda x: (
                    float(
                        x.get("negotiation_leverage_score")
                        or x.get("analytics", {}).get("negotiation_leverage_score")
                        or 0.0
                    ),
                    float(x.get("deal_score") or 0.0),
                ),
                reverse=(sort_by == "leverage_desc"),
            )
        elif sort_by in ("dom_desc", "dom_asc"):
            filtered.sort(
                key=lambda x: (
                    int(x.get("days_on_market") or x.get("raw_data", {}).get("days_on_market") or 0),
                    float(x.get("deal_score") or 0.0),
                ),
                reverse=(sort_by == "dom_desc"),
            )
        elif sort_by in ("msrp_off_desc", "msrp_off_asc"):
            filtered.sort(
                key=lambda x: (
                    float(x.get("msrp_discount_pct") or x.get("analytics", {}).get("msrp_discount_pct") or 0.0),
                    float(x.get("deal_score") or 0.0),
                ),
                reverse=(sort_by == "msrp_off_desc"),
            )
        else:
            filtered.sort(
                key=lambda x: (float(x.get("deal_score") or 0.0), -int(x.get("price_delta") or 0)),
                reverse=(sort_by != "score_asc"),
            )

        return filtered

    @staticmethod
    def compute_kpis(all_deals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute top-level KPI telemetry metrics across active (non-dismissed) inventory.

        Pre-conditions:
            - all_deals is a list of deal dictionaries.

        Post-conditions:
            - Returns a dictionary preserving all 7 legacy KPI metrics along with
              new quantitative market intelligence aggregations.
        """
        active = [
            d for d in all_deals
            if not bool(d.get("is_dismissed") or d.get("raw_data", {}).get("user_dismissed", False))
        ]
        excellent = [d for d in active if float(d.get("deal_score") or 0.0) >= 85.0]
        good = [d for d in active if float(d.get("deal_score") or 0.0) >= 75.0]
        saved = [
            d for d in active
            if bool(d.get("is_bookmarked") or d.get("raw_data", {}).get("user_bookmarked", False))
        ]
        dismissed = [
            d for d in all_deals
            if bool(d.get("is_dismissed") or d.get("raw_data", {}).get("user_dismissed", False))
        ]
        drops = [
            d for d in active
            if (d.get("price_change") or 0) < 0
            or (d.get("price_drop_total") or 0) > 0
            or (d.get("analytics", {}).get("price_drop_total") or 0) > 0
        ]

        discounts = [abs(int(d.get("price_delta") or 0)) for d in active if int(d.get("price_delta") or 0) < 0]
        max_savings = max(discounts) if discounts else 0
        avg_discount = int(sum(discounts) / len(discounts)) if discounts else 0

        n_active = len(active)
        below_p25_count = sum(
            1 for d in active
            if "BELOW_P25_COHORT" in (d.get("market_badges") or d.get("analytics", {}).get("market_badges") or [])
        )

        msrp_discounts = [
            float(d.get("msrp_discount_pct") or d.get("analytics", {}).get("msrp_discount_pct") or 0.0)
            for d in active
        ]
        avg_msrp_discount_pct = round(sum(msrp_discounts) / max(1.0, float(n_active)), 1) if n_active else 0.0

        doms = [
            float(d.get("days_on_market") or d.get("raw_data", {}).get("days_on_market") or 0)
            for d in active
        ]
        avg_dom = round(sum(doms) / max(1.0, float(n_active)), 1) if n_active else 0.0

        high_leverage_count = sum(
            1 for d in active
            if float(
                d.get("negotiation_leverage_score")
                or d.get("analytics", {}).get("negotiation_leverage_score")
                or 0.0
            ) >= 70.0
        )

        tax_credit_eligible_count = sum(
            1 for d in active
            if (d.get("used_ev_tax_credit") or d.get("analytics", {}).get("used_ev_tax_credit") or {}).get("eligible")
            is True
        )

        return {
            "total_active": n_active,
            "excellent_count": len(excellent),
            "good_count": len(good),
            "saved_count": len(saved),
            "dismissed_count": len(dismissed),
            "price_drops_count": len(drops),
            "max_savings": max_savings,
            "avg_discount": avg_discount,
            "below_p25_count": below_p25_count,
            "avg_msrp_discount_pct": avg_msrp_discount_pct,
            "avg_dom": avg_dom,
            "high_leverage_count": high_leverage_count,
            "tax_credit_eligible_count": tax_credit_eligible_count,
        }

    async def get_listing_history(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single listing and its TimescaleDB or in-memory price snapshots.

        Pre-conditions:
            - listing_id is a non-empty string identifier.

        Post-conditions:
            - Returns a dictionary with deal and snapshots list ordered newest-first,
              or None if listing does not exist.
        """
        all_deals = await self.fetch_all_Normalized_deals()
        target = next(
            (d for d in all_deals if str(d.get("id")) == listing_id or str(d.get("platform_id")) == listing_id),
            None,
        )
        if not target:
            return None

        snapshots: List[Dict[str, Any]] = []
        if HAS_SQLALCHEMY and self._fallback_deals is None and self.data_source_mode == "timescaledb":
            sql = text("""
                SELECT time, price, days_on_market, price_change
                FROM price_snapshots
                WHERE listing_id = CAST(:lid AS uuid)
                ORDER BY time DESC
                LIMIT 30
            """)
            try:
                async with get_db_session() as session:
                    res = await session.execute(sql, {"lid": target["id"]})
                    for row in res.mappings():
                        t_val = row["time"]
                        formatted_time = (
                            t_val.strftime("%Y-%m-%d %H:%M UTC") if isinstance(t_val, datetime) else str(t_val)
                        )
                        snapshots.append({
                            "time": formatted_time,
                            "price": int(row["price"]),
                            "days_on_market": int(row["days_on_market"] or 1),
                            "price_change": int(row["price_change"] or 0),
                        })
            except Exception as e:
                logger.warning(f"Failed to query price_snapshots for {listing_id}: {e}")

        if not snapshots:
            raw_history = target.get("price_history") or []
            if raw_history:
                for entry in raw_history:
                    if isinstance(entry, dict):
                        t_raw = entry.get("time") or entry.get("snapshot_date") or "Snapshot"
                        t_str = t_raw.strftime("%Y-%m-%d %H:%M UTC") if isinstance(t_raw, datetime) else str(t_raw)
                        snapshots.append({
                            "time": t_str,
                            "price": int(entry.get("price") or target["price"]),
                            "days_on_market": int(entry.get("days_on_market") or target["days_on_market"]),
                            "price_change": int(entry.get("price_change") or 0),
                        })
                snapshots.sort(
                    key=lambda s: (str(s.get("time") or ""), int(s.get("days_on_market") or 0)),
                    reverse=True,
                )

        if not snapshots:
            snapshots.append({
                "time": "Latest Snapshot",
                "price": target["price"],
                "days_on_market": target["days_on_market"],
                "price_change": target["price_change"],
            })

        return {
            "deal": target,
            "snapshots": snapshots,
        }

    async def toggle_user_flag(self, listing_id: str, flag_key: str) -> Optional[bool]:
        """
        Toggle user_bookmarked or user_dismissed on a listing across active data stores.

        Pre-conditions:
            - listing_id is a non-empty string identifier.
            - flag_key must be either 'user_bookmarked' or 'user_dismissed'.

        Post-conditions:
            - Returns the new boolean flag state, or None if listing_id or flag_key is invalid.
        """
        if flag_key not in ("user_bookmarked", "user_dismissed"):
            return None

        if self._fallback_deals is not None:
            for d in self._fallback_deals:
                if str(d.get("id")) == listing_id or str(d.get("platform_id")) == listing_id:
                    raw = d.setdefault("raw_data", {})
                    new_val = not bool(raw.get(flag_key, False))
                    raw[flag_key] = new_val
                    if flag_key == "user_bookmarked":
                        d["is_bookmarked"] = new_val
                    elif flag_key == "user_dismissed":
                        d["is_dismissed"] = new_val
                    return new_val
            return None

        if HAS_SQLALCHEMY and self.data_source_mode == "timescaledb":
            try:
                async with get_db_session() as session:
                    import uuid
                    try:
                        uid = uuid.UUID(listing_id)
                        listing = await session.get(Listing, uid)
                    except ValueError:
                        listing = None

                    if listing:
                        raw = dict(listing.raw_data or {})
                        new_val = not bool(raw.get(flag_key, False))
                        raw[flag_key] = new_val
                        listing.raw_data = raw
                        flag_modified(listing, "raw_data")
                        await session.flush()
                        return new_val
            except Exception as e:
                logger.warning(f"Failed to toggle {flag_key} for {listing_id} in DB: {e}")

        if self._offline_sample_cache is None:
            self._offline_sample_cache = get_offline_sample_deals()

        for d in self._offline_sample_cache:
            if str(d.get("id")) == listing_id or str(d.get("platform_id")) == listing_id:
                raw = d.setdefault("raw_data", {})
                new_val = not bool(raw.get(flag_key, False))
                raw[flag_key] = new_val
                if flag_key == "user_bookmarked":
                    d["is_bookmarked"] = new_val
                elif flag_key == "user_dismissed":
                    d["is_dismissed"] = new_val
                return new_val

        return None

    async def get_model_intelligence(self, make: str, model: str, year: int) -> Dict[str, Any]:
        """
        Fetch NHTSA Recalls, Complaints, and EPA Range for a vehicle model with caching and fallback.

        Pre-conditions:
            - make is a vehicle manufacturer name string.
            - model is a vehicle model name string.
            - year is a 4-digit calendar year integer.

        Post-conditions:
            - Returns a structured dictionary containing recalls, complaints, and EPA specs.
            - Caches responses in _MODEL_PROFILE_CACHE to avoid repeated external requests.
            - Never raises on network or API failures; returns safe fallback profile.
        """
        clean_model = model.strip()
        if "eqs" in clean_model.lower():
            clean_model = "EQS"
        elif "eqe" in clean_model.lower():
            clean_model = "EQE"
        elif "i4" in clean_model.lower():
            clean_model = "i4"

        cache_key = f"{make.lower()}:{clean_model.lower()}:{year}"
        if cache_key in _MODEL_PROFILE_CACHE:
            return _MODEL_PROFILE_CACHE[cache_key]

        try:
            client = GovAPIClient(timeout=2.5)
            results = await asyncio.gather(
                client.get_recalls(make, clean_model, year),
                client.get_complaints(make, clean_model, year),
                client.get_epa_fuel_economy(make, clean_model, year),
                return_exceptions=True,
            )
            recalls = results[0] if isinstance(results[0], list) else []
            complaints = results[1] if isinstance(results[1], list) else []
            epa_options = results[2] if isinstance(results[2], list) else []
            for err_candidate in results:
                if isinstance(err_candidate, Exception):
                    logger.warning(f"Partial Gov API lookup failed for {make} {clean_model} {year}: {err_candidate}")

            crash_count = sum(1 for c in complaints if getattr(c, "crash", False))
            fire_count = sum(1 for c in complaints if getattr(c, "fire", False))
            injury_count = sum(getattr(c, "number_of_injuries", 0) for c in complaints)

            profile = {
                "make": make,
                "model": clean_model,
                "year": year,
                "recalls_count": len(recalls),
                "recalls": [r.__dict__ if hasattr(r, "__dict__") else r for r in recalls[:10]],
                "complaints_count": len(complaints),
                "crash_count": crash_count,
                "fire_count": fire_count,
                "injury_count": injury_count,
                "complaints": [c.__dict__ if hasattr(c, "__dict__") else c for c in complaints[:10]],
                "epa_specs": [e.__dict__ if hasattr(e, "__dict__") else e for e in epa_options[:6]],
            }
        except Exception as e:
            logger.warning(f"Gov API lookup failed for {make} {clean_model} {year}: {e}")
            profile = {
                "make": make,
                "model": clean_model,
                "year": year,
                "recalls_count": 0,
                "recalls": [],
                "complaints_count": 0,
                "crash_count": 0,
                "fire_count": 0,
                "injury_count": 0,
                "complaints": [],
                "epa_specs": [],
            }

        _MODEL_PROFILE_CACHE[cache_key] = profile
        return profile

    async def get_market_overview(self) -> Dict[str, Any]:
        """
        Compile high-level market surveillance KPIs, model leaderboard, and inventory alerts.

        Pre-conditions:
            - None.

        Post-conditions:
            - Returns a dictionary with provenance, kpis, leaderboard, price_cut_movers,
              and stale_high_leverage.
        """
        deals = await self.fetch_all_Normalized_deals()
        if self._last_cohorts_data is None:
            cohorts_data = compute_cohort_stats(deals)
        else:
            cohorts_data = self._last_cohorts_data

        return compute_market_overview(
            enriched_deals=deals,
            cohorts_data=cohorts_data,
            target_models=settings.search_target_models,
            provenance=self.get_provenance(),
        )

    async def get_market_cohorts(
        self,
        cohort_key: Optional[str] = None,
        make: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve empirical cohort distributions, valuation percentiles, and scatter points.

        Pre-conditions:
            - cohort_key, make, and model are optional filter strings.

        Post-conditions:
            - Returns a dictionary with provenance, cohorts, selected_cohort, and scatter.
        """
        deals = await self.fetch_all_Normalized_deals()
        if self._last_cohorts_data is None:
            cohorts_data = compute_cohort_stats(deals)
        else:
            cohorts_data = self._last_cohorts_data

        cohorts = cohorts_data.get("cohorts", {})
        all_scatter = cohorts_data.get("all_scatter", {})

        selected: Dict[str, Any]
        if cohort_key and cohort_key in cohorts:
            selected = cohorts[cohort_key]
        elif make and model:
            candidate_key = f"{make}|{model}|ALL"
            if candidate_key in cohorts:
                selected = cohorts[candidate_key]
            else:
                matched = next(
                    (
                        c for c in cohorts.values()
                        if c.get("make", "").lower() == make.lower() and c.get("model", "").lower() == model.lower()
                    ),
                    None,
                )
                selected = matched or cohorts.get("ALL") or all_scatter
        elif cohort_key == "ALL" or not cohort_key:
            selected = cohorts.get("ALL") or all_scatter
        else:
            selected = cohorts.get(cohort_key) or cohorts.get("ALL") or all_scatter

        return {
            "provenance": self.get_provenance(),
            "cohorts": cohorts,
            "selected_cohort": selected,
            "scatter": selected.get("scatter_points", []),
        }

    async def get_dealer_arbitrage(self) -> Dict[str, Any]:
        """
        Aggregate market metrics across dealers, listing platforms, and geographic radius bands.

        Pre-conditions:
            - None.

        Post-conditions:
            - Returns a dictionary containing provenance, dealers, platforms, and distance_bands.
        """
        deals = await self.fetch_all_Normalized_deals()
        arbitrage = compute_dealer_and_platform_arbitrage(deals)
        return {
            "provenance": self.get_provenance(),
            "dealers": arbitrage.get("dealers", []),
            "platforms": arbitrage.get("platforms", []),
            "distance_bands": arbitrage.get("distance_bands", []),
        }

    async def get_listing_analysis(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """
        Build complete multi-factor quantitative valuation and risk dossier for a single listing.

        Pre-conditions:
            - listing_id is a non-empty string identifier.

        Post-conditions:
            - Returns a structured dictionary containing deal, cohort, snapshots,
              depreciation_3yr, leverage, tax_credit, safety_posture, epa,
              model_profile, and provenance; or None if listing not found.
            - Never raises or blocks if external safety/EPA APIs are unreachable.
        """
        history = await self.get_listing_history(listing_id)
        if history is None:
            return None

        deal = history["deal"]
        snapshots = history["snapshots"]

        if self._last_cohorts_data is None:
            all_deals = await self.fetch_all_Normalized_deals()
            cohorts_data = self._last_cohorts_data or compute_cohort_stats(all_deals)
        else:
            cohorts_data = self._last_cohorts_data

        mapping = cohorts_data.get("listing_cohort_map", {})
        lid = str(deal.get("id") or deal.get("platform_id") or deal.get("vin") or "")
        assigned_key = mapping.get(lid)
        cohorts = cohorts_data.get("cohorts", {})
        cohort = cohorts.get(assigned_key) if assigned_key else None
        if not cohort:
            make = str(deal.get("make") or "")
            model = str(deal.get("model") or "")
            cohort = cohorts.get(f"{make}|{model}|ALL") or cohorts.get("ALL") or {}

        make = str(deal.get("make") or "")
        model = str(deal.get("model") or "")
        year = int(deal.get("year") or 2023)

        try:
            profile = await asyncio.wait_for(
                self.get_model_intelligence(make, model, year),
                timeout=1.5,
            )
        except Exception as e:
            logger.warning(f"Model intelligence lookup fallback for {make} {model} {year}: {e}")
            profile = {
                "make": make,
                "model": model,
                "year": year,
                "recalls_count": int(deal.get("recalls_count") or 0),
                "recalls": [],
                "complaints_count": 0,
                "crash_count": 0,
                "fire_count": 0,
                "injury_count": 0,
                "complaints": [],
                "epa_specs": [],
            }

        analytics = enrich_listing_analytics(
            listing=deal,
            cohort=cohort,
            snapshots=snapshots,
            model_profile=profile,
        )

        depreciation_3yr = {
            "estimated_msrp": analytics.get("estimated_msrp", deal.get("estimated_msrp")),
            "projected_3yr_residual": analytics["projected_3yr_residual"],
            "projected_3yr_depreciation": analytics["projected_3yr_depreciation"],
            "energy_cost_3yr": analytics["energy_cost_3yr"],
            "total_3yr_ownership_delta": analytics["total_3yr_ownership_delta"],
        }
        leverage = {
            "negotiation_leverage_score": analytics["negotiation_leverage_score"],
            "leverage_tier": analytics["leverage_tier"],
            "leverage_breakdown": analytics["leverage_breakdown"],
            "suggested_offer_low": analytics["suggested_offer_low"],
            "suggested_offer_target": analytics["suggested_offer_target"],
            "initial_price": analytics["initial_price"],
            "price_drop_total": analytics["price_drop_total"],
            "price_drop_pct": analytics["price_drop_pct"],
            "price_drop_count": analytics.get("price_drop_count", 0),
            "price_velocity_per_week": analytics["price_velocity_per_week"],
        }

        return {
            "deal": deal,
            "cohort": cohort,
            "snapshots": snapshots,
            "depreciation_3yr": depreciation_3yr,
            "leverage": leverage,
            "tax_credit": analytics["used_ev_tax_credit"],
            "safety_posture": analytics["safety_posture"],
            "epa": analytics["epa"],
            "model_profile": profile,
            "provenance": self.get_provenance(),
        }

    async def get_compare_data(self, ids: List[str]) -> Dict[str, Any]:
        """
        Construct side-by-side comparison payload with highlight winners for up to 3 listings.

        Pre-conditions:
            - ids is a list of listing identifier strings.

        Post-conditions:
            - Returns a dictionary containing provenance, count, items, deals, and highlights.
        """
        deals = await self.fetch_all_Normalized_deals()
        payload = build_compare_payload(deals, ids)
        return {
            "provenance": self.get_provenance(),
            "count": payload.get("count", 0),
            "items": payload.get("items", []),
            "deals": payload.get("deals", []),
            "highlights": payload.get("highlights", {}),
        }

    @staticmethod
    def export_deals_csv(deals: List[Dict[str, Any]]) -> str:
        """
        Serialize deals into a CSV string preserving original 19 headers and 9 quantitative extensions.

        Pre-conditions:
            - deals is a list of deal dictionaries.

        Post-conditions:
            - Returns a valid CSV string with all 28 headers.
            - Strictly zero emojis in output.
        """
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
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
        ])
        for idx, d in enumerate(deals, 1):
            c_pctl = (
                d.get("cohort_percentile")
                if d.get("cohort_percentile") is not None
                else d.get("analytics", {}).get("cohort_percentile", "")
            )
            est_msrp = d.get("estimated_msrp") or d.get("analytics", {}).get("estimated_msrp") or ""
            msrp_off = (
                d.get("msrp_discount_pct")
                if d.get("msrp_discount_pct") is not None
                else d.get("analytics", {}).get("msrp_discount_pct", "")
            )
            msrp_off_str = f"{msrp_off}%" if msrp_off != "" else ""
            dom_val = d.get("days_on_market") or 0
            lev_score = (
                d.get("negotiation_leverage_score")
                if d.get("negotiation_leverage_score") is not None
                else d.get("analytics", {}).get("negotiation_leverage_score", "")
            )
            dep_3yr = (
                d.get("projected_3yr_depreciation")
                if d.get("projected_3yr_depreciation") is not None
                else d.get("analytics", {}).get("projected_3yr_depreciation", "")
            )
            tco_delta = (
                d.get("total_3yr_ownership_delta")
                if d.get("total_3yr_ownership_delta") is not None
                else d.get("analytics", {}).get("total_3yr_ownership_delta", "")
            )
            ev_credit = (
                (d.get("used_ev_tax_credit") or d.get("analytics", {}).get("used_ev_tax_credit") or {}).get(
                    "potential_credit_usd", 0
                )
            )
            safety = d.get("safety_posture") or d.get("analytics", {}).get("safety_posture") or ""

            writer.writerow([
                idx,
                d.get("deal_score", 0.0),
                d.get("recommendation", "FAIR_MARKET"),
                d.get("year", 2023),
                d.get("make", ""),
                d.get("model", ""),
                d.get("trim_detail", ""),
                d.get("price", 0),
                d.get("market_value", 0),
                d.get("price_delta", 0),
                f"{d.get('pct_savings', 0.0)}%",
                d.get("mileage", 0),
                d.get("distance_miles") if d.get("distance_miles") is not None else "",
                d.get("location_city", ""),
                d.get("seller_name", ""),
                d.get("title_status", "CLEAN"),
                d.get("vin", ""),
                d.get("platform", ""),
                d.get("url", ""),
                c_pctl,
                est_msrp,
                msrp_off_str,
                dom_val,
                lev_score,
                dep_3yr,
                tco_delta,
                ev_credit,
                safety,
            ])
        return output.getvalue()

    @staticmethod
    def export_deals_markdown(deals: List[Dict[str, Any]]) -> str:
        """
        Format deals into a structured Markdown surveillance report.

        Pre-conditions:
            - deals is a list of deal dictionaries.

        Post-conditions:
            - Returns a markdown string containing TOP VEHICLE DEALS FOUND header,
              market valuation deltas, cohort positioning, and quantitative highlights.
            - Strictly zero emojis in output.
        """
        if not deals:
            return (
                f"# TOP VEHICLE DEALS FOUND (Bay Area - {settings.search_radius_miles}mi Radius)\n\n"
                "No high-scoring deals found matching criteria today."
            )

        lines = [
            f"# TOP VEHICLE DEALS FOUND (Bay Area - {settings.search_radius_miles}mi Radius)",
            f"*Generated by Car Researcher Pipeline for Zip: {settings.search_zip_code}*",
            "",
        ]

        for i, d in enumerate(deals[:10], 1):
            price = int(d.get("price", 0))
            market_val = int(d.get("market_value", price))
            price_delta = int(d.get("price_delta", 0))
            deal_score = float(d.get("deal_score", 0.0))
            recommendation = str(d.get("recommendation", "FAIR_MARKET"))

            title = str(d.get("title") or f"{d.get('year')} {d.get('make')} {d.get('model')}")
            mileage = f"{int(d.get('mileage', 0)):,}"
            dist_val = d.get("distance_miles")
            city_val = d.get("location_city")
            if dist_val is not None:
                dist = f"{float(dist_val):.1f} mi ({city_val})" if city_val else f"{float(dist_val):.1f} mi"
            else:
                dist = str(city_val or "Bay Area")

            title_status = str(d.get("title_status", "clean")).upper()
            url = str(d.get("url", "#"))
            platform = str(d.get("platform", "")).upper()
            seller_name = d.get("seller_name")
            dealer_str = f" | **Dealer:** {seller_name}" if seller_name else ""

            savings_str = (
                f"-${abs(price_delta):,} below market" if price_delta < 0 else f"+${price_delta:,} above market"
            )

            lines.extend([
                f"### {i}. [{title}]({url}) — **${price:,}**",
                f"- **Deal Score:** `{deal_score}/100` ({recommendation})",
                f"- **Market Valuation:** Estimated Fair Value `${market_val:,}` (**{savings_str}**)",
                f"- **Odometer:** {mileage} miles | **Proximity:** {dist} | **Title:** {title_status}{dealer_str}",
                f"- **Platform:** {platform} | **Platform ID:** `{d.get('platform_id')}`",
            ])

            highlights = []
            c_pctl = (
                d.get("cohort_percentile")
                if d.get("cohort_percentile") is not None
                else d.get("analytics", {}).get("cohort_percentile")
            )
            if c_pctl is not None:
                highlights.append(f"**Cohort Percentile:** {c_pctl}%")

            lev_score = (
                d.get("negotiation_leverage_score")
                if d.get("negotiation_leverage_score") is not None
                else d.get("analytics", {}).get("negotiation_leverage_score")
            )
            lev_tier = d.get("leverage_tier") or d.get("analytics", {}).get("leverage_tier")
            if lev_score is not None:
                tier_str = f" ({lev_tier})" if lev_tier else ""
                highlights.append(f"**Leverage Score:** {lev_score}/100{tier_str}")

            tco = (
                d.get("total_3yr_ownership_delta")
                if d.get("total_3yr_ownership_delta") is not None
                else d.get("analytics", {}).get("total_3yr_ownership_delta")
            )
            if tco is not None:
                highlights.append(f"**3-Yr TCO Delta:** ${tco:,}")

            ev_tax = d.get("used_ev_tax_credit") or d.get("analytics", {}).get("used_ev_tax_credit") or {}
            if ev_tax.get("eligible"):
                cred = ev_tax.get("potential_credit_usd", 4000)
                highlights.append(f"**Clean Vehicle Credit:** Eligible (${cred:,})")

            if highlights:
                lines.append(f"- **Quantitative Analytics:** {' | '.join(highlights)}")

            lines.append("")

        return "\n".join(lines)
