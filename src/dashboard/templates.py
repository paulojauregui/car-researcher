"""
Server-side HTML rendering templates and components for the car-researcher dashboard.

Implements Milestone M06: Semantic HTML5 rendering, zero-CDN local asset loading,
tabular numeric alignment, Design by Contract invariants, and strict zero-emoji styling.

Pre-conditions:
    - Python standard library and src.config.settings are available.
    - index.html template shell exists at src/dashboard/templates/index.html.

Post-conditions:
    - All exported functions return valid HTML5 strings.
    - Strictly zero emojis, zero external CDN links, and zero hardcoded cluster port strings.
    - Enforces font-variant-numeric: tabular-nums on all numeric metrics.
"""

import html
import json
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config.settings import settings

_INDEX_HTML_PATH: Path = Path(__file__).resolve().parent / "templates" / "index.html"


def _esc(val: Any) -> str:
    """
    Escape unsafe HTML characters.

    Pre-conditions:
        - val is any scalar or None.

    Post-conditions:
        - Returns an HTML-escaped string representation. None returns empty string.
    """
    if val is None:
        return ""
    return html.escape(str(val))


def _score_badge_class(score: float) -> str:
    """
    Return semantic CSS class based on composite deal score.

    Pre-conditions:
        - score is a float in the range [0.0, 100.0].

    Post-conditions:
        - Returns a status CSS class corresponding to the score tier.
    """
    if score >= 85.0:
        return "score-pill--excellent"
    if score >= 75.0:
        return "score-pill--info"
    if score >= 60.0:
        return "score-pill--warn"
    return "score-pill--danger"


def render_kpis_partial(kpis: Dict[str, Any]) -> str:
    """
    Render the top 4 KPI telemetry cards for the dashboard header.

    Pre-conditions:
        - kpis is a dictionary containing summary metrics.

    Post-conditions:
        - Returns semantic HTML markup for #kpi-bar with tabular numerals.
        - Zero emojis.
    """
    total_active = kpis.get("total_active", 0)
    excellent_count = kpis.get("excellent_count", 0)
    max_savings = kpis.get("max_savings", 0)
    avg_discount = kpis.get("avg_discount", 0)
    saved_count = kpis.get("saved_count", 0)
    price_drops = kpis.get("price_drops_count", 0)

    return f"""
    <div id="kpi-bar" class="kpi-strip">
        <div class="kpi-card">
            <span class="kpi-label">Active Bay Area Inventory</span>
            <span class="kpi-value tabular-nums">{total_active}</span>
            <span class="kpi-sub">Within {settings.search_radius_miles} mi of {settings.search_zip_code}</span>
        </div>
        <div class="kpi-card kpi-card--excellent">
            <span class="kpi-label">Excellent Deals (Score &ge; 85)</span>
            <span class="kpi-value tabular-nums">{excellent_count}</span>
            <span class="kpi-sub">High-conviction buy targets</span>
        </div>
        <div class="kpi-card kpi-card--cut">
            <span class="kpi-label">Max Below-Market Savings</span>
            <span class="kpi-value tabular-nums">-${max_savings:,}</span>
            <span class="kpi-sub">Avg discount: -${avg_discount:,}</span>
        </div>
        <div class="kpi-card kpi-card--info">
            <span class="kpi-label">Saved &amp; Price Drops</span>
            <span class="kpi-value tabular-nums">{saved_count} saved</span>
            <span class="kpi-sub">{price_drops} price drops recorded</span>
        </div>
    </div>
    """.strip()


def render_degraded_banner(provenance: Optional[Dict[str, Any]] = None) -> str:
    """
    Render degraded mode notice when operating on offline sample data.

    Pre-conditions:
        - provenance is None or a dictionary with mode, detail, and temporal_available.

    Post-conditions:
        - Returns visible amber banner when mode is 'offline-sample'.
        - Returns hidden banner element when mode is nominal ('timescaledb' or 'fixture').
        - Zero emojis.
    """
    prov = provenance or {}
    mode = prov.get("mode", "") if isinstance(prov, dict) else str(prov)

    if mode == "offline-sample":
        detail = prov.get(
            "detail",
            "PostgreSQL/TimescaleDB unreachable; displaying 24 representative Bay Area EV sample listings. "
            "All analytical math, charts, and comparator workflows remain operational.",
        )
        return f"""
        <div id="degraded-banner" class="degraded-banner" role="status" aria-live="polite">
            <div class="degraded-banner__content">
                <svg class="degraded-banner__icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
                    <circle cx="8" cy="8" r="7"></circle>
                    <line x1="8" y1="4" x2="8" y2="9"></line>
                    <circle cx="8" cy="12" r="0.75" fill="currentColor"></circle>
                </svg>
                <div>
                    <span class="degraded-banner__tag">Degraded Mode / Offline Sample Data</span>
                    <p class="degraded-banner__text">{_esc(detail)}</p>
                </div>
            </div>
            <div class="degraded-banner__diagnostics">
                <button type="button" class="btn btn-secondary text-xs" onclick="window.location.reload()">Retry Connection</button>
            </div>
        </div>
        """.strip()

    return '<div id="degraded-banner" class="degraded-banner" role="status" aria-live="polite" hidden></div>'


