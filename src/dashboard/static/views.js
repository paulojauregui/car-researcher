/**
 * Automotive Telemetry Dashboard - Client Workspace Views & Renderers (views.js)
 *
 * Architectural Invariants:
 * - Pure vanilla ES module importing exclusively from ./charts.js (zero CDNs).
 * - Strictly zero emoji glyphs across all templates, icons, labels, and copy.
 * - Design by Contract (DbC) on all exported functions.
 * - Enforces font-variant-numeric: tabular-nums on every numeric metric and VIN.
 * - Enforces complete 5-State Matrix (Empty, Loading CLS=0, Nominal, Degraded, Error).
 * - WCAG 2.2 AA accessibility: explicit labels, aria-sort, role="dialog", focus preservation.
 */

import {
  renderCohortRangeBarHtml,
  renderPriceSparkline,
  escapeSvgText,
} from './charts.js';

/**
 * Escapes unsafe HTML characters to prevent XSS.
 *
 * Pre-conditions:
 *   - value can be string, number, boolean, null, or undefined.
 * Post-conditions:
 *   - Returns safely escaped string representation with XML entities replaced (&, <, >, ", ').
 *   - Returns empty string for null or undefined values.
 *
 * @param {any} value - Raw input value.
 * @returns {string} Escaped HTML string.
 */
