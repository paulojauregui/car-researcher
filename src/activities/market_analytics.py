from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple

from src.activities.scoring import DealScorer
from src.config.settings import DEFAULT_TARGET_MODELS

# Baseline EPA ratings for 14 watchlist models
MODEL_EPA_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "mercedes-benz:eqs": {"range_miles": 350, "comb_mpge": 97.0, "annual_fuel_cost": 750},
    "mercedes-benz:eqe": {"range_miles": 305, "comb_mpge": 96.0, "annual_fuel_cost": 750},
    "cadillac:lyriq": {"range_miles": 314, "comb_mpge": 89.0, "annual_fuel_cost": 850},
    "genesis:gv60": {"range_miles": 248, "comb_mpge": 95.0, "annual_fuel_cost": 800},
    "bmw:i4": {"range_miles": 301, "comb_mpge": 109.0, "annual_fuel_cost": 700},
    "audi:q4 e-tron": {"range_miles": 265, "comb_mpge": 95.0, "annual_fuel_cost": 800},
    "polestar:2": {"range_miles": 270, "comb_mpge": 107.0, "annual_fuel_cost": 700},
    "tesla:model y": {"range_miles": 310, "comb_mpge": 122.0, "annual_fuel_cost": 600},
    "tesla:model 3": {"range_miles": 272, "comb_mpge": 132.0, "annual_fuel_cost": 550},
    "ford:mustang mach-e": {"range_miles": 250, "comb_mpge": 101.0, "annual_fuel_cost": 750},
    "hyundai:ioniq 5": {"range_miles": 303, "comb_mpge": 114.0, "annual_fuel_cost": 650},
    "hyundai:ioniq 6": {"range_miles": 361, "comb_mpge": 140.0, "annual_fuel_cost": 500},
    "kia:ev6": {"range_miles": 310, "comb_mpge": 117.0, "annual_fuel_cost": 650},
    "chevrolet:bolt euv": {"range_miles": 247, "comb_mpge": 115.0, "annual_fuel_cost": 650},
}

LUXURY_MAKE_PREFIXES: Tuple[str, ...] = (
    "mercedes",
    "bmw",
    "cadillac",
    "audi",
    "genesis",
    "porsche",
    "polestar",
)


def compute_percentile(sorted_values: List[float], percentile: float) -> float:
    """
    Compute the p-th percentile of a sorted list of numeric values via linear interpolation.

    Pre-conditions:
        - sorted_values is a list of numeric floats or ints sorted in ascending order.
        - percentile is a float value nominally between 0.0 and 100.0.

    Post-conditions:
        - Returns 0.0 if sorted_values is empty.
        - Returns the exact value if sorted_values contains a single element.
        - Returns the linearly interpolated percentile clamped within [sorted_values[0], sorted_values[-1]].
    """
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    if n == 1:
        return float(sorted_values[0])
    p = max(0.0, min(100.0, float(percentile)))
    k = (n - 1) * (p / 100.0)
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return float(sorted_values[f])
    d0 = float(sorted_values[f]) * (c - k)
    d1 = float(sorted_values[c]) * (k - f)
    return round(float(d0 + d1), 2)


def compute_ols_regression(points: List[Tuple[float, float]]) -> Dict[str, float]:
    """
    Compute ordinary least squares linear regression over (x, y) coordinates.

    Pre-conditions:
        - points is a list of (x, y) float tuples, e.g. (mileage_in_k, price).

    Post-conditions:
        - Returns a dict containing slope_per_1k_miles, intercept, and r2.
        - If len(points) < 2 or variance in x is zero, returns 0.0 slope and 0.0 r2,
          with intercept equal to the mean of y (or 0.0 if empty).
    """
    if not points:
        return {"slope_per_1k_miles": 0.0, "intercept": 0.0, "r2": 0.0}
    n = len(points)
    mean_y = sum(p[1] for p in points) / float(n)
    if n < 2:
        return {"slope_per_1k_miles": 0.0, "intercept": round(mean_y, 2), "r2": 0.0}

    mean_x = sum(p[0] for p in points) / float(n)
    s_xx = sum((p[0] - mean_x) ** 2 for p in points)
    s_xy = sum((p[0] - mean_x) * (p[1] - mean_y) for p in points)
    s_yy = sum((p[1] - mean_y) ** 2 for p in points)

    if abs(s_xx) < 1e-12:
        return {"slope_per_1k_miles": 0.0, "intercept": round(mean_y, 2), "r2": 0.0}

    slope = s_xy / s_xx
    intercept = mean_y - slope * mean_x
    if abs(s_yy) < 1e-12:
        r2 = 0.0
    else:
        r2 = max(0.0, min(1.0, (s_xy**2) / (s_xx * s_yy)))

    return {
        "slope_per_1k_miles": round(float(slope), 2),
        "intercept": round(float(intercept), 2),
        "r2": round(float(r2), 4),
    }