def _render_grid_view(deals: List[Dict[str, Any]]) -> str:
    """
    Render deals as responsive 6-zone cards with tabular readouts.

    Pre-conditions:
        - deals is a list of normalized deal dictionaries.

    Post-conditions:
        - Returns an HTML grid of .deal-card elements. Zero emojis.
    """
    cards: List[str] = []
    for idx, d in enumerate(deals, 1):
        lid, title, url, vin = _esc(d.get("id", "")), _esc(d.get("title", "")), _esc(d.get("url", "#")), _esc(d.get("vin", ""))
        price, fmv, delta, pct = d.get("price", 0), d.get("market_value", 0), d.get("price_delta", 0), d.get("pct_savings", 0.0)
        score, rec, mileage, dom = float(d.get("deal_score", 0.0)), _esc(d.get("recommendation", "").replace("_", " ")), d.get("mileage", 0), d.get("days_on_market", 0)
        city, dist = _esc(d.get("location_city", "")), d.get("distance_miles")
        dist_str = f"{dist:.1f} mi | {city}" if dist is not None else city
        dealer, platform = _esc(d.get("seller_name", "")), _esc(d.get("platform", "Cars.com")).upper()
        score_cls = _score_badge_class(score)
        delta_pill = (
            f'<span class="deal-card__delta deal-card__delta--neg tabular-nums">-${abs(delta):,} ({pct:.1f}%) vs FMV</span>'
            if delta < 0 else f'<span class="deal-card__delta deal-card__delta--pos tabular-nums">+${delta:,} (+{pct:.1f}%) vs FMV</span>'
        )
        drop_badge = (
            f'<span class="market-badge market-badge--cut tabular-nums"><span class="market-badge__dot" aria-hidden="true"></span>Price Drop -${abs(d["price_change"]):,}</span>'
            if d.get("price_change", 0) < 0 else ""
        )
        cpo_badge = '<span class="provenance-pill provenance-pill--live">CPO</span>' if d.get("cpo") else ""
        media_html = f'<img src="{_esc(d["thumbnail"])}" alt="{title}" loading="lazy" />' if d.get("thumbnail") else (
            '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">'
            '<path d="M12,40 L16,26 L48,26 L52,40 Z"></path><circle cx="20" cy="42" r="6"></circle><circle cx="44" cy="42" r="6"></circle></svg>'
        )
        bd = d.get("score_breakdown", {})
        p_sc, h_sc = min(100, int(bd.get("price_score", 0))), min(100, int(bd.get("history_score", 0)))
        l_sc, px_sc = min(100, int(bd.get("leverage_score", 0))), min(100, int(bd.get("proximity_score", 0)))
        is_bm, is_dis = bool(d.get("is_bookmarked", False)), bool(d.get("is_dismissed", False))
        star_lbl, dis_lbl = ("Saved" if is_bm else "Save"), ("Restore" if is_dis else "Hide")

        cards.append(f"""
        <article class="deal-card" data-listing-id="{lid}">
            <div class="deal-card__media">
                {media_html}
                <div class="deal-card__overlay-tl">
                    <span class="scope-chip tabular-nums">#{idx}</span>
                    <span class="provenance-pill">{platform}</span>
                    {cpo_badge}{drop_badge}
                </div>
                <div class="deal-card__overlay-tr">
                    <span class="score-pill {score_cls}">
                        <span class="tabular-nums">{score:.1f}</span> &bull; <span>{rec}</span>
                    </span>
                </div>
            </div>
            <div class="deal-card__body">
                <h3 class="deal-card__title"><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></h3>
                <div class="deal-card__price-row">
                    <div class="deal-card__price-primary">
                        <span class="deal-card__price tabular-nums">${price:,}</span>
                        <span class="deal-card__fmv tabular-nums">Est. FMV ${fmv:,}</span>
                    </div>
                    {delta_pill}
                </div>
                <div class="deal-card__factors">
                    <div class="factor-item"><span class="factor-label">Price</span><span class="factor-value tabular-nums">{p_sc}</span><div class="factor-bar"><div class="factor-bar__fill factor-bar__fill--excellent" style="width:{p_sc}%;"></div></div></div>
                    <div class="factor-item"><span class="factor-label">Hist</span><span class="factor-value tabular-nums">{h_sc}</span><div class="factor-bar"><div class="factor-bar__fill factor-bar__fill--info" style="width:{h_sc}%;"></div></div></div>
                    <div class="factor-item"><span class="factor-label">DOM</span><span class="factor-value tabular-nums">{l_sc}</span><div class="factor-bar"><div class="factor-bar__fill factor-bar__fill--cut" style="width:{l_sc}%;"></div></div></div>
                    <div class="factor-item"><span class="factor-label">Prox</span><span class="factor-value tabular-nums">{px_sc}</span><div class="factor-bar"><div class="factor-bar__fill factor-bar__fill--telemetry" style="width:{px_sc}%;"></div></div></div>
                </div>
                <div class="deal-card__meta">
                    <div class="deal-card__meta-item"><span class="text-muted">Odometer:</span> <strong class="tabular-nums">{mileage:,} mi</strong></div>
                    <div class="deal-card__meta-item"><span class="text-muted">Location:</span> <span class="tabular-nums truncate" title="{dist_str}">{dist_str}</span></div>
                    <div class="deal-card__meta-item"><span class="text-muted">Dealer / DOM:</span> <span class="truncate tabular-nums" title="{dealer}">{dealer} ({dom}d)</span></div>
                    <div class="deal-card__meta-item"><button type="button" class="vin-chip tabular-nums" data-action="copy-vin" data-vin="{vin}" onclick="navigator.clipboard.writeText('{vin}')" title="Copy VIN">{vin}</button></div>
                </div>
            </div>
            <div class="deal-card__footer">
                <div class="flex items-center gap-1">
                    <button type="button" class="btn btn-secondary text-xs" data-action="pin" data-listing-id="{lid}" aria-pressed="false">Compare</button>
                    <button type="button" class="btn btn-ghost text-xs" hx-post="/api/listing/{lid}/bookmark" hx-target="#deals-container" hx-include="#filter-form" data-action="bookmark" data-listing-id="{lid}" aria-pressed="{str(is_bm).lower()}">{star_lbl}</button>
                    <button type="button" class="btn btn-ghost text-xs" hx-post="/api/listing/{lid}/dismiss" hx-target="#deals-container" hx-include="#filter-form" data-action="dismiss" data-listing-id="{lid}">{dis_lbl}</button>
                </div>
                <div class="flex items-center gap-1">
                    <button type="button" class="btn btn-secondary text-xs" hx-get="/partials/listing/{lid}/history" hx-target="#modal-body" data-action="analyze" data-listing-id="{lid}" onclick="openModal()">Analyze</button>
                    <a href="{url}" target="_blank" rel="noopener noreferrer" class="btn btn-primary text-xs" aria-label="Open listing on {platform}">View &nearr;</a>
                </div>
            </div>
        </article>
        """)

    return f'<div class="deals-grid">{"".join(cards)}</div>'