export function escapeHtml(value) {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Formats a numeric price into a USD currency string.
 *
 * Pre-conditions:
 *   - val is a numeric price or string convertible to number.
 * Post-conditions:
 *   - Returns formatted string such as "$34,500".
 *   - Returns "$0" for null, undefined, or non-numeric values.
 *
 * @param {number|string} val - Raw price value.
 * @returns {string} Formatted USD string.
 */
export function formatCurrency(val) {
  if (val === null || val === undefined || isNaN(Number(val))) {
    return '$0';
  }
  const num = Math.round(Number(val));
  return '$' + num.toLocaleString('en-US');
}

/**
 * Formats a numeric price delta into a signed USD currency string.
 *
 * Pre-conditions:
 *   - val is a numeric delta or string convertible to number.
 * Post-conditions:
 *   - Returns formatted signed string such as "-$2,450" or "+$1,200" or "$0".
 *
 * @param {number|string} val - Raw delta value.
 * @returns {string} Formatted signed USD string.
 */
export function formatSignedCurrency(val) {
  if (val === null || val === undefined || isNaN(Number(val))) {
    return '$0';
  }
  const num = Math.round(Number(val));
  if (num < 0) {
    return '-$' + Math.abs(num).toLocaleString('en-US');
  }
  if (num > 0) {
    return '+$' + num.toLocaleString('en-US');
  }
  return '$0';
}

/**
 * Formats a number with thousands comma separators.
 *
 * Pre-conditions:
 *   - val is a number or string convertible to number.
 * Post-conditions:
 *   - Returns formatted string such as "19,576" or "0".
 *
 * @param {number|string} val - Raw numeric value.
 * @returns {string} Comma-formatted number string.
 */
export function formatNumber(val) {
  if (val === null || val === undefined || isNaN(Number(val))) {
    return '0';
  }
  const num = Math.round(Number(val));
  return num.toLocaleString('en-US');
}

/**
 * Renders deterministic market badge pills with inline geometric 10px SVGs.
 *
 * Pre-conditions:
 *   - badges is an optional array of market badge string tokens.
 *   - deal is an optional listing object used for fallback derivation.
 *   - limit is a maximum integer count of badges to display (default 4).
 * Post-conditions:
 *   - Returns HTML string containing up to limit .market-badge spans.
 *   - Strictly zero emojis, pure geometric SVG icons.
 *
 * @param {Array<string>} [badges] - Array of badge identifiers.
 * @param {object} [deal] - Listing object for contextual values.
 * @param {number} [limit=4] - Max badges to render.
 * @returns {string} Rendered HTML string of badge elements.
 */
export function renderBadgesHtml(badges, deal = {}, limit = 4) {
  const d = deal || {};
  let badgeList = Array.isArray(badges) ? badges.slice() : [];

  if (badgeList.length === 0 && d.market_badges && Array.isArray(d.market_badges)) {
    badgeList = d.market_badges.slice();
  }

  // Derive badges from deal fields if none were explicitly supplied
  if (badgeList.length === 0) {
    const price = Number(d.price) || 0;
    const p25 = Number(d.cohort_p25) || Number(d.p25) || 0;
    const drop = Number(d.price_drop_total) || (Number(d.price_change) < 0 ? Math.abs(Number(d.price_change)) : 0);
    const dom = Number(d.days_on_market) || 0;
    const lev = Number(d.negotiation_leverage_score) || 0;
    const evEligible = Boolean(d.used_ev_tax_credit?.eligible || (d.analytics && d.analytics.used_ev_tax_credit?.eligible));

    if (p25 > 0 && price <= p25) badgeList.push('BELOW_P25_COHORT');
    if (drop > 0) badgeList.push('FRESH_PRICE_CUT');
    if (dom >= 30) badgeList.push('STALE_INVENTORY_30D');
    if (lev >= 70) badgeList.push('HIGH_LEVERAGE');
    if (evEligible) badgeList.push('USED_EV_TAX_CREDIT');
  }

  const items = badgeList.slice(0, Math.max(1, limit));
  if (items.length === 0) {
    return '';
  }

  return items
    .map((badgeKey) => {
      switch (badgeKey) {
        case 'BELOW_P25_COHORT':
          return `
            <span class="market-badge market-badge--excellent">
              <svg class="market-badge__icon" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
                <polyline points="1.5,5.5 4,8 8.5,2.5"></polyline>
              </svg>
              <span>Below p25</span>
            </span>
          `.trim();
        case 'FRESH_PRICE_CUT': {
          const dropAmt = Number(d.price_drop_total) || (Number(d.price_change) < 0 ? Math.abs(Number(d.price_change)) : 0);
          const dropLabel = dropAmt > 0 ? `Price Cut -${formatCurrency(dropAmt)}` : 'Price Cut';
          return `
            <span class="market-badge market-badge--cut">
              <svg class="market-badge__icon" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
                <line x1="2" y1="2" x2="8" y2="8"></line>
                <polyline points="4,8 8,8 8,4"></polyline>
              </svg>
              <span class="tabular-nums">${escapeHtml(dropLabel)}</span>
            </span>
          `.trim();
        }
        case 'STALE_INVENTORY_30D': {
          const domVal = Number(d.days_on_market) || 30;
          return `
            <span class="market-badge market-badge--warn">
              <svg class="market-badge__icon" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
                <circle cx="5" cy="5" r="4"></circle>
                <polyline points="5,2.5 5,5 7,6.5"></polyline>
              </svg>
              <span class="tabular-nums">Stale ${escapeHtml(domVal)}d+</span>
            </span>
          `.trim();
        }
        case 'HIGH_LEVERAGE': {
          const levScore = Math.round(Number(d.negotiation_leverage_score) || 75);
          return `
            <span class="market-badge market-badge--excellent">
              <svg class="market-badge__icon" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
                <polygon points="5.5,1 2,6 5,6 4.5,9 8,4 5,4"></polygon>
              </svg>
              <span class="tabular-nums">High Leverage ${escapeHtml(levScore)}</span>
            </span>
          `.trim();
        }
        case 'USED_EV_TAX_CREDIT':
          return `
            <span class="market-badge market-badge--excellent">
              <svg class="market-badge__icon" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
                <path d="M5,1 L8.5,2.5 L8.5,5.5 C8.5,7.5 5,9 5,9 C5,9 1.5,7.5 1.5,5.5 L1.5,2.5 Z"></path>
              </svg>
              <span>EV Credit $4k</span>
            </span>
          `.trim();
        default: {
          const cleanLabel = escapeHtml(badgeKey.replace(/_/g, ' '));
          return `
            <span class="market-badge market-badge--info">
              <span class="market-badge__dot"></span>
              <span>${cleanLabel}</span>
            </span>
          `.trim();
        }
      }
    })
    .join(' ');
}

/**
 * Renders the top 4 KPI telemetry cards matching the #kpi-bar specification.
 *
 * Pre-conditions:
 *   - kpis is an object with numerical market summary metrics.
 * Post-conditions:
 *   - Returns HTML containing 4 .kpi-card elements inside #kpi-bar.
 *   - All numeric readouts enforce tabular-nums.
 *
 * @param {object} kpis - KPI metrics dictionary.
 * @returns {string} Rendered HTML string.
 */
export function renderKpiStripHtml(kpis = {}) {
  const k = kpis || {};
  const totalActive = formatNumber(k.total_active || 0);
  const excellentCount = formatNumber(k.excellent_count || 0);
  const belowP25Count = formatNumber(k.below_p25_count || 0);
  const maxSavings = formatCurrency(k.max_savings || 0);
  const avgDiscount = formatCurrency(k.avg_discount || 0);
  const priceDropsCount = formatNumber(k.price_drops_count || 0);
  const highLeverageCount = formatNumber(k.high_leverage_count || 0);
  const taxCreditCount = formatNumber(k.tax_credit_eligible_count || 0);
  const avgMsrpDiscount = (Number(k.avg_msrp_discount_pct) || 0).toFixed(1);
  const avgDom = (Number(k.avg_dom) || 0).toFixed(1);

  return `
<div id="kpi-bar" class="kpi-strip">
  <div class="kpi-card">
    <span class="kpi-label">Active Bay Area Inventory</span>
    <span class="kpi-value tabular-nums">${totalActive}</span>
    <span class="kpi-sub">High-Conviction: <strong class="tabular-nums">${excellentCount}</strong> | Buy-Zone: <strong class="tabular-nums">${belowP25Count}</strong></span>
  </div>
  <div class="kpi-card kpi-card--excellent">
    <span class="kpi-label">High-Conviction Deals (Score &ge; 85)</span>
    <span class="kpi-value tabular-nums">${excellentCount}</span>
    <span class="kpi-sub">Avg MSRP Off: <strong class="tabular-nums">${avgMsrpDiscount}%</strong> | Peak: <strong class="tabular-nums">${maxSavings}</strong></span>
  </div>
  <div class="kpi-card kpi-card--cut">
    <span class="kpi-label">Max &amp; Avg Below-Market Savings</span>
    <span class="kpi-value tabular-nums">-${maxSavings}</span>
    <span class="kpi-sub">Avg discount: <strong class="tabular-nums">-${avgDiscount}</strong></span>
  </div>
  <div class="kpi-card kpi-card--info">
    <span class="kpi-label">Liquidity &amp; Leverage Signals</span>
    <span class="kpi-value tabular-nums">${priceDropsCount} drops</span>
    <span class="kpi-sub">High Leverage: <strong class="tabular-nums">${highLeverageCount}</strong> | EV Credit: <strong class="tabular-nums">${taxCreditCount}</strong> | Avg DOM: <strong class="tabular-nums">${avgDom}d</strong></span>
  </div>
</div>
  `.trim();
}

/**
 * Renders the Deal Workbench section including KPI strip, triage sub-tabs, export links,
 * and either Empty state, Precision Table, or Grid view.
 *
 * Pre-conditions:
 *   - deals is an array of deal objects.
 *   - kpis is an object of market summary metrics.
 *   - filters is an object with active filter and layout state.
 *   - pinnedIds is a Set or Array of currently pinned listing ID strings.
 * Post-conditions:
 *   - Returns full HTML fragment for #deals-container.
 *   - Preserves filter parameters on export links.
 *   - Sets aria-pressed on pin buttons matching pinnedIds.
 *
 * @param {Array<object>} deals - Array of listing objects.
 * @param {object} kpis - KPI metrics dictionary.
 * @param {object} filters - Active filters dictionary.
 * @param {Set|Array<string>} [pinnedIds] - Set or Array of pinned IDs.
 * @returns {string} Rendered HTML string.
 */
export function renderDealsSectionHtml(deals = [], kpis = {}, filters = {}, pinnedIds = new Set()) {
  const dList = Array.isArray(deals) ? deals : [];
  const k = kpis || {};
  const f = filters || {};
  const currentTab = f.tab || 'all';
  const viewMode = f.view || 'grid';
  const pinnedSet = pinnedIds instanceof Set ? pinnedIds : new Set(pinnedIds || []);

  // Build export query string preserving active filters (excluding view)
  const exportParams = new URLSearchParams();
  for (const [key, val] of Object.entries(f)) {
    if (val !== null && val !== undefined && val !== '' && key !== 'view') {
      exportParams.set(key, String(val));
    }
  }
  const exportQs = exportParams.toString();

  const subTabs = [
    { key: 'all', label: 'All Active', count: k.total_active ?? dList.length },
    { key: 'excellent', label: 'Excellent >= 85', count: k.excellent_count ?? 0 },
    { key: 'good', label: 'Good Value >= 75', count: k.good_count ?? 0 },
    { key: 'drops', label: 'Price Drops', count: k.price_drops_count ?? 0 },
    { key: 'saved', label: 'Saved', count: k.saved_count ?? 0 },
    { key: 'dismissed', label: 'Dismissed', count: k.dismissed_count ?? 0 },
  ];

  const tabsHtml = subTabs
    .map((tab) => {
      const isActive = tab.key === currentTab;
      const activeClass = isActive ? ' is-active' : '';
      return `
        <button type="button" role="tab" class="triage-tab${activeClass}" data-tab="${escapeHtml(tab.key)}" aria-selected="${isActive}">
          <span>${escapeHtml(tab.label)}</span>
          <span class="triage-count tabular-nums">(${formatNumber(tab.count)})</span>
        </button>
      `.trim();
    })
    .join('\n');

  let contentHtml = '';
  if (dList.length === 0) {
    let emptyTitle = 'No matching vehicles found';
    let emptyText = 'Try adjusting your search query, price, mileage, or make filters to expand your results.';
    let ctaHtml = '<button type="button" class="btn btn-secondary" data-action="reset-filters">Reset All Filters</button>';

    if (currentTab === 'saved') {
      emptyTitle = 'No saved vehicles yet';
      emptyText = 'Save vehicles from All Active to build your personalized shortlist.';
      ctaHtml = '<button type="button" class="btn btn-secondary" data-action="set-tab" data-tab="all">Browse All Active</button>';
    } else if (currentTab === 'dismissed') {
      emptyTitle = 'No hidden vehicles';
      emptyText = 'Vehicles you dismiss will appear here so you can review or restore them at any time.';
      ctaHtml = '<button type="button" class="btn btn-secondary" data-action="set-tab" data-tab="all">Browse All Active</button>';
    }

    contentHtml = `
      <div class="empty-state">
        <svg class="empty-state__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <h3 class="empty-state__title">${escapeHtml(emptyTitle)}</h3>
        <p class="empty-state__text">${escapeHtml(emptyText)}</p>
        <div>${ctaHtml}</div>
      </div>
    `.trim();
  } else if (viewMode === 'table') {
    contentHtml = renderPrecisionTableHtml(dList, f, pinnedSet);
  } else {
    contentHtml = renderDealsGridHtml(dList, pinnedSet);
  }

  return `
${renderKpiStripHtml(k)}

<div class="triage-bar">
  <div class="triage-tabs" role="tablist" aria-label="Deal Triage Categories">
    ${tabsHtml}
  </div>
  <div class="export-actions">
    <span class="control-hint">Showing <strong class="tabular-nums">${formatNumber(dList.length)}</strong> vehicles</span>
    <a href="/api/export/csv?${exportQs}" class="btn btn-secondary" download>Export CSV</a>
    <a href="/api/export/markdown?${exportQs}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary">Export Markdown</a>
  </div>
</div>

<div id="deals-view-container">
  ${contentHtml}
</div>
  `.trim();
}

/**
 * Helper rendering the precision sortable table.
 *
 * Pre-conditions:
 *   - deals is an array of listing objects.
 *   - filters is an object containing sort criteria.
 *   - pinnedSet is a Set of pinned IDs.
 * Post-conditions:
 *   - Returns HTML with table, scope="col", aria-sort, and tabular-nums.
 *
 * @param {Array<object>} deals - Listings.
 * @param {object} filters - Filters.
 * @param {Set<string>} pinnedSet - Pinned set.
 * @returns {string} Rendered table HTML.
 */
function renderPrecisionTableHtml(deals, filters, pinnedSet) {
  const currentSort = filters.sort || 'score_desc';

  function getAriaSort(keyAsc, keyDesc) {
    if (currentSort === keyAsc) return 'ascending';
    if (currentSort === keyDesc) return 'descending';
    return 'none';
  }

  const rowsHtml = deals
    .map((d, idx) => {
      const lid = String(d.id || d.platform_id || d.vin || '');
      const isPinned = pinnedSet.has(lid);
      const isBookmarked = Boolean(d.is_bookmarked || d.raw_data?.user_bookmarked);
      const isDismissed = Boolean(d.is_dismissed || d.raw_data?.user_dismissed);
      const price = Number(d.price) || 0;
      const fmv = Number(d.market_value) || 0;
      const delta = Number(d.price_delta) || (price - fmv);
      const pct = Number(d.pct_savings) || 0;
      const score = Number(d.deal_score) || 0;
      const msrpOff = Number(d.msrp_discount_pct) || 0;
      const mileage = Number(d.mileage) || 0;
      const dom = Number(d.days_on_market) || 0;
      const leverage = Number(d.negotiation_leverage_score) || 0;
      const dist = d.distance_miles != null ? Number(d.distance_miles) : null;
      const distLabel = dist != null ? `${dist.toFixed(1)} mi` : 'N/A';
      const seller = d.seller_name || 'Dealer';
      const city = d.location_city || 'Bay Area';
      const vin = d.vin || '';
      const platform = (d.platform || 'Cars.com').toUpperCase();
      const title = d.title || `${d.year || ''} ${d.make || ''} ${d.model || ''}`.trim();

      const deltaClass = delta <= 0 ? 'deal-card__delta--neg' : 'deal-card__delta--pos';
      const deltaText = `${formatSignedCurrency(delta)} (${pct.toFixed(1)}%)`;

      let scorePillClass = 'score-pill--info';
      if (score >= 85) scorePillClass = 'score-pill--excellent';
      else if (score < 60) scorePillClass = 'score-pill--danger';

      return `
        <tr class="${isPinned ? 'is-pinned' : ''}" data-listing-id="${escapeHtml(lid)}">
          <td class="tabular-nums font-mono">#${idx + 1}</td>
          <td>
            <span class="score-pill ${scorePillClass} tabular-nums">${score.toFixed(1)}</span>
          </td>
          <td>
            <div class="font-semibold text-primary">${escapeHtml(title)}</div>
            <div class="deal-card__badges mt-1">
              <button type="button" class="vin-chip tabular-nums" data-action="copy-vin" data-vin="${escapeHtml(vin)}" title="Copy VIN">
                ${escapeHtml(vin || 'NO VIN')}
              </button>
              ${renderBadgesHtml(d.market_badges, d, 2)}
            </div>
          </td>
          <td class="num-col font-bold text-primary tabular-nums">${formatCurrency(price)}</td>
          <td class="num-col text-muted tabular-nums">${formatCurrency(fmv)}</td>
          <td class="num-col tabular-nums">
            <span class="${deltaClass}">${escapeHtml(deltaText)}</span>
          </td>
          <td class="num-col tabular-nums">${msrpOff.toFixed(1)}%</td>
          <td class="num-col tabular-nums">${formatNumber(mileage)} mi</td>
          <td class="num-col tabular-nums">${formatNumber(dom)}d</td>
          <td class="num-col tabular-nums">
            <span class="font-semibold">${leverage.toFixed(0)}</span>
          </td>
          <td class="num-col tabular-nums">${escapeHtml(distLabel)}</td>
          <td>
            <div class="truncate max-w-[140px]" title="${escapeHtml(seller)}">${escapeHtml(seller)}</div>
            <span class="scope-chip">${escapeHtml(platform)}</span>
          </td>
          <td>
            <div class="flex items-center gap-1">
              <button type="button" class="btn btn-ghost btn-icon" data-action="pin" data-listing-id="${escapeHtml(lid)}" aria-pressed="${isPinned}" title="${isPinned ? 'Unpin' : 'Pin to compare'}">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M9.5,2 L14,6.5 L11,9.5 L12,13.5 L8,9.5 L4,13.5 L2.5,12 L6.5,8 L2.5,4 L6.5,5 L9.5,2 Z"></path></svg>
              </button>
              <button type="button" class="btn btn-ghost btn-icon" data-action="bookmark" data-listing-id="${escapeHtml(lid)}" aria-pressed="${isBookmarked}" title="${isBookmarked ? 'Saved' : 'Save'}">
                <svg viewBox="0 0 16 16" fill="${isBookmarked ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><polygon points="8,1.5 10,6 15,6.5 11.2,10 12.5,15 8,12.2 3.5,15 4.8,10 1,6.5 6,6"></polygon></svg>
              </button>
              <button type="button" class="btn btn-secondary text-xs" data-action="analyze" data-listing-id="${escapeHtml(lid)}">Analyze</button>
              <button type="button" class="btn btn-ghost text-xs" data-action="dismiss" data-listing-id="${escapeHtml(lid)}">${isDismissed ? 'Restore' : 'Hide'}</button>
            </div>
          </td>
        </tr>
      `.trim();
    })
    .join('\n');

  return `
<div class="table-scroll precision-table-wrap" tabindex="0" role="region" aria-label="Sortable Precision Table">
  <table class="precision-table">
    <thead>
      <tr>
        <th scope="col">#</th>
        <th scope="col">
          <button type="button" class="sort-btn" data-sort="score_desc" aria-sort="${getAriaSort('score_asc', 'score_desc')}">Score</button>
        </th>
        <th scope="col">Vehicle &amp; VIN</th>
        <th scope="col" class="num-col">
          <button type="button" class="sort-btn" data-sort="price_asc" aria-sort="${getAriaSort('price_asc', 'price_desc')}">Price</button>
        </th>
        <th scope="col" class="num-col">Est. FMV</th>
        <th scope="col" class="num-col">
          <button type="button" class="sort-btn" data-sort="savings_asc" aria-sort="${getAriaSort('savings_asc', 'savings_desc')}">Delta vs FMV</button>
        </th>
        <th scope="col" class="num-col">% Off MSRP</th>
        <th scope="col" class="num-col">
          <button type="button" class="sort-btn" data-sort="mileage_asc" aria-sort="${getAriaSort('mileage_asc', 'mileage_desc')}">Mileage</button>
        </th>
        <th scope="col" class="num-col">
          <button type="button" class="sort-btn" data-sort="dom_desc" aria-sort="${getAriaSort('dom_asc', 'dom_desc')}">DOM</button>
        </th>
        <th scope="col" class="num-col">
          <button type="button" class="sort-btn" data-sort="leverage_desc" aria-sort="${getAriaSort('leverage_asc', 'leverage_desc')}">Leverage</button>
        </th>
        <th scope="col" class="num-col">
          <button type="button" class="sort-btn" data-sort="distance_asc" aria-sort="${getAriaSort('distance_asc', 'distance_desc')}">Distance</button>
        </th>
        <th scope="col">Dealer &amp; Channel</th>
        <th scope="col">Actions</th>
      </tr>
    </thead>
    <tbody>
      ${rowsHtml}
    </tbody>
  </table>
</div>
  `.trim();
}

/**
 * Helper rendering the deals card grid.
 *
 * Pre-conditions:
 *   - deals is an array of listing objects.
 *   - pinnedSet is a Set of pinned IDs.
 * Post-conditions:
 *   - Returns HTML with .deals-grid and .deal-card elements.
 *
 * @param {Array<object>} deals - Listings.
 * @param {Set<string>} pinnedSet - Pinned set.
 * @returns {string} Rendered grid HTML.
 */
function renderDealsGridHtml(deals, pinnedSet) {
  const cardsHtml = deals
    .map((d, idx) => {
      const lid = String(d.id || d.platform_id || d.vin || '');
      const isPinned = pinnedSet.has(lid);
      const isBookmarked = Boolean(d.is_bookmarked || d.raw_data?.user_bookmarked);
      const isDismissed = Boolean(d.is_dismissed || d.raw_data?.user_dismissed);
      const price = Number(d.price) || 0;
      const fmv = Number(d.market_value) || 0;
      const delta = Number(d.price_delta) || (price - fmv);
      const pct = Number(d.pct_savings) || 0;
      const score = Number(d.deal_score) || 0;
      const mileage = Number(d.mileage) || 0;
      const dom = Number(d.days_on_market) || 0;
      const leverage = Number(d.negotiation_leverage_score) || 0;
      const dist = d.distance_miles != null ? Number(d.distance_miles) : null;
      const distLabel = dist != null ? `${dist.toFixed(1)} mi` : 'Bay Area';
      const seller = d.seller_name || 'Dealer';
      const city = d.location_city || 'Bay Area';
      const vin = d.vin || '';
      const platform = (d.platform || 'Cars.com').toUpperCase();
      const title = d.title || `${d.year || ''} ${d.make || ''} ${d.model || ''}`.trim();
      const thumb = d.thumbnail || '';
      const isCpo = Boolean(d.cpo || d.raw_data?.cpoIndicator);

      const bd = d.score_breakdown || {};
      const priceScore = Math.min(100, Math.max(0, Math.round(Number(bd.price_score) || 75)));
      const histScore = Math.min(100, Math.max(0, Math.round(Number(bd.history_score) || 80)));
      const domScore = Math.min(100, Math.max(0, Math.round(Number(bd.leverage_score) || 70)));
      const proxScore = Math.min(100, Math.max(0, Math.round(Number(bd.proximity_score) || 85)));

      const deltaClass = delta <= 0 ? 'deal-card__delta--neg' : 'deal-card__delta--pos';
      const deltaText = `${formatSignedCurrency(delta)} (${pct.toFixed(1)}%) vs FMV`;

      let scorePillClass = 'score-pill--info';
      let recLabel = 'Good Value';
      if (score >= 85) {
        scorePillClass = 'score-pill--excellent';
        recLabel = 'Excellent Deal';
      } else if (score < 60) {
        scorePillClass = 'score-pill--danger';
        recLabel = 'Fair / High Risk';
      }

      const mediaHtml = thumb
        ? `<img src="${escapeHtml(thumb)}" alt="${escapeHtml(title)}" loading="lazy" />`
        : `
          <svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
            <path d="M12,40 L16,26 L48,26 L52,40 Z"></path>
            <circle cx="20" cy="42" r="6"></circle>
            <circle cx="44" cy="42" r="6"></circle>
          </svg>
        `.trim();

      return `
        <article class="deal-card${isPinned ? ' is-pinned' : ''}" data-listing-id="${escapeHtml(lid)}">
          <div class="deal-card__media">
            ${mediaHtml}
            <div class="deal-card__overlay-tl">
              <span class="scope-chip tabular-nums">#${idx + 1}</span>
              <span class="provenance-pill">${escapeHtml(platform)}</span>
              ${isCpo ? '<span class="provenance-pill provenance-pill--live">CPO</span>' : ''}
            </div>
            <div class="deal-card__overlay-tr">
              <span class="score-pill ${scorePillClass}">
                <span class="tabular-nums">${score.toFixed(1)}</span>
                <span>&bull;</span>
                <span>${escapeHtml(recLabel)}</span>
              </span>
            </div>
          </div>

          <div class="deal-card__body">
            <h3 class="deal-card__title">
              <a href="${escapeHtml(d.url || '#')}" target="_blank" rel="noopener noreferrer">${escapeHtml(title)}</a>
            </h3>

            <div class="deal-card__price-row">
              <div class="deal-card__price-primary">
                <span class="deal-card__price tabular-nums">${formatCurrency(price)}</span>
                <span class="deal-card__fmv tabular-nums">FMV ${formatCurrency(fmv)}</span>
              </div>
              <span class="deal-card__delta ${deltaClass} tabular-nums">${escapeHtml(deltaText)}</span>
            </div>

            ${renderCohortRangeBarHtml(d)}

            <div class="deal-card__badges">
              ${renderBadgesHtml(d.market_badges, d, 4)}
            </div>

            <div class="deal-card__factors">
              <div class="factor-item">
                <span class="factor-label">Price</span>
                <span class="factor-value tabular-nums">${priceScore}</span>
                <div class="factor-bar"><div class="factor-bar__fill factor-bar__fill--excellent" style="width: ${priceScore}%;"></div></div>
              </div>
              <div class="factor-item">
                <span class="factor-label">Hist</span>
                <span class="factor-value tabular-nums">${histScore}</span>
                <div class="factor-bar"><div class="factor-bar__fill factor-bar__fill--info" style="width: ${histScore}%;"></div></div>
              </div>
              <div class="factor-item">
                <span class="factor-label">DOM</span>
                <span class="factor-value tabular-nums">${domScore}</span>
                <div class="factor-bar"><div class="factor-bar__fill factor-bar__fill--cut" style="width: ${domScore}%;"></div></div>
              </div>
              <div class="factor-item">
                <span class="factor-label">Prox</span>
                <span class="factor-value tabular-nums">${proxScore}</span>
                <div class="factor-bar"><div class="factor-bar__fill factor-bar__fill--telemetry" style="width: ${proxScore}%;"></div></div>
              </div>
            </div>

            <div class="deal-card__meta">
              <div class="deal-card__meta-item">
                <span class="text-muted">Odometer:</span>
                <strong class="tabular-nums">${formatNumber(mileage)} mi</strong>
              </div>
              <div class="deal-card__meta-item">
                <span class="text-muted">Location:</span>
                <span class="tabular-nums">${escapeHtml(distLabel)} (${escapeHtml(city)})</span>
              </div>
              <div class="deal-card__meta-item">
                <span class="text-muted">DOM / Lev:</span>
                <span class="tabular-nums">${dom}d / Lev ${leverage.toFixed(0)}</span>
              </div>
              <div class="deal-card__meta-item">
                <button type="button" class="vin-chip tabular-nums" data-action="copy-vin" data-vin="${escapeHtml(vin)}" title="Copy VIN">
                  ${escapeHtml(vin || 'NO VIN')}
                </button>
              </div>
            </div>
          </div>

          <div class="deal-card__footer">
            <div class="flex items-center gap-1">
              <button type="button" class="btn btn-secondary text-xs" data-action="pin" data-listing-id="${escapeHtml(lid)}" aria-pressed="${isPinned}">
                ${isPinned ? 'Pinned' : 'Compare'}
              </button>
              <button type="button" class="btn btn-ghost text-xs" data-action="bookmark" data-listing-id="${escapeHtml(lid)}" aria-pressed="${isBookmarked}">
                ${isBookmarked ? 'Saved' : 'Save'}
              </button>
              <button type="button" class="btn btn-ghost text-xs" data-action="dismiss" data-listing-id="${escapeHtml(lid)}">
                ${isDismissed ? 'Restore' : 'Hide'}
              </button>
            </div>
            <div class="flex items-center gap-1">
              <button type="button" class="btn btn-primary text-xs" data-action="analyze" data-listing-id="${escapeHtml(lid)}">Analyze</button>
              <a href="${escapeHtml(d.url || '#')}" target="_blank" rel="noopener noreferrer" class="btn btn-ghost text-xs" aria-label="Open listing on ${escapeHtml(platform)}">Open &nearr;</a>
            </div>
          </div>
        </article>
      `.trim();
    })
    .join('\n');

  return `<div class="deals-grid">${cardsHtml}</div>`;
}

/**
 * Renders geometry-matched CLS = 0 loading skeleton states for the Deal Workbench.
 *
 * Pre-conditions:
 *   - viewMode is 'grid' or 'table'.
 * Post-conditions:
 *   - Returns HTML containing exact height skeleton blocks preserving layout space.
 *   - aria-busy="true" declared on container.
 *
 * @param {string} [viewMode='grid'] - Active view layout.
 * @returns {string} Rendered loading skeleton HTML.
 */
export function renderWorkbenchLoadingHtml(viewMode = 'grid') {
  const kpiSkeletons = `
    <div class="kpi-strip" aria-busy="true" aria-label="Loading summary metrics">
      <div class="skeleton skeleton-kpi"></div>
      <div class="skeleton skeleton-kpi"></div>
      <div class="skeleton skeleton-kpi"></div>
      <div class="skeleton skeleton-kpi"></div>
    </div>
  `.trim();

  let bodySkeletons = '';
  if (viewMode === 'table') {
    const rows = Array.from({ length: 8 }, () => '<div class="skeleton skeleton-table-row"></div>').join('\n');
    bodySkeletons = `
      <div class="precision-table-wrap" aria-busy="true" aria-label="Loading listings table">
        ${rows}
      </div>
    `.trim();
  } else {
    const cards = Array.from({ length: 6 }, () => `
      <div class="skeleton-card" aria-busy="true">
        <div class="skeleton skeleton-card__media"></div>
        <div class="p-4 flex flex-col gap-3">
          <div class="skeleton h-5 w-3/4"></div>
          <div class="skeleton h-7 w-1/2"></div>
          <div class="skeleton h-12 w-full"></div>
          <div class="skeleton h-8 w-full"></div>
        </div>
      </div>
    `).join('\n');
    bodySkeletons = `<div class="deals-grid">${cards}</div>`;
  }

  return `
${kpiSkeletons}
<div class="triage-bar my-4">
  <div class="skeleton h-8 w-72"></div>
  <div class="skeleton h-8 w-48"></div>
</div>
${bodySkeletons}
  `.trim();
}

/**
 * Renders an inline recoverable error alert state preserving user context.
 *
 * Pre-conditions:
 *   - message is an error description string.
 *   - retryAction is an action identifier passed to data-retry-action.
 * Post-conditions:
 *   - Returns .error-state HTML with explicit retry button.
 *
 * @param {string} message - Error details.
 * @param {string} [retryAction='retry'] - Retry callback key.
 * @returns {string} Rendered error state HTML.
 */
export function renderWorkspaceErrorHtml(message, retryAction = 'retry') {
  const cleanMsg = escapeHtml(message || 'Failed to complete network request.');
  const cleanAction = escapeHtml(retryAction || 'retry');

  return `
<div class="error-state" role="alert" aria-live="assertive">
  <svg class="error-state__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
    <circle cx="12" cy="12" r="10"></circle>
    <line x1="12" y1="8" x2="12" y2="12"></line>
    <line x1="12" y1="16" x2="12.01" y2="16"></line>
  </svg>
  <h3 class="error-state__title">Unable to Load Data</h3>
  <p class="error-state__text">${cleanMsg}</p>
  <button type="button" class="btn btn-secondary" data-retry-action="${cleanAction}">Retry</button>
</div>
  `.trim();
}

/**
 * Renders Workspace 2 (Market Intelligence) containing valuation frontier controls,
 * telemetry summary pills, 14-model leaderboard, and momentum feed.
 *
 * Pre-conditions:
 *   - overview is an object from GET /api/market/overview.
 *   - cohortsData is an object from GET /api/market/cohorts.
 *   - selectedCohortKey is the currently selected cohort string key.
 *   - pinnedIds is a Set or Array of pinned listing ID strings.
 * Post-conditions:
 *   - Populates #cohort-select options matching cohortsData.cohorts.
 *   - Populates #cohort-leaderboard including 0-inventory watchlist models.
 *   - Populates #momentum-feed dual panels.
 *
 * @param {object} overview - Market overview analytics.
 * @param {object} cohortsData - Cohort statistics.
 * @param {string} [selectedCohortKey='ALL'] - Active cohort key.
 * @param {Set|Array<string>} [pinnedIds] - Pinned listing IDs.
 * @returns {string} Rendered HTML string for Workspace 2.
 */
export function renderMarketWorkspaceHtml(overview = {}, cohortsData = {}, selectedCohortKey = 'ALL', pinnedIds = new Set()) {
  const ov = overview || {};
  const cd = cohortsData || {};
  const cohorts = cd.cohorts || {};
  const selKey = selectedCohortKey || 'ALL';
  const sel = cd.selected_cohort || cohorts[selKey] || cd.all_scatter || {};

  const sampleSize = Number(sel.sample_size) || (Array.isArray(sel.scatter_points) ? sel.scatter_points.length : 0);
  const confidence = sel.confidence_tier || 'LOW';
  const scope = sel.cohort_scope || 'exact';
  const slope = sel.ols_trendline ? `${formatCurrency(sel.ols_trendline.slope_per_1k_miles)}/1k mi` : 'N/A';
  const r2 = sel.ols_trendline && sel.ols_trendline.r_squared != null ? sel.ols_trendline.r_squared.toFixed(2) : 'N/A';
  const p25 = sel.p25 != null ? formatCurrency(sel.p25) : 'N/A';
  const p50 = sel.p50 != null ? formatCurrency(sel.p50) : 'N/A';

  // Cohort select options
  const cohortOptions = ['ALL', ...Object.keys(cohorts).filter((k) => k !== 'ALL')]
    .map((k) => {
      const c = cohorts[k] || {};
      const n = c.sample_size || 0;
      const conf = c.confidence_tier || 'LOW';
      const label = k === 'ALL' ? `All Tracked EVs (${n} listings)` : `${k.replace(/\|/g, ' ')} (n=${n}, ${conf})`;
      const isSelected = k === selKey;
      return `<option value="${escapeHtml(k)}"${isSelected ? ' selected' : ''}>${escapeHtml(label)}</option>`;
    })
    .join('\n');

  // Accessible scatter data fallback table
  const scatterPoints = sel.scatter_points || cd.scatter || [];
  const scatterTableRows = scatterPoints.slice(0, 50).map((pt) => `
    <tr>
      <td>${escapeHtml(pt.title || `${pt.year || ''} ${pt.make || ''} ${pt.model || ''}`)}</td>
      <td class="num-col tabular-nums">${formatCurrency(pt.price)}</td>
      <td class="num-col tabular-nums">${formatNumber(pt.mileage)} mi</td>
      <td class="num-col tabular-nums">${pt.deal_score != null ? Number(pt.deal_score).toFixed(1) : 'N/A'}</td>
      <td class="num-col tabular-nums">${pt.days_on_market != null ? pt.days_on_market : 'N/A'}d</td>
    </tr>
  `).join('\n');

  // 14-Model Leaderboard
  const leaderboard = ov.leaderboard || [];
  const leaderboardRows = leaderboard.map((row) => {
    const isZero = row.sample_size === 0;
    const make = row.make || '';
    const model = row.model || '';
    const topScore = Number(row.top_deal_score) || 0;
    const bestDealId = row.best_deal_id || '';

    return `
      <tr class="${isZero ? 'opacity-60' : ''}">
        <td>
          <div class="font-semibold">${escapeHtml(make)} ${escapeHtml(model)}</div>
          <span class="control-hint">${escapeHtml(row.cohort_key || '')}</span>
        </td>
        <td class="num-col tabular-nums">
          <span class="font-bold">${formatNumber(row.sample_size)}</span>
          <span class="scope-chip ml-1">${escapeHtml(row.confidence_tier)}</span>
        </td>
        <td class="num-col tabular-nums">${isZero ? '--' : formatCurrency(row.p25)}</td>
        <td class="num-col tabular-nums font-semibold">${isZero ? '--' : formatCurrency(row.median_price)}</td>
        <td class="num-col tabular-nums">${isZero ? '--' : formatCurrency(row.p75)}</td>
        <td class="num-col tabular-nums">${isZero ? '--' : `$${Number(row.median_price_per_1k_miles).toFixed(1)}`}</td>
        <td class="num-col tabular-nums">${isZero ? '--' : `${Number(row.avg_msrp_discount_pct).toFixed(1)}%`}</td>
        <td class="num-col tabular-nums">${isZero ? '--' : `${Number(row.avg_dom).toFixed(1)}d`}</td>
        <td class="num-col tabular-nums">${isZero ? '--' : `${formatNumber(row.price_cut_count)} (${Number(row.price_cut_share_pct).toFixed(0)}%)`}</td>
        <td class="num-col tabular-nums">
          ${isZero ? '--' : `<span class="score-pill score-pill--${topScore >= 85 ? 'excellent' : 'info'}">${topScore.toFixed(1)}</span>`}
        </td>
        <td>
          <div class="flex items-center gap-1">
            <button type="button" class="btn btn-secondary text-xs" data-action="plot-frontier" data-cohort-key="${escapeHtml(row.cohort_key || '')}">
              Plot Frontier
            </button>
            <button type="button" class="btn btn-ghost text-xs" data-action="filter-workbench" data-make="${escapeHtml(make)}" data-model="${escapeHtml(model)}">
              Filter
            </button>
          </div>
        </td>
      </tr>
    `.trim();
  }).join('\n');

  // Momentum feed: Fresh price cuts & Stale high leverage
  const cutMovers = ov.price_cut_movers || [];
  const staleInventory = ov.stale_high_leverage || [];

  const cutMoversHtml = cutMovers.length === 0
    ? '<div class="empty-state text-xs p-4">No recent price drops in active inventory.</div>'
    : cutMovers.map((m) => {
        const lid = String(m.id || m.platform_id || m.vin || '');
        const dropAmt = Number(m.price_drop_total) || 0;
        const dropPct = Number(m.price_drop_pct) || 0;
        const vel = Number(m.price_velocity_per_week) || 0;
        return `
          <div class="momentum-row">
            <div>
              <div class="font-semibold text-primary">${escapeHtml(m.title || `${m.year || ''} ${m.make || ''} ${m.model || ''}`)}</div>
              <div class="control-hint tabular-nums">Current ${formatCurrency(m.price)} | Initial ${formatCurrency(m.initial_price || (m.price + dropAmt))}</div>
            </div>
            <div class="text-right">
              <span class="deal-card__delta deal-card__delta--neg tabular-nums">-${formatCurrency(dropAmt)} (-${dropPct.toFixed(1)}%)</span>
              <div class="control-hint tabular-nums">-$${vel.toFixed(0)}/wk &bull; Score ${Number(m.deal_score || 0).toFixed(1)}</div>
            </div>
            <button type="button" class="btn btn-secondary text-xs" data-action="analyze" data-listing-id="${escapeHtml(lid)}">Analyze</button>
          </div>
        `.trim();
      }).join('\n');

  const staleInventoryHtml = staleInventory.length === 0
    ? '<div class="empty-state text-xs p-4">No high-leverage inventory exceeding 30 days.</div>'
    : staleInventory.map((s) => {
        const lid = String(s.id || s.platform_id || s.vin || '');
        const dom = Number(s.days_on_market) || 0;
        const lev = Number(s.negotiation_leverage_score) || 0;
        const target = Number(s.suggested_offer_target) || Number(s.price) || 0;
        return `
          <div class="momentum-row">
            <div>
              <div class="font-semibold text-primary">${escapeHtml(s.title || `${s.year || ''} ${s.make || ''} ${s.model || ''}`)}</div>
              <div class="control-hint tabular-nums">${dom}d on market &bull; Target: ${formatCurrency(target)}</div>
            </div>
            <div class="text-right">
              <span class="market-badge market-badge--warn tabular-nums">DOM ${dom}d</span>
              <span class="market-badge market-badge--excellent tabular-nums">Lev ${lev.toFixed(0)}</span>
            </div>
            <button type="button" class="btn btn-secondary text-xs" data-action="analyze" data-listing-id="${escapeHtml(lid)}">Analyze</button>
          </div>
        `.trim();
      }).join('\n');

  return `
<div id="frontier-chart" class="frontier-panel">
  <div class="frontier-controls">
    <div>
      <label for="cohort-select" class="control-label">Active Valuation Cohort</label>
      <select id="cohort-select" class="control-select">
        ${cohortOptions}
      </select>
    </div>
    <div class="frontier-legend">
      <span class="frontier-legend-item">
        <span class="frontier-legend-dot frontier-legend-dot--buyzone"></span>
        <span>Buy-Zone (Score &ge; 85)</span>
      </span>
      <span class="frontier-legend-item">
        <span class="frontier-legend-dot frontier-legend-dot--fair"></span>
        <span>Good Value (75-84)</span>
      </span>
      <span class="frontier-legend-item">
        <span class="frontier-legend-dot frontier-legend-dot--overpriced"></span>
        <span>Fair / Elevated</span>
      </span>
      <span class="frontier-legend-item">
        <span class="frontier-legend-line frontier-legend-line--ols"></span>
        <span>OLS Regression</span>
      </span>
      <span class="frontier-legend-item">
        <span class="frontier-legend-line frontier-legend-line--p25"></span>
        <span>p25 Buy-Zone</span>
      </span>
    </div>
  </div>

  <div class="frontier-stats">
    <span class="frontier-stat-pill">Sample Size: <strong class="tabular-nums">n=${formatNumber(sampleSize)}</strong></span>
    <span class="frontier-stat-pill">Confidence: <strong>${escapeHtml(confidence)}</strong></span>
    <span class="frontier-stat-pill">Scope: <strong>${escapeHtml(scope)}</strong></span>
    <span class="frontier-stat-pill">OLS Slope: <strong class="tabular-nums">${escapeHtml(slope)}</strong></span>
    <span class="frontier-stat-pill">Fit R^2: <strong class="tabular-nums">${escapeHtml(r2)}</strong></span>
    <span class="frontier-stat-pill">p25 Buy-Zone: <strong class="tabular-nums">${escapeHtml(p25)}</strong></span>
    <span class="frontier-stat-pill">Median p50: <strong class="tabular-nums">${escapeHtml(p50)}</strong></span>
  </div>

  <div id="frontier-svg-wrapper" class="mt-4">
    <!-- SVG Frontier Chart dynamically rendered via renderFrontierChart() from charts.js -->
    <div id="frontier-svg-container"></div>
    <div id="frontier-tooltip" class="chart-tooltip" hidden></div>
  </div>

  <details class="mt-4 text-xs">
    <summary class="cursor-pointer text-muted hover:text-primary">View Scatter Coordinates as Precision Table</summary>
    <div class="table-scroll mt-2">
      <table class="precision-table">
        <thead>
          <tr>
            <th scope="col">Vehicle</th>
            <th scope="col" class="num-col">Price</th>
            <th scope="col" class="num-col">Mileage</th>
            <th scope="col" class="num-col">Score</th>
            <th scope="col" class="num-col">DOM</th>
          </tr>
        </thead>
        <tbody>
          ${scatterTableRows}
        </tbody>
      </table>
    </div>
  </details>
</div>

<div id="cohort-leaderboard" class="mt-5">
  <div class="mb-3">
    <h3 class="text-base font-bold text-primary">Watchlist Valuation Leaderboard (14 Target Models)</h3>
    <p class="control-hint">Empirical market distribution, p25 entry thresholds, and pricing velocity across all monitored EV lines.</p>
  </div>
  <div class="table-scroll">
    <table class="precision-table">
      <thead>
        <tr>
          <th scope="col">Model &amp; Cohort</th>
          <th scope="col" class="num-col">Count (n)</th>
          <th scope="col" class="num-col">p25 Buy-Zone</th>
          <th scope="col" class="num-col">Median (p50)</th>
          <th scope="col" class="num-col">p75</th>
          <th scope="col" class="num-col">Median $/1k mi</th>
          <th scope="col" class="num-col">Avg MSRP Off</th>
          <th scope="col" class="num-col">Avg DOM</th>
          <th scope="col" class="num-col">Price Cuts</th>
          <th scope="col" class="num-col">Top Score</th>
          <th scope="col">Actions</th>
        </tr>
      </thead>
      <tbody>
        ${leaderboardRows}
      </tbody>
    </table>
  </div>
</div>

<div id="momentum-feed" class="mt-5">
  <div class="momentum-grid grid grid-cols-1 lg:grid-cols-2 gap-4">
    <div class="momentum-panel">
      <h3 class="text-sm font-bold text-primary">Fresh Price-Cut Movers</h3>
      <p class="control-hint">Listings with steepest absolute reductions and active weekly markdown momentum.</p>
      <div class="flex flex-col gap-2 mt-2">
        ${cutMoversHtml}
      </div>
    </div>
    <div class="momentum-panel">
      <h3 class="text-sm font-bold text-primary">Stale High-Leverage Inventory (&ge; 30d)</h3>
      <p class="control-hint">Aging inventory with high dealer carrying friction and aggressive negotiation headroom.</p>
      <div class="flex flex-col gap-2 mt-2">
        ${staleInventoryHtml}
      </div>
    </div>
  </div>
</div>
  `.trim();
}

/**
 * Renders Workspace 3 (Dealer & Channel Arbitrage) showing platform spread,
 * distance band analysis, and dealer pricing matrix.
 *
 * Pre-conditions:
 *   - arbitrageData is an object with platforms, distance_bands, and dealers arrays.
 * Post-conditions:
 *   - Returns HTML containing #platform-comparison, #distance-bands, and #dealer-matrix.
 *   - All metrics formatted with tabular-nums.
 *
 * @param {object} arbitrageData - Data from GET /api/market/dealers.
 * @returns {string} Rendered HTML string.
 */
export function renderArbitrageWorkspaceHtml(arbitrageData = {}) {
  const data = arbitrageData || {};
  const platforms = data.platforms || [];
  const distanceBands = data.distance_bands || [];
  const dealers = data.dealers || [];

  // Platform comparison cards
  const platformCardsHtml = platforms.map((p) => {
    const platName = (p.platform || 'UNKNOWN').toUpperCase();
    const count = Number(p.listing_count) || 0;
    const medFmv = Number(p.median_pct_vs_fmv) || 0;
    const avgPrice = Number(p.avg_price) || 0;
    const avgDom = Number(p.avg_dom) || 0;
    const avgScore = Number(p.avg_deal_score) || 0;
    const cutPct = Number(p.price_cut_pct) || 0;

    return `
      <div class="platform-card">
        <div class="flex items-center justify-between">
          <span class="text-base font-bold text-primary">${escapeHtml(platName)}</span>
          <span class="scope-chip tabular-nums">${formatNumber(count)} listings</span>
        </div>
        <div class="grid grid-cols-2 gap-2 mt-2 text-xs">
          <div>
            <span class="control-hint">Median % vs FMV</span>
            <div class="font-bold text-primary tabular-nums">${medFmv >= 0 ? `+${medFmv.toFixed(1)}%` : `${medFmv.toFixed(1)}%`}</div>
          </div>
          <div>
            <span class="control-hint">Average Price</span>
            <div class="font-bold text-primary tabular-nums">${formatCurrency(avgPrice)}</div>
          </div>
          <div>
            <span class="control-hint">Average DOM</span>
            <div class="font-bold text-primary tabular-nums">${avgDom.toFixed(1)}d</div>
          </div>
          <div>
            <span class="control-hint">Avg Deal Score</span>
            <div class="font-bold text-primary tabular-nums">${avgScore.toFixed(1)}</div>
          </div>
        </div>
        <div class="control-hint mt-1 tabular-nums">Price-Cut Share: ${cutPct.toFixed(1)}% of listings</div>
      </div>
    `.trim();
  }).join('\n');

  // Analytical spread callout
  let spreadSummary = 'Insufficient cross-channel data to compute platform arbitrage.';
  const carscom = platforms.find((p) => String(p.platform).toUpperCase().includes('CARS'));
  const cargurus = platforms.find((p) => String(p.platform).toUpperCase().includes('GURUS'));
  if (carscom && cargurus) {
    const diffPct = ((Number(cargurus.median_pct_vs_fmv) || 0) - (Number(carscom.median_pct_vs_fmv) || 0)).toFixed(1);
    const diffDom = ((Number(cargurus.avg_dom) || 0) - (Number(carscom.avg_dom) || 0)).toFixed(1);
    spreadSummary = `CarGurus listings trade ${Math.abs(Number(diffPct))} percentage points ${Number(diffPct) < 0 ? 'deeper below' : 'higher than'} FMV with ${Math.abs(Number(diffDom))} days ${Number(diffDom) >= 0 ? 'higher' : 'lower'} average DOM than Cars.com.`;
  }

  // Distance band cards
  const distanceBandsHtml = distanceBands.map((band) => {
    const n = Number(band.listing_count) || 0;
    const medFmv = Number(band.median_pct_vs_fmv) || 0;
    const avgPrice = Number(band.avg_price) || 0;
    const avgScore = Number(band.avg_deal_score) || 0;
    const cutPct = Number(band.price_cut_pct) || 0;
    const barWidth = Math.min(100, Math.max(8, n * 8));

    return `
      <div class="band-card">
        <div class="flex items-center justify-between">
          <strong class="text-sm font-semibold text-primary">${escapeHtml(band.band)}</strong>
          <span class="tabular-nums font-mono text-xs">${formatNumber(n)} cars</span>
        </div>
        <div class="band-bar-track my-1">
          <div class="band-bar-fill" style="width: ${barWidth}%;"></div>
        </div>
        <div class="flex justify-between text-xs mt-1">
          <span class="control-hint">Median % vs FMV:</span>
          <span class="tabular-nums font-semibold">${medFmv >= 0 ? `+${medFmv.toFixed(1)}%` : `${medFmv.toFixed(1)}%`}</span>
        </div>
        <div class="flex justify-between text-xs">
          <span class="control-hint">Avg Price:</span>
          <span class="tabular-nums">${formatCurrency(avgPrice)}</span>
        </div>
        <div class="flex justify-between text-xs">
          <span class="control-hint">Avg Score:</span>
          <span class="tabular-nums">${avgScore.toFixed(1)}</span>
        </div>
        <div class="mt-2 pt-2 border-t border-subtle flex items-center justify-between">
          <span class="control-hint tabular-nums">Drops: ${cutPct.toFixed(0)}%</span>
          <button type="button" class="btn btn-ghost text-xs" data-action="filter-distance" data-max-distance="${escapeHtml(String(band.max_mi || 60))}">
            Filter &le; ${escapeHtml(String(band.max_mi || '60+'))} mi
          </button>
        </div>
      </div>
    `.trim();
  }).join('\n');

  // Dealer matrix precision table
  const dealerRowsHtml = dealers.map((dealer) => {
    const name = dealer.seller_name || 'Dealer';
    const city = dealer.location_city || 'Bay Area';
    const dist = dealer.distance_miles != null ? `${Number(dealer.distance_miles).toFixed(1)} mi` : 'N/A';
    const count = Number(dealer.listing_count) || 0;
    const medFmv = Number(dealer.median_pct_vs_fmv) || 0;
    const avgDelta = Number(dealer.avg_price_delta) || 0;
    const avgDom = Number(dealer.avg_dom) || 0;
    const avgScore = Number(dealer.avg_deal_score) || 0;
    const cutCount = Number(dealer.price_cut_count) || 0;
    const cutPct = Number(dealer.price_cut_pct) || 0;
    const bestDealId = dealer.best_deal_id || '';

    return `
      <tr>
        <td>
          <div class="font-semibold text-primary">${escapeHtml(name)}</div>
          <div class="control-hint">${escapeHtml(city)} &bull; <span class="tabular-nums">${escapeHtml(dist)}</span></div>
        </td>
        <td class="num-col tabular-nums font-bold">${formatNumber(count)}</td>
        <td class="num-col tabular-nums font-semibold">
          <span class="${medFmv <= 0 ? 'text-emerald-400' : 'text-amber-400'}">${medFmv >= 0 ? `+${medFmv.toFixed(1)}%` : `${medFmv.toFixed(1)}%`}</span>
        </td>
        <td class="num-col tabular-nums">${formatSignedCurrency(avgDelta)}</td>
        <td class="num-col tabular-nums">${avgDom.toFixed(1)}d</td>
        <td class="num-col tabular-nums font-semibold">${avgScore.toFixed(1)}</td>
        <td class="num-col tabular-nums">${formatNumber(cutCount)} (${cutPct.toFixed(0)}%)</td>
        <td>
          <div class="flex items-center gap-1">
            <button type="button" class="btn btn-secondary text-xs" data-action="analyze" data-listing-id="${escapeHtml(bestDealId)}"${!bestDealId ? ' disabled' : ''}>
              Inspect Best Deal
            </button>
            <button type="button" class="btn btn-ghost text-xs" data-action="filter-dealer" data-dealer="${escapeHtml(name)}">
              Filter
            </button>
          </div>
        </td>
      </tr>
    `.trim();
  }).join('\n');

  return `
<div id="platform-comparison" class="frontier-panel">
  <div class="mb-3">
    <h3 class="text-base font-bold text-primary">Channel Arbitrage: Cars.com vs CarGurus</h3>
    <p class="control-hint">Empirical spread between listing marketplaces across active Bay Area inventory.</p>
  </div>
  <div class="platform-grid grid grid-cols-1 md:grid-cols-2 gap-4">
    ${platformCardsHtml}
  </div>
  <div class="arbitrage-callout mt-4">
    <strong>Analytical Takeaway:</strong> ${escapeHtml(spreadSummary)}
  </div>
</div>

<div id="distance-bands" class="frontier-panel mt-5">
  <div class="mb-3">
    <h3 class="text-base font-bold text-primary">Geographic Distance-Band Pricing</h3>
    <p class="control-hint">Surveillance radial bands measured outward from San Francisco (ZIP 94103).</p>
  </div>
  <div class="distance-bands-grid">
    ${distanceBandsHtml}
  </div>
</div>

<div id="dealer-matrix" class="frontier-panel mt-5">
  <div class="mb-3">
    <h3 class="text-base font-bold text-primary">Bay Area Dealership Pricing Spread Matrix</h3>
    <p class="control-hint">Dealer pricing efficiency, aging lot inventory, and negotiation discount share.</p>
  </div>
  <div class="table-scroll">
    <table class="precision-table">
      <thead>
        <tr>
          <th scope="col">Dealer &amp; Location</th>
          <th scope="col" class="num-col">Listings</th>
          <th scope="col" class="num-col">Median % vs FMV</th>
          <th scope="col" class="num-col">Avg Delta</th>
          <th scope="col" class="num-col">Avg DOM</th>
          <th scope="col" class="num-col">Avg Score</th>
          <th scope="col" class="num-col">Price Drops</th>
          <th scope="col">Actions</th>
        </tr>
      </thead>
      <tbody>
        ${dealerRowsHtml}
      </tbody>
    </table>
  </div>
</div>
  `.trim();
}

/**
 * Renders Workspace 4 (Side-by-Side Comparator) comparing up to 3 pinned vehicles
 * across 10 normalized dimensions with Best-in-Row highlight badges.
 *
 * Pre-conditions:
 *   - compareData is an object with deals and highlights.
 *   - pinnedIds is an array or Set of pinned listing IDs.
 * Post-conditions:
 *   - When pinnedIds is empty, renders empty state with "Browse Deal Workbench" CTA.
 *   - When pinned, renders 3-slot matrix with winner highlight badges and Unpin actions.
 *
 * @param {object} compareData - Data from GET /api/compare.
 * @param {Array|Set<string>} [pinnedIds] - Pinned listing IDs.
 * @returns {string} Rendered comparator HTML.
 */
export function renderComparatorWorkspaceHtml(compareData = {}, pinnedIds = []) {
  const cd = compareData || {};
  const deals = cd.deals || cd.items || [];
  const highlights = cd.highlights || {};
  const pinnedList = Array.isArray(pinnedIds) ? pinnedIds : Array.from(pinnedIds || []);

  if (!pinnedList || pinnedList.length === 0 || deals.length === 0) {
    return `
<div class="empty-state">
  <svg class="empty-state__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
    <rect x="3" y="3" width="7" height="18" rx="1"></rect>
    <rect x="14" y="3" width="7" height="18" rx="1"></rect>
  </svg>
  <h3 class="empty-state__title">No Vehicles Pinned for Comparison</h3>
  <p class="empty-state__text">Pin up to 3 EVs from the Deal Workbench to compare 3-year TCO, negotiation leverage, cohort percentiles, and safety posture side-by-side.</p>
  <button type="button" class="btn btn-primary" data-action="switch-workspace" data-workspace="workbench">Browse Deal Workbench</button>
</div>
    `.trim();
  }

  // 3-slot columns
  const slots = [0, 1, 2].map((idx) => deals[idx] || null);

  function renderSlotHeader(deal, idx) {
    if (!deal) {
      return `
        <td class="compare-slot-header">
          <div class="compare-slot-empty">
            <span class="block font-semibold">Slot ${idx + 1} Open</span>
            <span class="block text-2xs mt-1">Add another vehicle from Workbench</span>
            <button type="button" class="btn btn-secondary text-xs mt-3" data-action="switch-workspace" data-workspace="workbench">Browse Deals</button>
          </div>
        </td>
      `.trim();
    }

    const lid = String(deal.id || deal.platform_id || deal.vin || '');
    const title = deal.title || `${deal.year || ''} ${deal.make || ''} ${deal.model || ''}`.trim();
    const price = Number(deal.price) || 0;
    const score = Number(deal.deal_score) || 0;
    const vin = deal.vin || '';
    const platform = (deal.platform || 'Cars.com').toUpperCase();

    return `
      <td class="compare-slot-header">
        <div class="flex flex-col gap-2 p-3 bg-surface border border-default rounded-lg">
          <div class="flex items-center justify-between">
            <span class="scope-chip">${escapeHtml(platform)}</span>
            <button type="button" class="btn btn-ghost text-xs" data-action="unpin" data-listing-id="${escapeHtml(lid)}" aria-label="Remove ${escapeHtml(title)} from comparison">Unpin</button>
          </div>
          <h4 class="font-bold text-sm text-primary line-clamp-1">${escapeHtml(title)}</h4>
          <div class="flex items-baseline justify-between">
            <span class="text-xl font-bold text-primary tabular-nums">${formatCurrency(price)}</span>
            <span class="score-pill score-pill--${score >= 85 ? 'excellent' : 'info'} tabular-nums">${score.toFixed(1)}</span>
          </div>
          <button type="button" class="vin-chip tabular-nums" data-action="copy-vin" data-vin="${escapeHtml(vin)}" title="Copy VIN">
            ${escapeHtml(vin || 'NO VIN')}
          </button>
        </div>
      </td>
    `.trim();
  }

  function renderDimensionRow(label, getValueAndWinnerFn) {
    const cellsHtml = slots.map((d) => {
      if (!d) return '<td class="text-muted text-center">--</td>';
      const { text, isWinner } = getValueAndWinnerFn(d);
      const winnerClass = isWinner ? ' compare-cell--winner font-semibold' : '';
      const winnerPill = isWinner ? '<span class="compare-winner-pill">Best</span>' : '';
      return `<td class="${winnerClass} tabular-nums">${text} ${winnerPill}</td>`;
    }).join('\n');

    return `
      <tr>
        <th scope="row" class="text-left font-medium text-secondary">${escapeHtml(label)}</th>
        ${cellsHtml}
      </tr>
    `.trim();
  }

  const dimensionRows = [
    renderDimensionRow('Price', (d) => {
      const price = Number(d.price) || 0;
      const minPrice = Math.min(...deals.map((x) => Number(x.price) || Infinity));
      const isWinner = price === minPrice && Number.isFinite(minPrice);
      return {
        text: formatCurrency(price),
        isWinner,
      };
    }),
    renderDimensionRow('vs FMV', (d) => {
      const lid = String(d.id || d.platform_id || d.vin || '');
      const delta = Number(d.price_delta) || 0;
      const pct = Number(d.pct_savings) || 0;
      const isWinner = highlights.lowest_vs_fmv_id === lid;
      return {
        text: `${formatSignedCurrency(delta)} (${pct.toFixed(1)}%) &bull; FMV ${formatCurrency(d.market_value)}`,
        isWinner,
      };
    }),
    renderDimensionRow('Deal Score', (d) => {
      const lid = String(d.id || d.platform_id || d.vin || '');
      const score = Number(d.deal_score) || 0;
      const isWinner = highlights.highest_score_id === lid;
      return {
        text: `${score.toFixed(1)} / 100`,
        isWinner,
      };
    }),
    renderDimensionRow('Mileage', (d) => {
      const mileage = Number(d.mileage) || 0;
      const minMil = Math.min(...deals.map((x) => Number(x.mileage) || Infinity));
      const isWinner = mileage === minMil && Number.isFinite(minMil);
      return {
        text: `${formatNumber(mileage)} mi`,
        isWinner,
      };
    }),
    renderDimensionRow('Price / 1k mi', (d) => {
      const mileage = Number(d.mileage) || 0;
      const price = Number(d.price) || 0;
      const per1k = d.price_per_1k_miles != null ? Number(d.price_per_1k_miles) : (price / Math.max(1, mileage / 1000));
      const minPer1k = Math.min(...deals.map((x) => {
        const m = Number(x.mileage) || 0;
        const p = Number(x.price) || 0;
        return x.price_per_1k_miles != null ? Number(x.price_per_1k_miles) : (p / Math.max(1, m / 1000));
      }));
      const isWinner = Math.abs(per1k - minPer1k) < 0.05;
      return {
        text: `$${per1k.toFixed(1)}`,
        isWinner,
      };
    }),
    renderDimensionRow('DOM', (d) => {
      const lid = String(d.id || d.platform_id || d.vin || '');
      const dom = Number(d.days_on_market) || 0;
      const drop = Number(d.price_drop_total) || 0;
      const isWinner = highlights.highest_dom_id === lid;
      return {
        text: `${dom}d on lot &bull; Drops: -${formatCurrency(drop)}`,
        isWinner,
      };
    }),
    renderDimensionRow('Negotiation Leverage', (d) => {
      const lid = String(d.id || d.platform_id || d.vin || '');
      const lev = Number(d.negotiation_leverage_score) || 0;
      const tier = d.leverage_tier || (lev >= 70 ? 'HIGH' : lev >= 45 ? 'MODERATE' : 'LOW');
      const isWinner = highlights.highest_leverage_id === lid;
      return {
        text: `Score ${lev.toFixed(0)} (${escapeHtml(tier)})`,
        isWinner,
      };
    }),
    renderDimensionRow('3-Yr TCO Delta', (d) => {
      const lid = String(d.id || d.platform_id || d.vin || '');
      const tco = Number(d.total_3yr_ownership_delta) || (Number(d.analytics?.total_3yr_ownership_delta) || 0);
      const isWinner = highlights.lowest_3yr_tco_id === lid;
      return {
        text: formatCurrency(tco),
        isWinner,
      };
    }),
    renderDimensionRow('EV Credit', (d) => {
      const lid = String(d.id || d.platform_id || d.vin || '');
      const eligible = Boolean(d.used_ev_tax_credit?.eligible || d.analytics?.used_ev_tax_credit?.eligible);
      const isWinner = Array.isArray(highlights.tax_credit_ids) && highlights.tax_credit_ids.includes(lid);
      return {
        text: eligible ? 'Eligible (-$4,000)' : 'Not Eligible',
        isWinner,
      };
    }),
    renderDimensionRow('Safety Posture', (d) => {
      const lid = String(d.id || d.platform_id || d.vin || '');
      const posture = d.safety_posture || d.analytics?.safety_posture || 'LOW';
      const cleanTitle = (d.title_status || 'CLEAN').toUpperCase() === 'CLEAN';
      const isWinner = Array.isArray(highlights.lowest_risk_ids) && highlights.lowest_risk_ids.includes(lid);
      return {
        text: `${escapeHtml(posture)} &bull; ${cleanTitle ? 'Clean Title' : 'Branded Title'}`,
        isWinner,
      };
    }),
  ];

  // Actions footer row
  const footerRowHtml = slots.map((d) => {
    if (!d) return '<td></td>';
    const lid = String(d.id || d.platform_id || d.vin || '');
    const isBookmarked = Boolean(d.is_bookmarked || d.raw_data?.user_bookmarked);
    return `
      <td>
        <div class="flex flex-col gap-2 pt-2">
          <button type="button" class="btn btn-primary text-xs" data-action="analyze" data-listing-id="${escapeHtml(lid)}">Analyze</button>
          <button type="button" class="btn btn-ghost text-xs" data-action="bookmark" data-listing-id="${escapeHtml(lid)}" aria-pressed="${isBookmarked}">
            ${isBookmarked ? 'Saved' : 'Save'}
          </button>
          <a href="${escapeHtml(d.url || '#')}" target="_blank" rel="noopener noreferrer" class="btn btn-ghost text-xs">Open Listing &nearr;</a>
        </div>
      </td>
    `.trim();
  }).join('\n');

  return `
<div class="compare-toolbar">
  <div>
    <h3 class="text-base font-bold text-primary">Side-by-Side EV Comparator (${formatNumber(deals.length)} / 3 Pinned)</h3>
    <p class="control-hint">Normalized cross-model evaluation across TCO, depreciation, negotiation leverage, and safety posture.</p>
  </div>
  <div class="flex items-center gap-2">
    <button type="button" class="btn btn-secondary text-xs" data-action="copy-compare-markdown">Copy Markdown Summary</button>
    <button type="button" class="btn btn-ghost text-xs" data-action="clear-pins">Clear All Pins</button>
  </div>
</div>

<div class="compare-matrix-wrap mt-4">
  <table class="compare-table">
    <thead>
      <tr>
        <th scope="col" class="w-1/4 text-left">Dimension</th>
        ${slots.map((s, idx) => renderSlotHeader(s, idx)).join('\n')}
      </tr>
    </thead>
    <tbody>
      ${dimensionRows.join('\n')}
      <tr>
        <th scope="row" class="text-left font-medium text-secondary">Actions</th>
        ${footerRowHtml}
      </tr>
    </tbody>
  </table>
</div>
  `.trim();
}

/**
 * Renders the complete 7-section valuation and negotiation dossier inside #analysis-drawer.
 *
 * Pre-conditions:
 *   - analysisData is an object returned from GET /api/listings/{id}/analysis.
 *   - pinnedIds is a Set or Array of currently pinned listing IDs.
 * Post-conditions:
 *   - Returns complete HTML adhering to all 7 required valuation sections.
 *   - Header includes platform pill, VIN chip, title, pricing, deal score, controls, and close button.
 *
 * @param {object} analysisData - Listing analysis data payload.
 * @param {Set|Array<string>} [pinnedIds] - Pinned listing IDs.
 * @returns {string} Rendered drawer inner HTML.
 */
export function renderAnalysisDrawerHtml(analysisData = {}, pinnedIds = new Set()) {
  const data = analysisData || {};
  const deal = data.deal || {};
  const cohort = data.cohort || {};
  const snapshots = data.snapshots || [];
  const dep = data.depreciation_3yr || {};
  const lev = data.leverage || {};
  const taxCredit = data.tax_credit || deal.used_ev_tax_credit || {};
  const safety = data.safety_posture || 'LOW';
  const epa = data.epa || {};
  const profile = data.model_profile || {};
  const pinnedSet = pinnedIds instanceof Set ? pinnedIds : new Set(pinnedIds || []);

  const lid = String(deal.id || deal.platform_id || deal.vin || '');
  const isPinned = pinnedSet.has(lid);
  const isBookmarked = Boolean(deal.is_bookmarked || deal.raw_data?.user_bookmarked);
  const isDismissed = Boolean(deal.is_dismissed || deal.raw_data?.user_dismissed);
  const title = deal.title || `${deal.year || ''} ${deal.make || ''} ${deal.model || ''}`.trim();
  const price = Number(deal.price) || 0;
  const fmv = Number(deal.market_value) || 0;
  const delta = Number(deal.price_delta) || (price - fmv);
  const pct = Number(deal.pct_savings) || 0;
  const score = Number(deal.deal_score) || 0;
  const vin = deal.vin || '';
  const platform = (deal.platform || 'Cars.com').toUpperCase();
  const seller = deal.seller_name || 'Dealer';
  const city = deal.location_city || 'Bay Area';
  const dist = deal.distance_miles != null ? `${Number(deal.distance_miles).toFixed(1)} mi` : 'Bay Area';

  const deltaClass = delta <= 0 ? 'deal-card__delta--neg' : 'deal-card__delta--pos';
  const deltaText = `${formatSignedCurrency(delta)} (${pct.toFixed(1)}%) vs FMV`;

  // 1. Sticky Header Controls
  const headerHtml = `
    <div class="drawer-header sticky top-0 bg-elevated z-10 border-b border-default p-4">
      <div class="flex items-start justify-between gap-3 w-full">
        <div class="min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <span class="scope-chip">${escapeHtml(platform)}</span>
            <button type="button" class="vin-chip tabular-nums" data-action="copy-vin" data-vin="${escapeHtml(vin)}" title="Copy VIN">
              ${escapeHtml(vin || 'NO VIN')}
            </button>
            <span class="control-hint">${escapeHtml(dist)} &bull; ${escapeHtml(city)} &bull; ${escapeHtml(seller)}</span>
          </div>
          <h2 id="drawer-title" class="drawer-title truncate">${escapeHtml(title)}</h2>
          <div class="flex items-baseline gap-3 mt-1">
            <span class="text-2xl font-bold text-primary tabular-nums">${formatCurrency(price)}</span>
            <span class="text-sm text-muted tabular-nums">FMV ${formatCurrency(fmv)}</span>
            <span class="deal-card__delta ${deltaClass} tabular-nums">${escapeHtml(deltaText)}</span>
            <span class="score-pill score-pill--${score >= 85 ? 'excellent' : 'info'} tabular-nums">${score.toFixed(1)}</span>
          </div>
        </div>
        <div class="flex items-center gap-1.5 flex-shrink-0">
          <button type="button" class="btn btn-secondary text-xs" data-action="pin" data-listing-id="${escapeHtml(lid)}" aria-pressed="${isPinned}">
            ${isPinned ? 'Pinned' : 'Compare'}
          </button>
          <button type="button" class="btn btn-ghost text-xs" data-action="bookmark" data-listing-id="${escapeHtml(lid)}" aria-pressed="${isBookmarked}">
            ${isBookmarked ? 'Saved' : 'Save'}
          </button>
          <button type="button" class="btn btn-ghost text-xs" data-action="dismiss" data-listing-id="${escapeHtml(lid)}">
            ${isDismissed ? 'Restore' : 'Hide'}
          </button>
          <a href="${escapeHtml(deal.url || '#')}" target="_blank" rel="noopener noreferrer" class="btn btn-ghost text-xs" aria-label="Open external listing on ${escapeHtml(platform)}">Open &nearr;</a>
          <button type="button" id="drawer-close-btn" class="btn btn-ghost btn-icon" data-action="close-drawer" aria-label="Close valuation drawer">&times;</button>
        </div>
      </div>
    </div>
  `.trim();

  // 2. Cohort Valuation
  const cohortPctl = cohort.cohort_percentile != null ? Math.round(Number(cohort.cohort_percentile)) : (deal.cohort_percentile != null ? Math.round(Number(deal.cohort_percentile)) : 'N/A');
  const zScore = cohort.cohort_z_score != null ? Number(cohort.cohort_z_score).toFixed(2) : (deal.cohort_z_score != null ? Number(deal.cohort_z_score).toFixed(2) : '0.00');
  const per1k = deal.price_per_1k_miles != null ? Number(deal.price_per_1k_miles).toFixed(1) : (Number(deal.price) / Math.max(1, (Number(deal.mileage) || 0) / 1000)).toFixed(1);
  const estMsrp = dep.estimated_msrp || deal.estimated_msrp || 0;
  const msrpOff = Number(deal.msrp_discount_pct) || 0;

  const section2Html = `
    <section class="drawer-section p-4 border-b border-default">
      <div class="flex items-center justify-between mb-2">
        <h3 class="text-sm font-bold text-primary">Cohort Valuation &amp; Empirical Percentile</h3>
        <span class="scope-chip">n=${formatNumber(cohort.sample_size || 0)} &bull; ${escapeHtml(cohort.confidence_tier || 'LOW')} Confidence</span>
      </div>
      ${renderCohortRangeBarHtml(deal)}
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3 text-xs">
        <div class="p-2 bg-inset rounded border border-subtle">
          <span class="control-hint">Cohort Percentile</span>
          <div class="font-bold text-primary tabular-nums">p${cohortPctl}</div>
        </div>
        <div class="p-2 bg-inset rounded border border-subtle">
          <span class="control-hint">Z-Score</span>
          <div class="font-bold text-primary tabular-nums">${zScore} &sigma;</div>
        </div>
        <div class="p-2 bg-inset rounded border border-subtle">
          <span class="control-hint">$/1k Miles</span>
          <div class="font-bold text-primary tabular-nums">$${per1k}</div>
        </div>
        <div class="p-2 bg-inset rounded border border-subtle">
          <span class="control-hint">Est. MSRP Off</span>
          <div class="font-bold text-primary tabular-nums">${msrpOff.toFixed(1)}% (${formatCurrency(estMsrp)})</div>
        </div>
      </div>
    </section>
  `.trim();

  // 3. TimescaleDB Price History
  const sparklineHtml = renderPriceSparkline(snapshots);
  const dropTotal = lev.price_drop_total != null ? Number(lev.price_drop_total) : (deal.price_drop_total || 0);
  const dropPct = lev.price_drop_pct != null ? Number(lev.price_drop_pct) : 0;
  const dropCount = lev.price_drop_count != null ? Number(lev.price_drop_count) : 0;
  const vel = lev.price_velocity_per_week != null ? Number(lev.price_velocity_per_week) : 0;

  const snapshotRows = snapshots.slice(-5).reverse().map((snap) => `
    <tr>
      <td class="tabular-nums font-mono text-2xs">${escapeHtml(snap.time ? String(snap.time).slice(0, 10) : 'Snapshot')}</td>
      <td class="num-col tabular-nums font-semibold">${formatCurrency(snap.price)}</td>
      <td class="num-col tabular-nums">${snap.price_change != null ? formatSignedCurrency(snap.price_change) : '$0'}</td>
      <td class="num-col tabular-nums">${snap.days_on_market != null ? snap.days_on_market : '1'}d</td>
    </tr>
  `).join('\n');

  const section3Html = `
    <section class="drawer-section p-4 border-b border-default">
      <div class="flex items-center justify-between mb-2">
        <h3 class="text-sm font-bold text-primary">TimescaleDB Price History &amp; Surveillance Ledger</h3>
        <span class="control-hint tabular-nums">Snapshots: ${snapshots.length}</span>
      </div>
      <div class="grid grid-cols-4 gap-2 mb-3 text-xs">
        <div>
          <span class="control-hint">Initial Price</span>
          <div class="font-bold tabular-nums">${formatCurrency(lev.initial_price || price)}</div>
        </div>
        <div>
          <span class="control-hint">Total Markdown</span>
          <div class="font-bold tabular-nums text-emerald-400">-${formatCurrency(dropTotal)} (-${dropPct.toFixed(1)}%)</div>
        </div>
        <div>
          <span class="control-hint">Price Cuts</span>
          <div class="font-bold tabular-nums">${dropCount}</div>
        </div>
        <div>
          <span class="control-hint">Weekly Velocity</span>
          <div class="font-bold tabular-nums">-$${vel.toFixed(0)}/wk</div>
        </div>
      </div>
      <div class="my-2">
        ${sparklineHtml}
      </div>
      ${snapshots.length <= 1 ? '<p class="control-hint text-2xs mt-1">1 snapshot recorded so far; multi-day price velocity will appear after subsequent daily runs.</p>' : ''}
      <div class="table-scroll mt-2">
        <table class="precision-table text-2xs">
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col" class="num-col">Price</th>
              <th scope="col" class="num-col">Change</th>
              <th scope="col" class="num-col">DOM</th>
            </tr>
          </thead>
          <tbody>
            ${snapshotRows}
          </tbody>
        </table>
      </div>
    </section>
  `.trim();

  // 4. 4-Factor Deal Breakdown
  const bd = deal.score_breakdown || {};
  const pScore = Math.round(Number(bd.price_score) || 75);
  const hScore = Math.round(Number(bd.history_score) || 80);
  const lScore = Math.round(Number(bd.leverage_score) || 70);
  const xScore = Math.round(Number(bd.proximity_score) || 85);

  const section4Html = `
    <section class="drawer-section p-4 border-b border-default">
      <h3 class="text-sm font-bold text-primary mb-2">4-Factor Deal Score Breakdown</h3>
      <div class="space-y-2 text-xs">
        <div>
          <div class="flex justify-between">
            <span>Price vs Fair Market Value (50% weight)</span>
            <strong class="tabular-nums">${pScore} / 100</strong>
          </div>
          <div class="factor-bar mt-1"><div class="factor-bar__fill factor-bar__fill--excellent" style="width: ${pScore}%;"></div></div>
        </div>
        <div>
          <div class="flex justify-between">
            <span>Title &amp; Vehicle History (25% weight)</span>
            <strong class="tabular-nums">${hScore} / 100</strong>
          </div>
          <div class="factor-bar mt-1"><div class="factor-bar__fill factor-bar__fill--info" style="width: ${hScore}%;"></div></div>
        </div>
        <div>
          <div class="flex justify-between">
            <span>Days on Market Leverage (15% weight)</span>
            <strong class="tabular-nums">${lScore} / 100</strong>
          </div>
          <div class="factor-bar mt-1"><div class="factor-bar__fill factor-bar__fill--cut" style="width: ${lScore}%;"></div></div>
        </div>
        <div>
          <div class="flex justify-between">
            <span>Bay Area Proximity (10% weight)</span>
            <strong class="tabular-nums">${xScore} / 100</strong>
          </div>
          <div class="factor-bar mt-1"><div class="factor-bar__fill factor-bar__fill--telemetry" style="width: ${xScore}%;"></div></div>
        </div>
      </div>
    </section>
  `.trim();

  // 5. Negotiation Leverage & Offer Strategy
  const levScore = Number(lev.negotiation_leverage_score) || 0;
  const levTier = lev.leverage_tier || (levScore >= 70 ? 'HIGH' : levScore >= 45 ? 'MODERATE' : 'LOW');
  const offerLow = Number(lev.suggested_offer_low) || Math.round(price * 0.92);
  const offerTarget = Number(lev.suggested_offer_target) || Math.round(price * 0.96);
  const levBd = lev.leverage_breakdown || {};

  const section5Html = `
    <section class="drawer-section p-4 border-b border-default">
      <div class="flex items-center justify-between mb-2">
        <h3 class="text-sm font-bold text-primary">Negotiation Leverage &amp; Offer Strategy</h3>
        <span class="score-pill score-pill--${levScore >= 70 ? 'excellent' : 'info'} tabular-nums">Leverage ${levScore.toFixed(0)} (${escapeHtml(levTier)})</span>
      </div>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs mb-3">
        <div class="p-2 bg-inset rounded">
          <span class="control-hint">Stale DOM</span>
          <div class="font-bold tabular-nums">${Number(levBd.dom_component || 0).toFixed(1)} / 40</div>
        </div>
        <div class="p-2 bg-inset rounded">
          <span class="control-hint">Price Velocity</span>
          <div class="font-bold tabular-nums">${Number(levBd.velocity_component || 0).toFixed(1)} / 25</div>
        </div>
        <div class="p-2 bg-inset rounded">
          <span class="control-hint">p25 Headroom</span>
          <div class="font-bold tabular-nums">${Number(levBd.headroom_component || 0).toFixed(1)} / 20</div>
        </div>
        <div class="p-2 bg-inset rounded">
          <span class="control-hint">Friction</span>
          <div class="font-bold tabular-nums">${Number(levBd.friction_component || 0).toFixed(1)} / 15</div>
        </div>
      </div>
      <div class="arbitrage-callout">
        <div class="font-semibold text-primary mb-1">Recommended Offer Strategy</div>
        <div class="flex items-center gap-4 text-xs">
          <div>
            <span class="control-hint">Opening Offer:</span>
            <strong class="text-sm font-bold tabular-nums text-emerald-400">${formatCurrency(offerLow)}</strong>
          </div>
          <div>
            <span class="control-hint">Target Close:</span>
            <strong class="text-sm font-bold tabular-nums text-primary">${formatCurrency(offerTarget)}</strong>
          </div>
        </div>
      </div>
    </section>
  `.trim();

  // 6. 3-Year Depreciation, TCO & EV Tax Credit
  const res3yr = Number(dep.projected_3yr_residual) || 0;
  const dep3yr = Number(dep.projected_3yr_depreciation) || 0;
  const fuel3yr = Number(dep.energy_cost_3yr) || 0;
  const creditOffset = Number(taxCredit.potential_credit_usd) || 0;
  const net3yr = Number(dep.total_3yr_ownership_delta) || (dep3yr + fuel3yr - creditOffset);
  const isEligible = Boolean(taxCredit.eligible);
  const tcReasons = taxCredit.reasons || {};

  const section6Html = `
    <section class="drawer-section p-4 border-b border-default">
      <h3 class="text-sm font-bold text-primary mb-2">3-Year Depreciation, TCO &amp; Used EV Tax Credit</h3>
      <div class="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs mb-3">
        <div class="p-2 bg-inset rounded">
          <span class="control-hint">Purchase Price</span>
          <div class="font-bold tabular-nums">${formatCurrency(price)}</div>
        </div>
        <div class="p-2 bg-inset rounded">
          <span class="control-hint">3-Yr Projected Residual</span>
          <div class="font-bold tabular-nums">${formatCurrency(res3yr)}</div>
        </div>
        <div class="p-2 bg-inset rounded">
          <span class="control-hint">3-Yr Depreciation</span>
          <div class="font-bold tabular-nums text-amber-400">-${formatCurrency(dep3yr)}</div>
        </div>
        <div class="p-2 bg-inset rounded">
          <span class="control-hint">3-Yr Energy Cost</span>
          <div class="font-bold tabular-nums">${formatCurrency(fuel3yr)}</div>
        </div>
        <div class="p-2 bg-inset rounded">
          <span class="control-hint">EV Tax Credit</span>
          <div class="font-bold tabular-nums text-emerald-400">-${formatCurrency(creditOffset)}</div>
        </div>
        <div class="p-2 bg-inset rounded">
          <span class="control-hint">Net 3-Yr TCO Delta</span>
          <div class="font-bold tabular-nums text-primary">${formatCurrency(net3yr)}</div>
        </div>
      </div>

      <div class="tax-credit-card">
        <div class="flex items-center justify-between mb-2">
          <strong class="text-xs font-semibold">Used Clean Vehicle Credit ($4,000)</strong>
          <span class="market-badge market-badge--${isEligible ? 'excellent' : 'warn'}">
            ${isEligible ? 'Eligible ($4,000 Potential Credit)' : 'Not Eligible'}
          </span>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 text-2xs mb-2">
          <div class="flex items-center gap-1">
            <span class="${tcReasons.price_under_25k !== false && price <= 25000 ? 'text-emerald-400' : 'text-muted'}">&bull;</span>
            <span>Price &le; $25,000</span>
          </div>
          <div class="flex items-center gap-1">
            <span class="${tcReasons.model_year_2plus_years_old !== false ? 'text-emerald-400' : 'text-muted'}">&bull;</span>
            <span>Model Year &ge; 2 yrs old</span>
          </div>
          <div class="flex items-center gap-1">
            <span class="${tcReasons.clean_title !== false ? 'text-emerald-400' : 'text-muted'}">&bull;</span>
            <span>Clean Title</span>
          </div>
        </div>
        <p class="control-hint text-2xs">Informational estimate only; IRS buyer AGI limits, dealer point-of-sale registration, and first-resale rules apply.</p>
      </div>
    </section>
  `.trim();

  // 7. NHTSA Safety & EPA Telemetry
  const safetyClass = safety === 'LOW' ? 'safety-badge--low' : safety === 'MODERATE' ? 'safety-badge--moderate' : 'safety-badge--elevated';
  const range = epa.ev_range_miles || epa.range_miles || 'N/A';
  const mpge = epa.comb_mpge || epa.combined_mpge || 'N/A';
  const fuelCost = Number(epa.annual_fuel_cost) || 0;
  const recalls = profile.recalls || deal.recalls || [];
  const complaints = profile.complaints || [];

  const recallsListHtml = recalls.length === 0
    ? '<div class="control-hint text-2xs">0 open safety recall campaigns recorded.</div>'
    : recalls.slice(0, 3).map((r) => `
        <div class="recall-card text-2xs mt-1">
          <strong class="tabular-nums">${escapeHtml(r.NHTSACampaignNumber || r.campaign_number || 'Recall')}</strong>:
          ${escapeHtml(r.Component || r.component || 'Component')}&mdash;${escapeHtml(r.Summary || r.summary || 'Summary')}
        </div>
      `).join('\n');

  const section7Html = `
    <section class="drawer-section p-4">
      <div class="flex items-center justify-between mb-2">
        <h3 class="text-sm font-bold text-primary">NHTSA Safety Posture &amp; EPA Telemetry</h3>
        <span class="safety-badge ${safetyClass}">Safety: ${escapeHtml(safety)}</span>
      </div>
      <div class="grid grid-cols-3 gap-2 text-xs mb-3">
        <div class="p-2 bg-inset rounded">
          <span class="control-hint">EV Range</span>
          <div class="font-bold tabular-nums">${escapeHtml(String(range))} mi</div>
        </div>
        <div class="p-2 bg-inset rounded">
          <span class="control-hint">Combined MPGe</span>
          <div class="font-bold tabular-nums">${escapeHtml(String(mpge))} MPGe</div>
        </div>
        <div class="p-2 bg-inset rounded">
          <span class="control-hint">Annual Fuel</span>
          <div class="font-bold tabular-nums">${formatCurrency(fuelCost)}/yr</div>
        </div>
      </div>
      <div>
        <h4 class="text-xs font-semibold text-primary mb-1">NHTSA Safety Recalls &amp; VOQ Complaints</h4>
        ${recallsListHtml}
        <div class="control-hint text-2xs mt-2">
          Complaints: <strong class="tabular-nums">${complaints.length}</strong> | Crash: <strong class="tabular-nums">${Number(profile.crash_count || 0)}</strong> | Fire: <strong class="tabular-nums">${Number(profile.fire_count || 0)}</strong>
        </div>
      </div>
    </section>
  `.trim();

  return `
<div class="drawer-inner flex flex-col h-full bg-elevated text-primary" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
  ${headerHtml}
  <div class="drawer-body flex-1 overflow-y-auto">
    ${section2Html}
    ${section3Html}
    ${section4Html}
    ${section5Html}
    ${section6Html}
    ${section7Html}
  </div>
</div>
  `.trim();
}

/**
 * Renders the floating Compare Tray fixed to the bottom of the viewport.
 *
 * Pre-conditions:
 *   - dealsById is a map or object containing listing objects by ID.
 *   - pinnedIds is an array or Set of pinned listing IDs.
 * Post-conditions:
 *   - When pinnedIds is empty, returns empty string.
 *   - When pinnedIds has 1..3 IDs, returns HTML matching .compare-tray specification.
 *
 * @param {object} dealsById - Lookup of deals by identifier.
 * @param {Array|Set<string>} [pinnedIds] - Pinned listing IDs.
 * @returns {string} Rendered tray HTML.
 */
export function renderCompareTrayHtml(dealsById = {}, pinnedIds = []) {
  const map = dealsById || {};
  const pinned = Array.isArray(pinnedIds) ? pinnedIds : Array.from(pinnedIds || []);

  if (pinned.length === 0) {
    return '';
  }

  const slotsHtml = [0, 1, 2].map((idx) => {
    const id = pinned[idx];
    if (!id) {
      return `
        <div class="compare-slot compare-slot--empty">
          <span>Slot ${idx + 1} Open</span>
        </div>
      `.trim();
    }

    const d = map[id] || {};
    const title = d.title || `${d.year || ''} ${d.make || ''} ${d.model || ''}`.trim() || 'Vehicle';
    const price = Number(d.price) || 0;

    return `
      <div class="compare-slot compare-slot--filled">
        <div class="truncate">
          <strong class="text-xs text-primary truncate">${escapeHtml(title)}</strong>
          <span class="control-hint tabular-nums">${formatCurrency(price)}</span>
        </div>
        <button type="button" class="btn btn-ghost btn-icon" data-action="unpin" data-listing-id="${escapeHtml(id)}" aria-label="Remove ${escapeHtml(title)} from comparison">&times;</button>
      </div>
    `.trim();
  }).join('\n');

  return `
<div class="compare-tray__inner">
  <div class="compare-slots">
    ${slotsHtml}
  </div>
  <div class="compare-tray__actions">
    <button type="button" class="btn btn-ghost text-xs" data-action="clear-pins">Clear All</button>
    <button type="button" class="btn btn-primary text-xs" data-action="switch-workspace" data-workspace="compare">
      Compare Now (${pinned.length}/3)
    </button>
  </div>
</div>
  `.trim();
}

/**
 * Renders the Degraded / Offline Fallback Banner (#degraded-banner).
 *
 * Pre-conditions:
 *   - provenance is an object with mode or execution details.
 * Post-conditions:
 *   - Returns HTML matching #degraded-banner structure with Retry and Acknowledge actions.
 *
 * @param {object} provenance - Execution provenance dictionary.
 * @returns {string} Rendered banner HTML.
 */
export function renderDegradedBannerHtml(provenance = {}) {
  const p = provenance || {};
  const mode = p.mode || 'offline-sample';
  const tagLabel = mode === 'offline-sample' ? 'Offline Sample Data' : 'Degraded Mode';
  const message = p.message || 'PostgreSQL/TimescaleDB unreachable; displaying 24 representative Bay Area EV sample listings. All analytical math, charts, and comparator workflows remain operational.';

  return `
<div class="degraded-banner__content">
  <svg class="degraded-banner__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
    <line x1="12" y1="9" x2="12" y2="13"></line>
    <line x1="12" y1="17" x2="12.01" y2="17"></line>
  </svg>
  <div>
    <span class="degraded-banner__tag">${escapeHtml(tagLabel)}</span>
    <p class="degraded-banner__text">${escapeHtml(message)}</p>
  </div>
</div>
<div class="flex items-center gap-2">
  <button type="button" class="btn btn-secondary text-xs" data-action="retry-connection">Check Live Status</button>
  <button type="button" class="btn btn-ghost text-xs" data-action="acknowledge-degraded">Acknowledge</button>
</div>
  `.trim();
}

/**
 * Renders the Pipeline Status Banner (#scan-status-banner).
 *
 * Pre-conditions:
 *   - scanState is an object representing pipeline progress.
 *   - temporalUiUrl is an optional configured external URL string.
 * Post-conditions:
 *   - Returns HTML with structured status indicators.
 *   - Omits external Temporal link if temporalUiUrl is not configured or empty.
 *
 * @param {object} scanState - Scan lifecycle state.
 * @param {string|null} [temporalUiUrl] - Optional external Temporal web UI link.
 * @returns {string} Rendered status banner HTML.
 */
export function renderScanStatusBannerHtml(scanState = {}, temporalUiUrl = null) {
  const s = scanState || {};
  const status = s.status || 'running';
  const wfId = s.workflow_id || '';
  const elapsed = s.elapsed_seconds != null ? `${s.elapsed_seconds}s` : '';
  const scraped = formatNumber(s.scraped_count || 0);
  const scored = formatNumber(s.scored_count || 0);
  const topDeals = formatNumber(s.top_deals_count || 0);
  const target = s.target_model || 'All Watchlist Models';
  const message = s.message || '';

  let modifier = 'scan-banner--running';
  if (status === 'completed') modifier = 'scan-banner--completed';
  else if (status === 'error') modifier = 'scan-banner--error';
  else if (status === 'unavailable') modifier = 'scan-banner--unavailable';

  let temporalAnchor = '';
  if (temporalUiUrl && typeof temporalUiUrl === 'string' && temporalUiUrl.trim() !== '') {
    const escapedUrl = escapeHtml(temporalUiUrl.trim());
    temporalAnchor = `<a href="${escapedUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-ghost text-xs">Temporal UI &nearr;</a>`;
  }

  if (status === 'submitting') {
    return `
      <div class="scan-banner ${modifier}">
        <span class="scan-banner__dot"></span>
        <span class="scan-banner__label">Dispatching surveillance workflow for ${escapeHtml(target)}...</span>
      </div>
    `.trim();
  }

  if (status === 'error' || status === 'unavailable') {
    return `
      <div class="scan-banner ${modifier} flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="scan-banner__dot"></span>
          <span class="scan-banner__label">${escapeHtml(message || 'Marketplace scan unavailable or failed.')}</span>
        </div>
        <div class="flex items-center gap-2">
          <button type="button" class="btn btn-secondary text-xs" data-action="retry-scan">Retry Scan</button>
          <button type="button" class="btn btn-ghost text-xs" data-action="dismiss-scan-banner">Dismiss</button>
        </div>
      </div>
    `.trim();
  }

  if (status === 'completed') {
    return `
      <div class="scan-banner ${modifier} flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="scan-banner__dot"></span>
          <span class="scan-banner__label">Scan completed: <strong class="tabular-nums">${scored}</strong> listings scored for ${escapeHtml(target)}.</span>
        </div>
        <button type="button" class="btn btn-ghost text-xs" data-action="dismiss-scan-banner">Dismiss</button>
      </div>
    `.trim();
  }

  return `
    <div class="scan-banner ${modifier} flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <span class="scan-banner__dot"></span>
        <span class="scan-banner__label">Marketplace Scan Running:</span>
        <span class="font-mono text-xs tabular-nums">${escapeHtml(wfId || 'Workflow')}</span>
        ${elapsed ? `<span class="control-hint tabular-nums">(${escapeHtml(elapsed)})</span>` : ''}
      </div>
      <div class="scan-banner__counters">
        <span>Scraped: <strong class="tabular-nums">${scraped}</strong></span>
        <span>Scored: <strong class="tabular-nums">${scored}</strong></span>
        <span>Top Deals: <strong class="tabular-nums">${topDeals}</strong></span>
      </div>
      <div class="flex items-center gap-2">
        ${temporalAnchor}
        <button type="button" class="btn btn-ghost text-xs" data-action="dismiss-scan-banner">Dismiss</button>
      </div>
    </div>
  `.trim();
}