def get_model_epa_baseline(
    make: str,
    model: str,
    model_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Resolve EPA baseline specifications for a make and model.

    Pre-conditions:
        - make and model are vehicle brand and model strings.
        - model_profile is an optional dict containing cached or live NHTSA/EPA data.

    Post-conditions:
        - Returns a dict containing range_miles (int), comb_mpge (float), annual_fuel_cost (int),
          and source ("live_epa" or "watchlist_baseline").
    """
    if model_profile and isinstance(model_profile.get("epa_specs"), list) and len(model_profile["epa_specs"]) > 0:
        first = model_profile["epa_specs"][0]
        if isinstance(first, dict):
            return {
                "range_miles": int(first.get("range_miles") or 270),
                "comb_mpge": float(first.get("comb_mpge") or 102.0),
                "annual_fuel_cost": int(first.get("annual_fuel_cost") or 750),
                "source": "live_epa",
            }

    make_clean = (make or "").strip().lower()
    model_clean = (model or "").strip().lower()
    exact_key = f"{make_clean}:{model_clean}"

    if exact_key in MODEL_EPA_DEFAULTS:
        return {**MODEL_EPA_DEFAULTS[exact_key], "source": "watchlist_baseline"}

    for key, val in MODEL_EPA_DEFAULTS.items():
        k_make, k_model = key.split(":", 1)
        if (k_make in make_clean or make_clean in k_make) and (k_model in model_clean or model_clean in k_model):
            return {**val, "source": "watchlist_baseline"}

    return {
        "range_miles": 270,
        "comb_mpge": 102.0,
        "annual_fuel_cost": 750,
        "source": "watchlist_baseline",
    }


def _compute_price_percentile(sorted_prices: List[float], price: float) -> float:
    """
    Compute the continuous percentile rank of a price within a sorted list of prices.

    Pre-conditions:
        - sorted_prices is a sorted list of ascending price floats.
        - price is a float value.

    Post-conditions:
        - Returns a float between 0.0 and 100.0 representing the position of price.
    """
    if not sorted_prices:
        return 50.0
    n = len(sorted_prices)
    if n == 1:
        return 50.0
    if price <= sorted_prices[0]:
        return 0.0
    if price >= sorted_prices[-1]:
        return 100.0

    for i in range(n - 1):
        p_low = sorted_prices[i]
        p_high = sorted_prices[i + 1]
        if p_low <= price <= p_high:
            if p_high == p_low:
                return round((float(i) / float(n - 1)) * 100.0, 1)
            t = (price - p_low) / (p_high - p_low)
            pct = ((float(i) + t) / float(n - 1)) * 100.0
            return round(pct, 1)

    return 50.0


def _is_active_listing(listing: Dict[str, Any]) -> bool:
    """
    Check if a listing record is active (not dismissed and has positive price).

    Pre-conditions:
        - listing is a dictionary representing vehicle listing data.

    Post-conditions:
        - Returns True if listing is not dismissed and price > 0, else False.
    """
    dismissed = bool(listing.get("is_dismissed") or listing.get("raw_data", {}).get("user_dismissed", False))
    price = float(listing.get("price") or 0)
    return (not dismissed) and (price > 0)


def _build_cohort_aggregate(
    cohort_key: str,
    label: str,
    make: str,
    model: str,
    year_val: Any,
    cohort_scope: str,
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Construct complete statistical metrics for a single cohort bucket.

    Pre-conditions:
        - cohort_key, label, make, model, cohort_scope are identifying strings.
        - year_val is either an integer year or "ALL".
        - items is a list of active listing dictionaries.

    Post-conditions:
        - Returns a structured dictionary containing all required distribution stats,
          regression trendlines, and scatter plot points.
    """
    n = len(items)
    if n >= 8:
        confidence_tier = "HIGH"
    elif n >= 3:
        confidence_tier = "MEDIUM"
    else:
        confidence_tier = "LOW"

    if n == 0:
        return {
            "cohort_key": cohort_key,
            "label": label,
            "make": make,
            "model": model,
            "year": year_val,
            "cohort_scope": cohort_scope,
            "sample_size": 0,
            "confidence_tier": confidence_tier,
            "min_price": 0,
            "p10": 0.0,
            "p25": 0.0,
            "p50": 0.0,
            "p75": 0.0,
            "max_price": 0,
            "iqr": 0.0,
            "mean_price": 0.0,
            "std_dev": 0.0,
            "fair_low": 0.0,
            "fair_median": 0.0,
            "fair_high": 0.0,
            "avg_mileage": 0.0,
            "median_price_per_1k_miles": 0.0,
            "avg_msrp": 0.0,
            "avg_msrp_discount_pct": 0.0,
            "avg_dom": 0.0,
            "price_cut_count": 0,
            "price_cut_share_pct": 0.0,
            "below_p25_count": 0,
            "top_deal_score": 0.0,
            "ols_trendline": {"slope_per_1k_miles": 0.0, "intercept": 0.0, "r2": 0.0},
            "scatter_points": [],
            "prices": [],
        }

    prices = sorted([float(d.get("price") or 0) for d in items])
    min_price = int(prices[0])
    max_price = int(prices[-1])
    p10 = compute_percentile(prices, 10.0)
    p25 = compute_percentile(prices, 25.0)
    p50 = compute_percentile(prices, 50.0)
    p75 = compute_percentile(prices, 75.0)
    iqr = round(p75 - p25, 2)
    mean_price = round(sum(prices) / float(n), 2)
    variance = sum((p - mean_price) ** 2 for p in prices) / float(n)
    std_dev = round(math.sqrt(variance), 2)

    mileages = [float(d.get("mileage") or 0) for d in items]
    avg_mileage = round(sum(mileages) / float(n), 1)

    prices_per_1k = [float(d.get("price") or 0) / max(1.0, float(d.get("mileage") or 0) / 1000.0) for d in items]
    median_price_per_1k_miles = compute_percentile(sorted(prices_per_1k), 50.0)

    msrps = []
    for d in items:
        bd = d.get("score_breakdown") or {}
        val = bd.get("estimated_msrp") or d.get("estimated_msrp")
        if not val:
            val = DealScorer.get_estimated_original_msrp(
                d.get("make", ""),
                d.get("model", ""),
                trim_detail=d.get("trim_detail"),
                title=d.get("title"),
            )
        msrps.append(float(val))

    avg_msrp = round(sum(msrps) / float(n), 1)
    msrp_discounts = [((m - p) / max(1.0, m)) * 100.0 for m, p in zip(msrps, prices)]
    avg_msrp_discount_pct = round(sum(msrp_discounts) / float(n), 1)

    doms = [float(d.get("days_on_market") or d.get("raw_data", {}).get("days_on_market") or 0) for d in items]
    avg_dom = round(sum(doms) / float(n), 1)

    price_cut_count = sum(
        1
        for d in items
        if (d.get("price_change") or 0) < 0
        or (d.get("price_drop_total") or 0) > 0
        or (d.get("analytics", {}).get("price_drop_total") or 0) > 0
    )
    price_cut_share_pct = round((price_cut_count / float(n)) * 100.0, 1)
    below_p25_count = sum(1 for p in prices if p <= p25)

    scores = [float(d.get("deal_score") or 0.0) for d in items]
    top_deal_score = max(scores) if scores else 0.0

    ols_points = [(float(d.get("mileage") or 0) / 1000.0, float(d.get("price") or 0)) for d in items]
    ols_trendline = compute_ols_regression(ols_points)

    scatter_points = []
    for d in items:
        p_val = float(d.get("price") or 0)
        m_val = float(d.get("mileage") or 0)
        c_pct = _compute_price_percentile(prices, p_val)
        drop_tot = int(
            d.get("price_drop_total")
            or d.get("analytics", {}).get("price_drop_total")
            or (abs(d["price_change"]) if (d.get("price_change") or 0) < 0 else 0)
        )
        scatter_points.append(
            {
                "id": str(d.get("id") or d.get("platform_id") or d.get("vin") or ""),
                "title": d.get("title", ""),
                "trim_detail": d.get("trim_detail") or "",
                "make": d.get("make", ""),
                "model": d.get("model", ""),
                "year": int(d.get("year") or 0),
                "mileage": int(m_val),
                "price": int(p_val),
                "market_value": int(d.get("market_value") or 0),
                "deal_score": float(d.get("deal_score") or 0.0),
                "pct_savings": float(d.get("pct_savings") or 0.0),
                "price_delta": int(d.get("price_delta") or 0),
                "days_on_market": int(d.get("days_on_market") or d.get("raw_data", {}).get("days_on_market") or 0),
                "price_drop_total": drop_tot,
                "below_p25": bool(p_val <= p25),
                "cohort_percentile": c_pct,
                "seller_name": d.get("seller_name") or "",
                "location_city": d.get("location_city") or "",
                "platform": d.get("platform") or "",
                "price_per_1k_miles": round(p_val / max(1.0, m_val / 1000.0), 1),
            }
        )

    return {
        "cohort_key": cohort_key,
        "label": label,
        "make": make,
        "model": model,
        "year": year_val,
        "cohort_scope": cohort_scope,
        "sample_size": n,
        "confidence_tier": confidence_tier,
        "min_price": min_price,
        "p10": p10,
        "p25": p25,
        "p50": p50,
        "p75": p75,
        "max_price": max_price,
        "iqr": iqr,
        "mean_price": mean_price,
        "std_dev": std_dev,
        "fair_low": p25,
        "fair_median": p50,
        "fair_high": p75,
        "avg_mileage": avg_mileage,
        "median_price_per_1k_miles": median_price_per_1k_miles,
        "avg_msrp": avg_msrp,
        "avg_msrp_discount_pct": avg_msrp_discount_pct,
        "avg_dom": avg_dom,
        "price_cut_count": price_cut_count,
        "price_cut_share_pct": price_cut_share_pct,
        "below_p25_count": below_p25_count,
        "top_deal_score": top_deal_score,
        "ols_trendline": ols_trendline,
        "scatter_points": scatter_points,
        "prices": prices,
    }


def compute_cohort_stats(listings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Partition active listings into primary and model-fallback cohorts and compute valuation metrics.

    Pre-conditions:
        - listings is a list of dictionary representations of vehicle listings.

    Post-conditions:
        - Returns a dict with "cohorts", "listing_cohort_map", and "all_scatter".
        - Primary cohorts are keyed by "{make}|{model}|{year}".
        - Model fallback cohorts are keyed by "{make}|{model}|ALL".
        - An overarching "ALL" aggregate cohort is computed and returned in cohorts and all_scatter.
    """
    active_listings = [d for d in listings if _is_active_listing(d)]

    exact_groups: Dict[Tuple[str, str, int], List[Dict[str, Any]]] = {}
    model_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

    for d in active_listings:
        make = str(d.get("make") or "").strip()
        model = str(d.get("model") or "").strip()
        year = int(d.get("year") or 0)
        exact_groups.setdefault((make, model, year), []).append(d)
        model_groups.setdefault((make, model), []).append(d)

    cohorts: Dict[str, Dict[str, Any]] = {}
    listing_cohort_map: Dict[str, str] = {}

    for (make, model, year), items in exact_groups.items():
        key = f"{make}|{model}|{year}"
        label = f"{year} {make} {model}"
        cohorts[key] = _build_cohort_aggregate(
            cohort_key=key,
            label=label,
            make=make,
            model=model,
            year_val=year,
            cohort_scope="exact_year",
            items=items,
        )

    for (make, model), items in model_groups.items():
        key = f"{make}|{model}|ALL"
        label = f"{make} {model} (All Years)"
        cohorts[key] = _build_cohort_aggregate(
            cohort_key=key,
            label=label,
            make=make,
            model=model,
            year_val="ALL",
            cohort_scope="model_fallback",
            items=items,
        )

    all_aggregate = _build_cohort_aggregate(
        cohort_key="ALL",
        label="All Models (All Years)",
        make="ALL",
        model="ALL",
        year_val="ALL",
        cohort_scope="all_aggregate",
        items=active_listings,
    )
    cohorts["ALL"] = all_aggregate

    for d in active_listings:
        lid = str(d.get("id") or d.get("platform_id") or d.get("vin") or "")
        make = str(d.get("make") or "").strip()
        model = str(d.get("model") or "").strip()
        year = int(d.get("year") or 0)

        exact_key = f"{make}|{model}|{year}"
        model_key = f"{make}|{model}|ALL"

        if exact_key in cohorts and cohorts[exact_key]["sample_size"] >= 3:
            assigned = exact_key
        elif model_key in cohorts:
            assigned = model_key
        else:
            assigned = "ALL"

        if lid:
            listing_cohort_map[lid] = assigned

    return {
        "cohorts": cohorts,
        "listing_cohort_map": listing_cohort_map,
        "all_scatter": all_aggregate,
    }


def enrich_listing_analytics(
    listing: Dict[str, Any],
    cohort: Dict[str, Any],
    snapshots: Optional[List[Dict[str, Any]]] = None,
    model_profile: Optional[Dict[str, Any]] = None,
    current_year: int = 2026,
) -> Dict[str, Any]:
    """
    Enrich a single vehicle listing with quantitative cohort positioning, leverage scores, and 3-year TCO.

    Pre-conditions:
        - listing is a dictionary containing vehicle listing fields (price, mileage, make, model, year).
        - cohort is a dictionary produced by compute_cohort_stats representing the listing's cohort.
        - snapshots is an optional chronological list of historical price snapshot dicts.
        - model_profile is an optional dict containing NHTSA/EPA specs.
        - current_year is a 4-digit calendar year integer.

    Post-conditions:
        - Returns a dictionary containing cohort positioning, negotiation leverage, 3-year depreciation,
          used EV tax credit evaluation, safety posture, and deterministic market badges.
    """
    price = float(listing.get("price") or 0.0)
    mileage = int(listing.get("mileage") or 0)
    year = int(listing.get("year") or current_year)
    make = str(listing.get("make") or "").strip()
    model = str(listing.get("model") or "").strip()

    cohort_key = str(cohort.get("cohort_key") or f"{make}|{model}|{year}")
    cohort_scope = str(cohort.get("cohort_scope") or "model_fallback")
    cohort_sample_size = int(cohort.get("sample_size") or 0)
    cohort_confidence = str(cohort.get("confidence_tier") or "LOW")

    cohort_p10 = float(cohort.get("p10") if cohort.get("p10") is not None else price)
    cohort_p25 = float(cohort.get("p25") if cohort.get("p25") is not None else price)
    cohort_p50 = float(cohort.get("p50") if cohort.get("p50") is not None else price)
    cohort_p75 = float(cohort.get("p75") if cohort.get("p75") is not None else price)
    cohort_min = int(cohort.get("min_price") if cohort.get("min_price") is not None else price)
    cohort_max = int(cohort.get("max_price") if cohort.get("max_price") is not None else price)
    fair_band = [cohort_p25, cohort_p50, cohort_p75]

    sorted_prices = cohort.get("prices") or []
    cohort_percentile = _compute_price_percentile(sorted_prices, price)

    mean_price = float(cohort.get("mean_price") if cohort.get("mean_price") is not None else price)
    std_dev = float(cohort.get("std_dev") or 0.0)
    cohort_z_score = round((price - mean_price) / std_dev, 2) if std_dev > 0.0 else 0.0

    price_per_1k_miles = round(price / max(1.0, float(mileage) / 1000.0), 1)

    score_bd = listing.get("score_breakdown") or {}
    estimated_msrp_raw = score_bd.get("estimated_msrp") or listing.get("estimated_msrp")
    if not estimated_msrp_raw:
        estimated_msrp = DealScorer.get_estimated_original_msrp(
            make,
            model,
            trim_detail=listing.get("trim_detail"),
            title=listing.get("title"),
        )
    else:
        estimated_msrp = int(estimated_msrp_raw)

    msrp_discount_pct = round(((estimated_msrp - price) / max(1.0, float(estimated_msrp))) * 100.0, 1)

    history = snapshots or listing.get("price_history") or []
    if history:
        def _snapshot_sort_key(snap: Dict[str, Any]) -> Tuple[str, int]:
            return (str(snap.get("time") or ""), int(snap.get("days_on_market") or 0))

        ordered_history = sorted(history, key=_snapshot_sort_key)
        hist_prices = [int(s.get("price") or 0) for s in ordered_history if (s.get("price") or 0) > 0]
        if not hist_prices:
            hist_prices = [int(price)]
        initial_price = hist_prices[0]
        current_p = int(price)
        price_drop_total = max(0, initial_price - current_p)
        price_drop_count = sum(1 for i in range(len(hist_prices) - 1) if hist_prices[i + 1] < hist_prices[i])
        if price_drop_total > 0 and price_drop_count == 0:
            price_drop_count = 1
    else:
        price_chg = int(listing.get("price_change") or 0)
        if price_chg < 0:
            price_drop_total = abs(price_chg)
            initial_price = int(price + price_drop_total)
            price_drop_count = 1
        else:
            price_drop_total = int(listing.get("price_drop_total") or 0)
            initial_price = int(price + price_drop_total)
            price_drop_count = 1 if price_drop_total > 0 else 0

    price_drop_pct = round((price_drop_total / max(1.0, float(initial_price))) * 100.0, 1)

    dom = int(listing.get("days_on_market") or listing.get("raw_data", {}).get("days_on_market") or 1)
    dom = max(1, dom)
    weeks = max(0.5, float(dom) / 7.0)
    price_velocity_per_week = round(float(price_drop_total) / weeks, 2)

    dom_component = min(40.0, dom * 0.65)
    velocity_component = min(25.0, price_drop_count * 9.0 + price_drop_pct * 1.5)
    if price > cohort_p25:
        headroom_component = min(20.0, max(5.0, ((price - cohort_p25) / max(1.0, cohort_p25)) * 80.0))
    else:
        headroom_component = 10.0

    cpo = bool(listing.get("cpo") or listing.get("raw_data", {}).get("cpoIndicator", False))
    snapshot_count = len(history) if history else int(listing.get("snapshot_count") or 1)
    fric_dom = 10.0 if (dom >= 21 and not cpo) else (4.0 if dom >= 14 else 0.0)
    fric_snap = 5.0 if snapshot_count >= 2 else 0.0
    friction_component = fric_dom + fric_snap

    negotiation_leverage_score = round(
        min(100.0, dom_component + velocity_component + headroom_component + friction_component),
        1,
    )

    if negotiation_leverage_score >= 70.0:
        leverage_tier = "HIGH"
    elif negotiation_leverage_score >= 45.0:
        leverage_tier = "MODERATE"
    else:
        leverage_tier = "LOW"

    discount_target = max(0.02, min(0.12, (negotiation_leverage_score / 100.0) * 0.12))
    discount_low = max(0.04, min(0.18, (negotiation_leverage_score / 100.0) * 0.18))
    suggested_offer_target = int(round(price * (1.0 - discount_target)))
    suggested_offer_low = int(round(price * (1.0 - discount_low)))
    suggested_offer_low = max(1000, min(int(price), suggested_offer_low))
    suggested_offer_target = max(suggested_offer_low, min(int(price), suggested_offer_target))

    is_luxury = any(lux in make.lower() for lux in LUXURY_MAKE_PREFIXES)
    age_now = max(0.5, float(current_year - year))
    age_3yr = age_now + 3.0
    projected_3yr_residual = DealScorer.calculate_fair_market_value(
        base_model_msrp=estimated_msrp,
        age_years=age_3yr,
        mileage=mileage + 36000,
        is_luxury=is_luxury,
    )
    projected_3yr_depreciation = max(0, int(price) - projected_3yr_residual)

    epa = get_model_epa_baseline(make, model, model_profile)
    energy_cost_3yr = int(epa["annual_fuel_cost"] * 3)

    clean_title = str(listing.get("title_status") or "CLEAN").strip().upper() == "CLEAN"
    price_under_25k = int(price) <= 25000
    model_year_2plus = year <= (current_year - 2)
    ev_credit_eligible = price_under_25k and model_year_2plus and clean_title
    potential_credit_usd = 4000 if ev_credit_eligible else 0

    used_ev_tax_credit = {
        "eligible": ev_credit_eligible,
        "potential_credit_usd": potential_credit_usd,
        "reasons": {
            "price_under_25k": price_under_25k,
            "model_year_2plus_years_old": model_year_2plus,
            "clean_title": clean_title,
        },
        "note": (
            "Informational estimate only; IRS buyer AGI limits, dealer point-of-sale registration, "
            "and first-resale VIN transfer rules apply."
        ),
    }

    total_3yr_ownership_delta = projected_3yr_depreciation + energy_cost_3yr - potential_credit_usd

    accident_count = int(listing.get("accident_count") or 0)
    recalls_count = int(listing.get("recalls_count") or 0)
    if not clean_title or accident_count >= 2:
        safety_posture = "ELEVATED"
    elif accident_count == 1 or recalls_count >= 3:
        safety_posture = "MODERATE"
    else:
        safety_posture = "LOW"

    market_badges: List[str] = []
    if price <= cohort_p25 and cohort_p25 > 0:
        market_badges.append("BELOW_P25_COHORT")
    if price_drop_total > 0 or (listing.get("price_change") or 0) < 0:
        market_badges.append("FRESH_PRICE_CUT")
    if dom >= 30:
        market_badges.append("STALE_INVENTORY_30D")
    if negotiation_leverage_score >= 70.0:
        market_badges.append("HIGH_LEVERAGE")
    if ev_credit_eligible:
        market_badges.append("USED_EV_TAX_CREDIT")

    return {
        "cohort_key": cohort_key,
        "cohort_scope": cohort_scope,
        "cohort_sample_size": cohort_sample_size,
        "cohort_confidence": cohort_confidence,
        "cohort_p10": cohort_p10,
        "cohort_p25": cohort_p25,
        "cohort_p50": cohort_p50,
        "cohort_p75": cohort_p75,
        "cohort_min": cohort_min,
        "cohort_max": cohort_max,
        "fair_band": fair_band,
        "cohort_percentile": cohort_percentile,
        "cohort_z_score": cohort_z_score,
        "price_per_1k_miles": price_per_1k_miles,
        "estimated_msrp": estimated_msrp,
        "msrp_discount_pct": msrp_discount_pct,
        "initial_price": initial_price,
        "price_drop_total": price_drop_total,
        "price_drop_pct": price_drop_pct,
        "price_drop_count": price_drop_count,
        "price_velocity_per_week": price_velocity_per_week,
        "negotiation_leverage_score": negotiation_leverage_score,
        "leverage_tier": leverage_tier,
        "leverage_breakdown": {
            "dom_component": round(dom_component, 1),
            "velocity_component": round(velocity_component, 1),
            "headroom_component": round(headroom_component, 1),
            "friction_component": round(friction_component, 1),
        },
        "suggested_offer_low": suggested_offer_low,
        "suggested_offer_target": suggested_offer_target,
        "projected_3yr_residual": projected_3yr_residual,
        "projected_3yr_depreciation": projected_3yr_depreciation,
        "epa": epa,
        "energy_cost_3yr": energy_cost_3yr,
        "used_ev_tax_credit": used_ev_tax_credit,
        "total_3yr_ownership_delta": total_3yr_ownership_delta,
        "safety_posture": safety_posture,
        "market_badges": market_badges,
    }


def enrich_collection_with_analytics(
    deals: List[Dict[str, Any]],
    current_year: int = 2026,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Enrich an entire collection of deal records with cohort distribution metrics and quantitative flags.

    Pre-conditions:
        - deals is a list of vehicle listing dictionaries.
        - current_year is a 4-digit calendar year integer.

    Post-conditions:
        - Returns a tuple of (enriched_deals, cohorts_data).
        - Every deal dict in enriched_deals receives all analytics fields merged at the top level
          as well as nested under "analytics".
    """
    cohorts_data = compute_cohort_stats(deals)
    cohorts = cohorts_data["cohorts"]
    mapping = cohorts_data["listing_cohort_map"]

    enriched_deals: List[Dict[str, Any]] = []
    for d in deals:
        lid = str(d.get("id") or d.get("platform_id") or d.get("vin") or "")
        assigned_key = mapping.get(lid)
        if not assigned_key or assigned_key not in cohorts:
            make = str(d.get("make") or "").strip()
            model = str(d.get("model") or "").strip()
            fallback_key = f"{make}|{model}|ALL"
            if fallback_key in cohorts:
                assigned_key = fallback_key
            else:
                assigned_key = "ALL"

        cohort_dict = cohorts.get(assigned_key) or cohorts.get("ALL") or {}
        analytics = enrich_listing_analytics(
            listing=d,
            cohort=cohort_dict,
            snapshots=d.get("snapshots") or d.get("price_history"),
            current_year=current_year,
        )

        item = dict(d)
        item.update(analytics)
        item["analytics"] = analytics
        enriched_deals.append(item)

    return enriched_deals, cohorts_data


def compute_dealer_and_platform_arbitrage(enriched_deals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate market metrics across dealers, listing platforms, and geographic radius bands.

    Pre-conditions:
        - enriched_deals is a list of active or inactive enriched listing dictionaries.

    Post-conditions:
        - Returns a dict containing "dealers", "platforms", and "distance_bands" metrics
          computed strictly over active listings.
    """
    active = [d for d in enriched_deals if _is_active_listing(d)]

    dealer_groups: Dict[str, List[Dict[str, Any]]] = {}
    for d in active:
        s_name = str(d.get("seller_name") or "Bay Area Dealer").strip()
        dealer_groups.setdefault(s_name, []).append(d)

    dealers: List[Dict[str, Any]] = []
    for s_name, group in dealer_groups.items():
        n = len(group)
        avg_price = round(sum(d.get("price", 0) for d in group) / float(n), 1)
        avg_deal_score = round(sum(float(d.get("deal_score", 0.0)) for d in group) / float(n), 1)
        avg_dom = round(sum(float(d.get("days_on_market", 0)) for d in group) / float(n), 1)
        avg_price_delta = round(sum(float(d.get("price_delta", 0)) for d in group) / float(n), 1)
        pct_vs_fmv_vals = sorted([float(d.get("pct_savings", 0.0)) for d in group])
        median_pct_vs_fmv = round(compute_percentile(pct_vs_fmv_vals, 50.0), 1)
        price_cuts = sum(
            1
            for d in group
            if (d.get("price_drop_total") or 0) > 0
            or (d.get("price_change") or 0) < 0
            or (d.get("analytics", {}).get("price_drop_total") or 0) > 0
        )
        price_cut_pct = round((price_cuts / float(n)) * 100.0, 1)
        high_lev = sum(1 for d in group if float(d.get("negotiation_leverage_score", 0.0)) >= 70.0)
        best_deal = max(group, key=lambda x: float(x.get("deal_score", 0.0)))
        top_score = float(best_deal.get("deal_score", 0.0))
        best_deal_id = str(best_deal.get("id") or best_deal.get("platform_id") or best_deal.get("vin") or "")
        cities = [str(d.get("location_city") or "") for d in group if d.get("location_city")]
        dists = [float(d["distance_miles"]) for d in group if d.get("distance_miles") is not None]

        dealers.append(
            {
                "seller_name": s_name,
                "location_city": cities[0] if cities else "Bay Area",
                "distance_miles": round(min(dists), 1) if dists else None,
                "listing_count": n,
                "avg_price": avg_price,
                "avg_price_delta": avg_price_delta,
                "median_pct_vs_fmv": median_pct_vs_fmv,
                "avg_deal_score": avg_deal_score,
                "avg_dom": avg_dom,
                "price_cut_count": price_cuts,
                "price_cut_pct": price_cut_pct,
                "high_leverage_count": high_lev,
                "top_deal_score": top_score,
                "best_deal_id": best_deal_id,
            }
        )
    dealers.sort(key=lambda x: (x["listing_count"], -x["median_pct_vs_fmv"], x["avg_deal_score"]), reverse=True)

    plat_groups: Dict[str, List[Dict[str, Any]]] = {}
    for d in active:
        plat = str(d.get("platform") or "UNKNOWN").upper().strip()
        plat_groups.setdefault(plat, []).append(d)

    platforms: List[Dict[str, Any]] = []
    for plat, group in plat_groups.items():
        n = len(group)
        avg_price = round(sum(d.get("price", 0) for d in group) / float(n), 1)
        avg_deal_score = round(sum(float(d.get("deal_score", 0.0)) for d in group) / float(n), 1)
        avg_dom = round(sum(float(d.get("days_on_market", 0)) for d in group) / float(n), 1)
        pct_vs_fmv_vals = sorted([float(d.get("pct_savings", 0.0)) for d in group])
        median_pct_vs_fmv = round(compute_percentile(pct_vs_fmv_vals, 50.0), 1)
        price_cuts = sum(
            1
            for d in group
            if (d.get("price_drop_total") or 0) > 0
            or (d.get("price_change") or 0) < 0
            or (d.get("analytics", {}).get("price_drop_total") or 0) > 0
        )
        price_cut_pct = round((price_cuts / float(n)) * 100.0, 1)
        top_score = max([float(d.get("deal_score", 0.0)) for d in group], default=0.0)

        platforms.append(
            {
                "platform": plat,
                "listing_count": n,
                "avg_price": avg_price,
                "median_pct_vs_fmv": median_pct_vs_fmv,
                "avg_deal_score": avg_deal_score,
                "avg_dom": avg_dom,
                "price_cut_count": price_cuts,
                "price_cut_pct": price_cut_pct,
                "top_deal_score": top_score,
            }
        )
    platforms.sort(key=lambda x: x["listing_count"], reverse=True)

    band_defs = [
        ("0-15 mi", 0.0, 15.0),
        ("15-30 mi", 15.0001, 30.0),
        ("30-60 mi", 30.0001, 60.0),
        ("60+ mi", 60.0001, 9999.0),
    ]
    distance_bands: List[Dict[str, Any]] = []
    for label, low, high in band_defs:
        group = [
            d for d in active if d.get("distance_miles") is not None and low <= float(d["distance_miles"]) <= high
        ]
        n = len(group)
        if n > 0:
            avg_p = round(sum(d.get("price", 0) for d in group) / float(n), 1)
            sorted_p = sorted([float(d.get("price", 0)) for d in group])
            med_p = round(compute_percentile(sorted_p, 50.0), 1)
            pct_vals = sorted([float(d.get("pct_savings", 0.0)) for d in group])
            med_pct = round(compute_percentile(pct_vals, 50.0), 1)
            avg_score = round(sum(float(d.get("deal_score", 0.0)) for d in group) / float(n), 1)
            avg_dist = round(sum(float(d.get("distance_miles", 0.0)) for d in group) / float(n), 1)
            cuts = sum(
                1
                for d in group
                if (d.get("price_drop_total") or 0) > 0 or (d.get("price_change") or 0) < 0
            )
            cut_pct = round((cuts / float(n)) * 100.0, 1)
            top_score = max([float(d.get("deal_score", 0.0)) for d in group], default=0.0)
        else:
            avg_p = 0.0
            med_p = 0.0
            med_pct = 0.0
            avg_score = 0.0
            avg_dist = 0.0
            cut_pct = 0.0
            top_score = 0.0

        distance_bands.append(
            {
                "band": label,
                "min_mi": int(round(low)) if low > 0 else 0,
                "max_mi": int(high) if high < 9000 else None,
                "listing_count": n,
                "avg_price": avg_p,
                "median_price": med_p,
                "median_pct_vs_fmv": med_pct,
                "avg_deal_score": avg_score,
                "avg_distance": avg_dist,
                "price_cut_pct": cut_pct,
                "top_deal_score": top_score,
            }
        )

    return {
        "dealers": dealers,
        "platforms": platforms,
        "distance_bands": distance_bands,
    }


def compute_market_overview(
    enriched_deals: List[Dict[str, Any]],
    cohorts_data: Dict[str, Any],
    target_models: Optional[List[Dict[str, Any]]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compile high-level market surveillance KPIs, model leaderboard, and inventory alerts.

    Pre-conditions:
        - enriched_deals is a list of enriched vehicle listing dictionaries.
        - cohorts_data is a dictionary produced by compute_cohort_stats.
        - target_models is an optional list of model configuration dicts (defaults to DEFAULT_TARGET_MODELS).
        - provenance is an optional dict identifying execution source and timestamp.

    Post-conditions:
        - Returns a dict containing provenance, kpis, leaderboard, price_cut_movers, and stale_high_leverage.
        - Leaderboard includes all watchlist target models even when listing count is zero.
    """
    if provenance is None:
        prov = {"mode": "live", "generated_at": datetime.now(timezone.utc).isoformat()}
    else:
        prov = dict(provenance)

    active = [d for d in enriched_deals if _is_active_listing(d)]
    dismissed = [
        d for d in enriched_deals if bool(d.get("is_dismissed") or d.get("raw_data", {}).get("user_dismissed", False))
    ]

    n_active = len(active)
    excellent_count = sum(1 for d in active if float(d.get("deal_score") or 0.0) >= 85.0)
    good_count = sum(1 for d in active if float(d.get("deal_score") or 0.0) >= 75.0)
    saved_count = sum(
        1 for d in active if bool(d.get("is_bookmarked") or d.get("raw_data", {}).get("user_bookmarked", False))
    )
    dismissed_count = len(dismissed)
    price_drops_count = sum(
        1
        for d in active
        if (d.get("price_drop_total") or 0) > 0
        or (d.get("price_change") or 0) < 0
        or (d.get("analytics", {}).get("price_drop_total") or 0) > 0
    )
    dollar_discounts = [abs(int(d.get("price_delta") or 0)) for d in active if int(d.get("price_delta") or 0) < 0]
    max_savings = max(dollar_discounts) if dollar_discounts else 0
    avg_discount = int(sum(dollar_discounts) / len(dollar_discounts)) if dollar_discounts else 0
    max_pct_savings = min([float(d.get("pct_savings") or 0.0) for d in active], default=0.0)
    avg_pct_savings = round(sum(float(d.get("pct_savings") or 0.0) for d in active) / max(1.0, float(n_active)), 1)
    below_p25_count = sum(1 for d in active if "BELOW_P25_COHORT" in d.get("market_badges", []))
    avg_msrp_discount_pct = round(
        sum(float(d.get("msrp_discount_pct") or 0.0) for d in active) / max(1.0, float(n_active)), 1
    )
    avg_dom = round(sum(float(d.get("days_on_market") or 0) for d in active) / max(1.0, float(n_active)), 1)
    high_leverage_count = sum(1 for d in active if float(d.get("negotiation_leverage_score") or 0.0) >= 70.0)
    tax_credit_eligible_count = sum(1 for d in active if d.get("used_ev_tax_credit", {}).get("eligible") is True)

    kpis = {
        "total_active": n_active,
        "excellent_count": excellent_count,
        "good_count": good_count,
        "saved_count": saved_count,
        "dismissed_count": dismissed_count,
        "price_drops_count": price_drops_count,
        "max_savings": max_savings,
        "avg_discount": avg_discount,
        "max_pct_savings": max_pct_savings,
        "avg_pct_savings": avg_pct_savings,
        "below_p25_count": below_p25_count,
        "avg_msrp_discount_pct": avg_msrp_discount_pct,
        "avg_dom": avg_dom,
        "high_leverage_count": high_leverage_count,
        "tax_credit_eligible_count": tax_credit_eligible_count,
    }

    if target_models is None:
        target_list: List[Any] = DEFAULT_TARGET_MODELS
    else:
        target_list = list(target_models)

    leaderboard: List[Dict[str, Any]] = []
    for tgt in target_list:
        if isinstance(tgt, dict):
            t_make = str(tgt.get("make") or "")
            t_model = str(tgt.get("model") or "")
        else:
            t_make = str(getattr(tgt, "make", ""))
            t_model = str(getattr(tgt, "model", ""))

        matching = [
            d
            for d in active
            if t_make.lower() in str(d.get("make", "")).lower() and t_model.lower() in str(d.get("model", "")).lower()
        ]

        if matching:
            s_size = len(matching)
            min_p = min(int(d.get("price", 0)) for d in matching)
            sorted_p = sorted([float(d.get("price", 0)) for d in matching])
            p25_p = compute_percentile(sorted_p, 25.0)
            med_p = compute_percentile(sorted_p, 50.0)
            p75_p = compute_percentile(sorted_p, 75.0)
            per_1k = sorted(
                [float(d.get("price", 0)) / max(1.0, float(d.get("mileage", 0)) / 1000.0) for d in matching]
            )
            med_per_1k = round(compute_percentile(per_1k, 50.0), 1)
            avg_dom_m = round(sum(float(d.get("days_on_market", 0)) for d in matching) / float(s_size), 1)
            avg_msrp_off = round(sum(float(d.get("msrp_discount_pct", 0.0)) for d in matching) / float(s_size), 1)
            cuts_m = sum(
                1
                for d in matching
                if (d.get("price_drop_total") or 0) > 0 or (d.get("price_change") or 0) < 0
            )
            cut_share_m = round((cuts_m / float(s_size)) * 100.0, 1)
            below_p25_m = sum(1 for p in sorted_p if p <= p25_p)
            conf_m = "HIGH" if s_size >= 8 else ("MEDIUM" if s_size >= 3 else "LOW")
            top_score = max([float(d.get("deal_score", 0.0)) for d in matching], default=0.0)
            best_deal = max(matching, key=lambda x: float(x.get("deal_score", 0.0)))
            best_deal_id = str(best_deal.get("id") or best_deal.get("platform_id") or best_deal.get("vin") or "")
            cohort_key_m = f"{t_make}|{t_model}|ALL"
        else:
            s_size = 0
            min_p = 0
            p25_p = 0.0
            med_p = 0.0
            p75_p = 0.0
            med_per_1k = 0.0
            avg_dom_m = 0.0
            avg_msrp_off = 0.0
            cuts_m = 0
            cut_share_m = 0.0
            below_p25_m = 0
            conf_m = "LOW"
            top_score = 0.0
            best_deal_id = None
            cohort_key_m = f"{t_make}|{t_model}|ALL"

        leaderboard.append(
            {
                "cohort_key": cohort_key_m,
                "make": t_make,
                "model": t_model,
                "sample_size": s_size,
                "confidence_tier": conf_m,
                "min_price": min_p,
                "p25": p25_p,
                "median_price": med_p,
                "p75": p75_p,
                "median_price_per_1k_miles": med_per_1k,
                "avg_dom": avg_dom_m,
                "avg_msrp_discount_pct": avg_msrp_off,
                "price_cut_count": cuts_m,
                "price_cut_share_pct": cut_share_m,
                "below_p25_count": below_p25_m,
                "top_deal_score": top_score,
                "best_deal_id": best_deal_id,
            }
        )

    leaderboard.sort(key=lambda x: (x["sample_size"] > 0, x["top_deal_score"]), reverse=True)

    cut_deals = [
        d
        for d in active
        if (d.get("price_drop_total") or 0) > 0
        or (d.get("price_change") or 0) < 0
        or (d.get("analytics", {}).get("price_drop_total") or 0) > 0
    ]
    cut_deals.sort(
        key=lambda x: float(x.get("price_drop_total") or x.get("analytics", {}).get("price_drop_total") or 0),
        reverse=True,
    )
    price_cut_movers = cut_deals[:8]

    stale_deals = [
        d
        for d in active
        if float(d.get("negotiation_leverage_score", 0.0)) >= 60.0 or int(d.get("days_on_market", 0)) >= 30
    ]
    stale_deals.sort(
        key=lambda x: float(x.get("negotiation_leverage_score") or x.get("analytics", {}).get("negotiation_leverage_score") or 0.0),
        reverse=True,
    )
    stale_high_leverage = stale_deals[:8]

    return {
        "provenance": prov,
        "kpis": kpis,
        "leaderboard": leaderboard,
        "price_cut_movers": price_cut_movers,
        "stale_high_leverage": stale_high_leverage,
    }


def build_compare_payload(
    enriched_deals: List[Dict[str, Any]],
    ids: List[str],
) -> Dict[str, Any]:
    """
    Construct side-by-side comparison payload with deterministic highlight winners for up to 3 listings.

    Pre-conditions:
        - enriched_deals is a list of enriched vehicle listing dictionaries.
        - ids is a list of listing identifier strings.

    Post-conditions:
        - Returns a dict containing "deals" (ordered list of matched listings, max 3)
          and "highlights" (map of comparative winner flags and identifier lists).
    """
    deal_map: Dict[str, Dict[str, Any]] = {}
    for d in enriched_deals:
        lid = str(d.get("id") or d.get("platform_id") or d.get("vin") or "")
        if lid:
            deal_map[lid] = d

    selected_deals: List[Dict[str, Any]] = []
    seen_ids = set()
    for requested_id in ids[:3]:
        rid_str = str(requested_id)
        if rid_str in deal_map and rid_str not in seen_ids:
            selected_deals.append(deal_map[rid_str])
            seen_ids.add(rid_str)

    if not selected_deals:
        return {"count": 0, "items": [], "deals": [], "highlights": {}}

    def _get_id(d: Dict[str, Any]) -> str:
        return str(d.get("id") or d.get("platform_id") or d.get("vin") or "")

    lowest_vs_fmv_deal = min(selected_deals, key=lambda d: float(d.get("price_delta", 0)))
    highest_msrp_discount_deal = max(selected_deals, key=lambda d: float(d.get("msrp_discount_pct", 0.0)))
    highest_score_deal = max(selected_deals, key=lambda d: float(d.get("deal_score", 0.0)))
    highest_leverage_deal = max(selected_deals, key=lambda d: float(d.get("negotiation_leverage_score", 0.0)))
    lowest_3yr_tco_deal = min(selected_deals, key=lambda d: float(d.get("total_3yr_ownership_delta", 0.0)))

    tax_credit_ids = [
        _get_id(d)
        for d in selected_deals
        if d.get("used_ev_tax_credit", {}).get("eligible") is True
        or d.get("analytics", {}).get("used_ev_tax_credit", {}).get("eligible") is True
    ]

    highest_range_deal = max(
        selected_deals,
        key=lambda d: get_model_epa_baseline(str(d.get("make", "")), str(d.get("model", "")))["range_miles"],
    )

    highest_dom_deal = max(selected_deals, key=lambda d: int(d.get("days_on_market", 0)))

    closest_distance_deal = min(
        selected_deals,
        key=lambda d: float(d.get("distance_miles") if d.get("distance_miles") is not None else 9999.0),
    )

    lowest_risk_ids = [
        _get_id(d)
        for d in selected_deals
        if (d.get("safety_posture") == "LOW" or d.get("analytics", {}).get("safety_posture") == "LOW")
        and str(d.get("title_status") or "").upper() == "CLEAN"
    ]

    highlights = {
        "lowest_vs_fmv_id": _get_id(lowest_vs_fmv_deal),
        "highest_msrp_discount_id": _get_id(highest_msrp_discount_deal),
        "highest_score_id": _get_id(highest_score_deal),
        "highest_leverage_id": _get_id(highest_leverage_deal),
        "lowest_3yr_tco_id": _get_id(lowest_3yr_tco_deal),
        "tax_credit_ids": tax_credit_ids,
        "highest_range_id": _get_id(highest_range_deal),
        "highest_dom_id": _get_id(highest_dom_deal),
        "closest_distance_id": _get_id(closest_distance_deal),
        "lowest_risk_ids": lowest_risk_ids,
    }

    return {
        "count": len(selected_deals),
        "items": selected_deals,
        "deals": selected_deals,
        "highlights": highlights,
    }