def _render_table_view(deals: List[Dict[str, Any]]) -> str:
    """
    Render deals as a high-density tabular precision table.

    Pre-conditions:
        - deals is a list of normalized deal dictionaries.

    Post-conditions:
        - Returns an HTML table inside .precision-table-wrap. Zero emojis.
    """
    rows: List[str] = []
    for idx, d in enumerate(deals, 1):
        lid, title, url, vin = _esc(d.get("id", "")), _esc(d.get("title", "")), _esc(d.get("url", "#")), _esc(d.get("vin", ""))
        price, fmv, delta, pct = d.get("price", 0), d.get("market_value", 0), d.get("price_delta", 0), d.get("pct_savings", 0.0)
        score, mileage, dom = float(d.get("deal_score", 0.0)), d.get("mileage", 0), d.get("days_on_market", 0)
        city, dist = _esc(d.get("location_city", "")), d.get("distance_miles")
        dist_str = f"{dist:.1f} mi ({city})" if dist is not None else city
        dealer, platform = _esc(d.get("seller_name", "")), _esc(d.get("platform", "Cars.com")).upper()
        score_cls = _score_badge_class(score)
        delta_str = f"-${abs(delta):,} ({pct:.1f}%)" if delta < 0 else f"+${delta:,} (+{pct:.1f}%)"
        delta_cls = "deal-card__delta--neg" if delta < 0 else "deal-card__delta--pos"
        is_bm, is_dis = bool(d.get("is_bookmarked", False)), bool(d.get("is_dismissed", False))
        star_lbl, dis_lbl = ("Saved" if is_bm else "Save"), ("Restore" if is_dis else "Hide")

        rows.append(f"""
        <tr data-listing-id="{lid}">
            <td class="tabular-nums font-mono">#{idx}</td>
            <td><span class="score-pill {score_cls} tabular-nums">{score:.1f}</span></td>
            <td>
                <a href="{url}" target="_blank" rel="noopener noreferrer" class="font-semibold text-primary">{title}</a>
                <div class="deal-card__badges mt-1">
                    <button type="button" class="vin-chip tabular-nums" data-action="copy-vin" data-vin="{vin}" onclick="navigator.clipboard.writeText('{vin}')" title="Copy VIN">{vin}</button>
                </div>
            </td>
            <td class="num-col font-bold text-primary tabular-nums">${price:,}</td>
            <td class="num-col text-muted tabular-nums">${fmv:,}</td>
            <td class="num-col tabular-nums"><span class="deal-card__delta {delta_cls}">{delta_str}</span></td>
            <td class="num-col tabular-nums">{mileage:,} mi</td>
            <td class="num-col tabular-nums">{dom}d</td>
            <td class="num-col tabular-nums">{dist_str}</td>
            <td><div class="truncate max-w-[140px]" title="{dealer}">{dealer}</div><span class="scope-chip">{platform}</span></td>
            <td class="text-right whitespace-nowrap">
                <div class="flex items-center justify-end gap-1">
                    <button type="button" class="btn btn-ghost text-xs" data-action="pin" data-listing-id="{lid}">Compare</button>
                    <button type="button" hx-post="/api/listing/{lid}/bookmark" hx-target="#deals-container" hx-include="#filter-form" data-action="bookmark" data-listing-id="{lid}" class="btn btn-ghost text-xs">{star_lbl}</button>
                    <button type="button" hx-get="/partials/listing/{lid}/history" hx-target="#modal-body" data-action="analyze" data-listing-id="{lid}" onclick="openModal()" class="btn btn-secondary text-xs">Analyze</button>
                    <button type="button" hx-post="/api/listing/{lid}/dismiss" hx-target="#deals-container" hx-include="#filter-form" data-action="dismiss" data-listing-id="{lid}" class="btn btn-ghost text-xs">{dis_lbl}</button>
                    <a href="{url}" target="_blank" rel="noopener noreferrer" class="btn btn-primary text-xs">View &nearr;</a>
                </div>
            </td>
        </tr>
        """)

    return f"""
    <div class="table-scroll precision-table-wrap" tabindex="0" role="region" aria-label="Sortable Precision Table">
        <table class="precision-table">
            <thead>
                <tr>
                    <th scope="col">#</th>
                    <th scope="col">Score</th>
                    <th scope="col">Vehicle &amp; VIN</th>
                    <th scope="col" class="num-col">Price</th>
                    <th scope="col" class="num-col">Est. FMV</th>
                    <th scope="col" class="num-col">Savings vs FMV</th>
                    <th scope="col" class="num-col">Mileage</th>
                    <th scope="col" class="num-col">DOM</th>
                    <th scope="col" class="num-col">Proximity</th>
                    <th scope="col">Dealer &amp; Channel</th>
                    <th scope="col" class="text-right">Actions</th>
                </tr>
            </thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
    </div>
    """


def render_deals_section(
    deals: List[Dict[str, Any]],
    kpis: Dict[str, Any],
    filters: Dict[str, Any],
) -> str:
    """
    Render KPI summary, triage category tabs, export actions, and deals Grid or Table view.

    Pre-conditions:
        - deals is a list of normalized deal dictionaries.
        - kpis is a dictionary of KPI summary metrics.
        - filters is a dictionary of active filter criteria.

    Post-conditions:
        - Returns HTML fragment containing #kpi-bar, triage tabs, and cards or table.
        - Preserves active filters on export links. Zero emojis.
    """
    view_mode = filters.get("view", "grid")
    current_tab = filters.get("tab", "all")
    export_params = {k: v for k, v in filters.items() if v is not None and v != "" and k != "view"}
    export_qs = urllib.parse.urlencode(export_params)

    sub_tabs = [
        ("all", "All Active", kpis.get("total_active", len(deals))),
        ("excellent", "Excellent &ge; 85", kpis.get("excellent_count", 0)),
        ("good", "Good Value &ge; 75", kpis.get("good_count", 0)),
        ("drops", "Price Drops", kpis.get("price_drops_count", 0)),
        ("saved", "Saved", kpis.get("saved_count", 0)),
        ("dismissed", "Dismissed", kpis.get("dismissed_count", 0)),
    ]
    normalized_tab = "saved" if current_tab in ("saved", "bookmarked") else (
        "drops" if current_tab in ("drops", "price_drops") else current_tab
    )

    tabs_html: List[str] = [
        f'<button type="button" role="tab" class="triage-tab{" is-active" if t_key == normalized_tab else ""}" '
        f'data-action="subtab" data-tab="{t_key}" aria-selected="{str(t_key == normalized_tab).lower()}">'
        f'<span>{t_label}</span> <span class="triage-count tabular-nums">({t_count})</span></button>'
        for t_key, t_label, t_count in sub_tabs
    ]

    if not deals:
        content_html = """
        <div class="empty-state">
            <svg class="empty-state__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
                <circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <h3 class="empty-state__title">No matching vehicles found</h3>
            <p class="empty-state__text">Try relaxing your price, mileage, or make filters, or trigger a fresh marketplace scan above.</p>
        </div>
        """
    elif view_mode == "table":
        content_html = _render_table_view(deals)
    else:
        content_html = _render_grid_view(deals)

    return f"""
    {render_kpis_partial(kpis)}
    <div class="triage-bar">
        <div class="triage-tabs" role="tablist" aria-label="Deal Triage Categories">{''.join(tabs_html)}</div>
        <div class="export-actions">
            <span class="control-hint">Showing <strong class="tabular-nums">{len(deals)}</strong> vehicles</span>
            <a href="/api/export/csv?{export_qs}" class="btn btn-secondary text-xs" download>Export CSV</a>
            <a href="/api/export/markdown?{export_qs}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary text-xs">Export Markdown</a>
        </div>
    </div>
    <div id="deals-view-container">{content_html}</div>
    """.strip()


def render_listing_history_modal(history_data: Optional[Dict[str, Any]]) -> str:
    """
    Render TimescaleDB price history snapshots and 4-factor deal score modal.

    Pre-conditions:
        - history_data is None or a dictionary with 'deal' and 'snapshots'.

    Post-conditions:
        - Returns HTML modal content for #modal-body or drawer.
        - Preserves 'TimescaleDB Price Snapshots', VIN, price, and delta strings. Zero emojis.
    """
    if not history_data:
        return '<div class="p-6 text-muted">Listing not found.</div>'

    d = history_data.get("deal", {})
    snapshots = history_data.get("snapshots", [])
    bd = d.get("score_breakdown", {})

    snap_rows: List[str] = []
    for s in snapshots:
        chg = s.get("price_change", 0)
        badge = (
            f'<span class="deal-card__delta deal-card__delta--neg tabular-nums">-${abs(chg):,}</span>'
            if chg < 0 else (
                f'<span class="deal-card__delta deal-card__delta--pos tabular-nums">+${chg:,}</span>'
                if chg > 0 else '<span class="text-muted tabular-nums">No change</span>'
            )
        )
        snap_rows.append(
            f'<tr><td class="font-mono tabular-nums">{_esc(s.get("time", ""))}</td>'
            f'<td class="num-col font-bold tabular-nums">${s.get("price", 0):,}</td>'
            f'<td class="num-col">{badge}</td><td class="num-col tabular-nums">{s.get("days_on_market", 0)} days</td></tr>'
        )

    p_sc, h_sc = min(100, int(bd.get("price_score", 0))), min(100, int(bd.get("history_score", 0)))
    l_sc, px_sc = min(100, int(bd.get("leverage_score", 0))), min(100, int(bd.get("proximity_score", 0)))

    return f"""
    <div class="modal-content">
        <div class="flex items-start justify-between gap-4 border-b border-subtle pb-4">
            <div>
                <span class="scope-chip">{_esc(d.get('platform', ''))} | VIN: {_esc(d.get('vin', ''))}</span>
                <h2 class="text-lg font-bold text-primary mt-1">{_esc(d.get('title', ''))}</h2>
                <p class="text-xs text-muted mt-1">{_esc(d.get('seller_name', ''))} | {_esc(d.get('location_city', ''))}</p>
            </div>
            <div class="text-right">
                <div class="text-2xl font-bold tabular-nums text-primary">${d.get('price', 0):,}</div>
                <div class="text-xs text-secondary tabular-nums">Est. Fair Value: ${d.get('market_value', 0):,}</div>
            </div>
        </div>
        <div class="mt-5">
            <h3 class="kpi-label mb-3">Composite Deal Score Breakdown ({d.get('deal_score', 0)} / 100 &bull; {_esc(d.get('recommendation', ''))})</h3>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 bg-inset p-4 rounded-lg">
                <div>
                    <div class="flex justify-between text-xs mb-1"><span class="text-secondary">1. Price vs. Market Value (50% weight)</span><span class="font-bold tabular-nums">{bd.get('price_score', 0):.1f} / 100</span></div>
                    <div class="factor-bar"><div class="factor-bar__fill factor-bar__fill--excellent" style="width:{p_sc}%;"></div></div>
                </div>
                <div>
                    <div class="flex justify-between text-xs mb-1"><span class="text-secondary">2. Title &amp; Accident History (25% weight)</span><span class="font-bold tabular-nums">{bd.get('history_score', 0):.1f} / 100</span></div>
                    <div class="factor-bar"><div class="factor-bar__fill factor-bar__fill--info" style="width:{h_sc}%;"></div></div>
                </div>
                <div>
                    <div class="flex justify-between text-xs mb-1"><span class="text-secondary">3. Days on Market Leverage (15% weight)</span><span class="font-bold tabular-nums">{bd.get('leverage_score', 0):.1f} / 100</span></div>
                    <div class="factor-bar"><div class="factor-bar__fill factor-bar__fill--cut" style="width:{l_sc}%;"></div></div>
                </div>
                <div>
                    <div class="flex justify-between text-xs mb-1"><span class="text-secondary">4. Bay Area Proximity (10% weight)</span><span class="font-bold tabular-nums">{bd.get('proximity_score', 0):.1f} / 100</span></div>
                    <div class="factor-bar"><div class="factor-bar__fill factor-bar__fill--telemetry" style="width:{px_sc}%;"></div></div>
                </div>
            </div>
        </div>
        <div class="mt-6">
            <h3 class="kpi-label mb-2">TimescaleDB Price Snapshots ({len(snapshots)} recorded)</h3>
            <div class="table-scroll precision-table-wrap">
                <table class="precision-table">
                    <thead><tr><th scope="col">Recorded Timestamp</th><th scope="col" class="num-col">Listed Price</th><th scope="col" class="num-col">Price Delta</th><th scope="col" class="num-col">Days on Market</th></tr></thead>
                    <tbody>{"".join(snap_rows)}</tbody>
                </table>
            </div>
        </div>
        <div class="mt-6 flex justify-end gap-2">
            <a href="{_esc(d.get('url', '#'))}" target="_blank" rel="noopener noreferrer" class="btn btn-primary text-xs">Open Listing on {_esc(d.get('platform', ''))} &nearr;</a>
        </div>
    </div>
    """.strip()


def render_model_profile_modal(profile: Dict[str, Any]) -> str:
    """
    Render NHTSA Recalls, Consumer Complaints, and EPA Fuel Economy modal.

    Pre-conditions:
        - profile is a dictionary of macro intelligence metrics.

    Post-conditions:
        - Returns HTML modal content for model telemetry inspection. Zero emojis.
    """
    make, model, year = _esc(profile.get("make", "")), _esc(profile.get("model", "")), _esc(profile.get("year", ""))
    recalls, complaints, epa_specs = profile.get("recalls", []), profile.get("complaints", []), profile.get("epa_specs", [])

    epa_html = [
        f'<div class="kpi-card"><div class="font-semibold text-primary">{year} {make} {model}</div>'
        f'<div class="mt-1 flex items-center justify-between text-xs text-secondary">'
        f'<span>Range: <strong class="tabular-nums">{e.get("range_miles") or "N/A"} mi</strong></span>'
        f'<span>Combined: <strong class="tabular-nums">{e.get("comb_mpge") or "N/A"} MPGe</strong></span>'
        f'<span>Est. Fuel Cost: <strong class="tabular-nums">${e.get("annual_fuel_cost") or "N/A"}/yr</strong></span>'
        f'</div></div>'
        for e in epa_specs
    ] or ['<div class="text-xs text-muted">No specific EPA option records returned for this model string.</div>']

    recall_items = [
        f'<div class="p-3 bg-inset border border-strong rounded-lg text-xs space-y-1">'
        f'<div class="flex justify-between font-semibold text-primary"><span>Campaign #{_esc(r.get("campaign_number", ""))}</span><span>{_esc(r.get("component", ""))}</span></div>'
        f'<p class="text-secondary">{_esc(r.get("summary", ""))}</p><p class="text-muted text-2xs"><strong>Remedy:</strong> {_esc(r.get("remedy", ""))}</p></div>'
        for r in recalls[:5]
    ] or ['<div class="p-3 bg-inset rounded-lg text-xs text-secondary">0 NHTSA safety recalls reported for this model year.</div>']

    complaint_items: List[str] = []
    for c in complaints[:5]:
        flags: List[str] = []
        if c.get("crash"):
            flags.append('<span class="market-badge market-badge--danger">Crash</span>')
        if c.get("fire"):
            flags.append('<span class="market-badge market-badge--warn">Fire</span>')
        flag_str = f" {' '.join(flags)}" if flags else ""
        complaint_items.append(
            f'<div class="p-3 bg-inset border border-strong rounded-lg text-xs space-y-1">'
            f'<div class="flex justify-between text-secondary"><span class="font-semibold text-primary">{_esc(c.get("component", ""))}</span>'
            f'<span>ODI #{_esc(c.get("odi_number", ""))}{flag_str}</span></div>'
            f'<p class="text-secondary line-clamp-3">{_esc(c.get("summary", ""))}</p></div>'
        )
    if not complaint_items:
        complaint_items.append('<div class="text-xs text-muted">No NHTSA consumer complaints on file.</div>')

    return f"""
    <div class="modal-content space-y-5 max-h-[80vh] overflow-y-auto">
        <div class="border-b border-subtle pb-3 flex items-center justify-between">
            <div>
                <span class="scope-chip">Macro Intelligence | Federal Safety &amp; Efficiency</span>
                <h2 class="text-lg font-bold text-primary mt-1">{year} {make} {model}</h2>
            </div>
            <div class="flex gap-2 text-xs">
                <span class="market-badge market-badge--warn tabular-nums font-semibold">{profile.get('recalls_count', 0)} Recalls</span>
                <span class="market-badge market-badge--info tabular-nums font-semibold">{profile.get('complaints_count', 0)} Complaints ({profile.get('fire_count', 0)} Fires)</span>
            </div>
        </div>
        <div><h3 class="kpi-label mb-2">EPA Range &amp; Efficiency Benchmarks</h3><div class="grid grid-cols-1 sm:grid-cols-2 gap-2">{''.join(epa_html)}</div></div>
        <div><h3 class="kpi-label mb-2">Official NHTSA Safety Recalls (Top 5)</h3><div class="space-y-2">{''.join(recall_items)}</div></div>
        <div><h3 class="kpi-label mb-2">Consumer Safety Complaints (NHTSA VOQ Sample)</h3><div class="space-y-2">{''.join(complaint_items)}</div></div>
    </div>
    """.strip()


def render_scan_status_banner(workflow_id: str, summary: Dict[str, Any]) -> str:
    """
    Render live polling status banner for an active or completed Temporal scan.

    Pre-conditions:
        - workflow_id is a non-empty string.
        - summary is a dictionary with is_completed, total_scraped, total_scored, and top_deals_count.

    Post-conditions:
        - When running, renders #active-scan-poller with 2s polling trigger.
        - When completed, renders completion banner with refresh trigger.
        - Uses optional settings.temporal_ui_url safely without default local ports. Zero emojis.
    """
    is_completed = bool(summary.get("is_completed", False))
    scraped, scored, top_count = summary.get("total_scraped", 0), summary.get("total_scored", 0), summary.get("top_deals_count", 0)

    temporal_ui_url = getattr(settings, "temporal_ui_url", None)
    if temporal_ui_url:
        clean_url = str(temporal_ui_url).rstrip("/")
        ns = getattr(settings, "temporal_namespace", "default")
        temporal_link = (
            f'<a href="{_esc(clean_url)}/namespaces/{_esc(ns)}/workflows/{_esc(workflow_id)}" '
            f'target="_blank" rel="noopener noreferrer" class="btn btn-ghost text-xs">Inspect in Temporal UI &rarr;</a>'
        )
    else:
        temporal_link = ""

    if is_completed:
        return f"""
        <div class="scan-banner scan-banner--completed"
             hx-get="/partials/deals" hx-target="#deals-container" hx-include="#filter-form" hx-trigger="load">
            <div class="flex items-center gap-2">
                <span class="scan-banner__label">Scan Completed ({_esc(workflow_id)}):</span>
                <span>Scraped <strong class="tabular-nums">{scraped}</strong> listings, scored <strong class="tabular-nums">{scored}</strong> vehicles, found <strong class="tabular-nums">{top_count}</strong> top deals! Inventory refreshed below.</span>
            </div>
            {temporal_link}
        </div>
        """.strip()

    return f"""
    <div id="active-scan-poller"
         hx-get="/api/scan/{_esc(workflow_id)}/status"
         hx-trigger="every 2s"
         hx-swap="outerHTML"
         class="scan-banner scan-banner--running">
        <div class="flex items-center gap-2">
            <span class="scan-banner__dot" aria-hidden="true"></span>
            <span><strong>Temporal Scan Running ({_esc(workflow_id)}):</strong> Scraped <strong class="tabular-nums">{scraped}</strong> listings | Scored <strong class="tabular-nums">{scored}</strong> deals so far...</span>
        </div>
        {temporal_link}
    </div>
    """.strip()


def render_full_dashboard_page(
    deals: List[Dict[str, Any]],
    kpis: Dict[str, Any],
    filters: Dict[str, Any],
    provenance: Optional[Dict[str, Any]] = None,
    market_overview: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Render the complete semantic HTML5 dashboard page.

    Pre-conditions:
        - deals is a list of normalized deal dictionaries.
        - kpis is a dictionary of KPI summary metrics.
        - filters is a dictionary of active filter criteria.
        - provenance is an optional dictionary describing the active data source tier.
        - market_overview is an optional dictionary of market analysis overview data.

    Post-conditions:
        - Loads index.html shell from disk.
        - Populates all placeholder tokens cleanly.
        - Escapes JSON in initial-state script to prevent tag breakouts.
        - Zero external CDN links, zero emojis, zero hardcoded cluster ports.
    """
    template_str = _INDEX_HTML_PATH.read_text(encoding="utf-8")

    prov = provenance or {}
    mode = prov.get("mode", "offline-sample") if isinstance(prov, dict) else str(prov)
    if mode == "timescaledb":
        badge_html = '<span class="provenance-pill provenance-pill--live"><span class="provenance-pill__dot" aria-hidden="true"></span> Live TimescaleDB</span>'
    elif mode == "offline-sample":
        badge_html = '<span class="provenance-pill provenance-pill--offline"><span class="provenance-pill__dot" aria-hidden="true"></span> Offline Sample Dataset</span>'
    else:
        badge_html = f'<span class="provenance-pill provenance-pill--fixture"><span class="provenance-pill__dot" aria-hidden="true"></span> {_esc(str(mode).title())}</span>'

    scan_options = ['<option value="ALL">All 14 Watchlist EVs (Full Surveillance Run)</option>']
    for m in settings.search_target_models:
        scan_options.append(f'<option value="{_esc(m.make)}|{_esc(m.model)}">{_esc(m.make)} {_esc(m.model)}</option>')

    watchlist_options = ['<option value="">All Watchlist Makes &amp; Models</option>']
    seen_makes = set()
    make_filter = filters.get("make_filter") or filters.get("make") or ""
    for m in settings.search_target_models:
        label = f"{m.make} {m.model}"
        if m.make not in seen_makes:
            seen_makes.add(m.make)
            make_sel = " selected" if make_filter == m.make else ""
            watchlist_options.append(f'<option value="{_esc(m.make)}"{make_sel}>{_esc(m.make)} (All Models)</option>')
        sel = " selected" if make_filter == label else ""
        watchlist_options.append(f'<option value="{_esc(label)}"{sel}>&nbsp;&nbsp;&rarr; {_esc(label)}</option>')

    temporal_ui_url = getattr(settings, "temporal_ui_url", None)
    if temporal_ui_url and str(temporal_ui_url).strip():
        temporal_action_html = (
            f'<a href="{_esc(str(temporal_ui_url).strip())}" target="_blank" rel="noopener noreferrer" '
            f'class="btn btn-secondary text-xs">Temporal UI &rarr;</a>'
        )
    else:
        temporal_action_html = ""

    initial_state: Dict[str, Any] = {
        "deals": deals,
        "kpis": kpis,
        "filters": filters,
        "provenance": provenance,
        "market_overview": market_overview,
        "search_context": {
            "zip_code": str(settings.search_zip_code),
            "radius_miles": int(settings.search_radius_miles),
        },
    }
    initial_state_json = json.dumps(initial_state, default=str).replace("</", "<\\/")

    replacements: Dict[str, str] = {
        "{{SEARCH_ZIP}}": _esc(settings.search_zip_code),
        "{{SEARCH_RADIUS}}": str(settings.search_radius_miles),
        "{{PROVENANCE_BADGE}}": badge_html,
        "{{SCAN_OPTIONS_HTML}}": "\n".join(scan_options),
        "{{WATCHLIST_OPTIONS_HTML}}": "\n".join(watchlist_options),
        "{{TEMPORAL_ACTION_HTML}}": temporal_action_html,
        "{{DEGRADED_BANNER_HTML}}": render_degraded_banner(provenance),
        "{{INITIAL_DEALS_HTML}}": render_deals_section(deals, kpis, filters),
        "{{FILTER_TAB}}": _esc(filters.get("tab", "all")),
        "{{FILTER_VIEW}}": _esc(filters.get("view", "grid")),
        "{{FILTER_Q}}": _esc(filters.get("q", "")),
        "{{INITIAL_STATE_JSON}}": initial_state_json,
    }

    rendered = template_str
    for placeholder, val in replacements.items():
        rendered = rendered.replace(placeholder, val)

    return rendered
