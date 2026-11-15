/**
 * Automotive Telemetry Dashboard - Pure SVG & HTML Visualizations (charts.js)
 *
 * Architectural Invariants:
 * - Pure vanilla ES module (zero external dependencies, zero CDNs).
 * - Strictly zero emoji glyphs.
 * - Design by Contract (DbC) on all functions.
 * - WCAG 2.2 AA accessibility and keyboard navigation.
 */

/**
 * Safe entity escaping for dynamic SVG text, XML nodes, and HTML attributes.
 *
 * Pre-conditions:
 *   - value can be string, number, boolean, null, or undefined.
 * Post-conditions:
 *   - Returns safely escaped string representation with XML entities replaced (&, <, >, ", ').
 *   - Returns empty string for null or undefined values.
 *
 * @param {any} value - Raw input value.
 * @returns {string} Escaped XML/HTML entity string.
 */
export function escapeSvgText(value) {
  if (value === null || value === undefined) {
    return '';
  }
  const str = String(value);
  return str
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
 *
 * @param {number|string} val - Raw price value.
 * @returns {string} Formatted USD string.
 */
function formatCurrency(val) {
  const num = Math.round(Number(val) || 0);
  if (num < 0) {
    return '-$' + Math.abs(num).toLocaleString('en-US');
  }
  return '$' + num.toLocaleString('en-US');
}

/**
 * Formats mileage ticks into compact abbreviation (e.g., "20k mi").
 *
 * Pre-conditions:
 *   - val is numeric mileage.
 * Post-conditions:
 *   - Returns compact string abbreviation.
 *
 * @param {number} val - Mileage value.
 * @returns {string} Abbreviated mileage tick string.
 */
function formatTickMileage(val) {
  const k = Math.round((Number(val) || 0) / 1000);
  return `${k}k mi`;
}

/**
 * Formats price ticks into compact abbreviation (e.g., "$35k").
 *
 * Pre-conditions:
 *   - val is numeric price.
 * Post-conditions:
 *   - Returns compact price tick string.
 *
 * @param {number} val - Price value.
 * @returns {string} Abbreviated price tick string.
 */
function formatTickPrice(val) {
  const k = Math.round((Number(val) || 0) / 1000);
  return `$${k}k`;
}

/**
 * Formats date string into short MM/DD label.
 *
 * Pre-conditions:
 *   - val is an ISO timestamp or date string.
 * Post-conditions:
 *   - Returns formatted "M/D" date string.
 *
 * @param {string} val - Date timestamp string.
 * @returns {string} Formatted date label.
 */
function formatDateLabel(val) {
  if (!val) return '';
  const d = new Date(val);
  if (isNaN(d.getTime())) return String(val).slice(0, 10);
  const m = d.getMonth() + 1;
  const day = d.getDate();
  return `${m}/${day}`;
}

/**
 * Computes ordinary least squares linear regression over mileage/price pairs.
 *
 * Pre-conditions:
 *   - points is an array of objects with mileage and price numbers.
 * Post-conditions:
 *   - Returns { slope_per_1k_miles, intercept } when points length >= 3 and variance > 0.
 *   - Returns null if insufficient points or zero variance.
 *
 * @param {Array<object>} points - Vehicle scatter points.
 * @returns {object|null} Computed regression parameters or null.
 */
function computeOls(points) {
  if (!Array.isArray(points) || points.length < 3) {
    return null;
  }
  const n = points.length;
  let sumX = 0;
  let sumY = 0;
  for (let i = 0; i < n; i++) {
    sumX += (Number(points[i].mileage) || 0) / 1000.0;
    sumY += Number(points[i].price) || 0;
  }
  const meanX = sumX / n;
  const meanY = sumY / n;
  let sxx = 0;
  let sxy = 0;
  for (let i = 0; i < n; i++) {
    const dx = (Number(points[i].mileage) || 0) / 1000.0 - meanX;
    const dy = (Number(points[i].price) || 0) - meanY;
    sxx += dx * dx;
    sxy += dx * dy;
  }
  if (Math.abs(sxx) < 1e-12) {
    return null;
  }
  const slope = sxy / sxx;
  const intercept = meanY - slope * meanX;
  if (!Number.isFinite(slope) || !Number.isFinite(intercept)) {
    return null;
  }
  return { slope_per_1k_miles: slope, intercept: intercept };
}

/**
 * Updates content and clamped positioning of interactive scatter focus tooltip.
 *
 * Pre-conditions:
 *   - tooltipEl is an HTMLElement for tooltip display.
 *   - pt is a vehicle scatter point data record.
 *   - containerEl is the chart wrapper HTMLElement.
 *   - nodeEl is the focused or hovered SVG group node.
 * Post-conditions:
 *   - Populates tooltipEl with tabular vehicle metrics.
 *   - Unhides tooltipEl and clamps its top/left position within containerEl bounds.
 *
 * @param {HTMLElement} tooltipEl - Tooltip element.
 * @param {object} pt - Vehicle point data.
 * @param {HTMLElement} containerEl - Parent container element.
 * @param {SVGElement} nodeEl - Focused SVG node.
 */
function updateTooltip(tooltipEl, pt, containerEl, nodeEl) {
  const title =
    pt.title ||
    `${pt.year || ''} ${pt.make || ''} ${pt.model || ''}`.trim() ||
    'Vehicle Listing';
  const price = Math.round(Number(pt.price) || 0);
  const mileage = Math.round(Number(pt.mileage) || 0);
  const pctl = pt.cohort_percentile != null ? `${Math.round(Number(pt.cohort_percentile))}%` : 'N/A';
  const score = pt.deal_score != null ? Math.round(Number(pt.deal_score)) : 'N/A';
  const dom = pt.days_on_market != null ? `${pt.days_on_market}d` : 'N/A';

  tooltipEl.innerHTML = `
    <div class="chart-tooltip-title">${escapeSvgText(title)}</div>
    <div class="chart-tooltip-row">
      <span>Listed Price</span>
      <span class="chart-tooltip-val">${formatCurrency(price)}</span>
    </div>
    <div class="chart-tooltip-row">
      <span>Mileage</span>
      <span class="chart-tooltip-val">${mileage.toLocaleString('en-US')} mi</span>
    </div>
    <div class="chart-tooltip-row">
      <span>Cohort Pctl</span>
      <span class="chart-tooltip-val">${escapeSvgText(pctl)}</span>
    </div>
    <div class="chart-tooltip-row">
      <span>Deal Score</span>
      <span class="chart-tooltip-val">${score}</span>
    </div>
    <div class="chart-tooltip-row">
      <span>DOM</span>
      <span class="chart-tooltip-val">${escapeSvgText(dom)}</span>
    </div>
  `.trim();
  tooltipEl.hidden = false;

  if (
    containerEl &&
    nodeEl &&
    typeof containerEl.getBoundingClientRect === 'function' &&
    typeof nodeEl.getBoundingClientRect === 'function'
  ) {
    const containerRect = containerEl.getBoundingClientRect();
    const nodeRect = nodeEl.getBoundingClientRect();
    const tooltipRect =
      typeof tooltipEl.getBoundingClientRect === 'function'
        ? tooltipEl.getBoundingClientRect()
        : { width: 220, height: 140 };

    const nodeCenterX = nodeRect.left + nodeRect.width / 2 - containerRect.left;
    const nodeTopY = nodeRect.top - containerRect.top;

    let left = nodeCenterX - tooltipRect.width / 2;
    let top = nodeTopY - tooltipRect.height - 10;

    const minLeft = 8;
    const maxLeft = Math.max(minLeft, containerRect.width - tooltipRect.width - 8);
    left = Math.max(minLeft, Math.min(maxLeft, left));

    if (top < 8) {
      top = nodeRect.bottom - containerRect.top + 10;
    }
    const maxTop = Math.max(8, containerRect.height - tooltipRect.height - 8);
    top = Math.max(8, Math.min(maxTop, top));

    tooltipEl.style.left = `${left.toFixed(1)}px`;
    tooltipEl.style.top = `${top.toFixed(1)}px`;
  }
}

/**
 * Renders the interactive Price-vs-Mileage Valuation Frontier Scatter Chart.
 *
 * Pre-conditions:
 *   - containerEl is an HTMLElement hosting the rendered chart.
 *   - tooltipEl is an HTMLElement or null for the floating tooltip.
 *   - cohortData contains scatter_points (array), sample_size (number),
 *     p25 (number), p50 (number), and optional ols_trendline (object).
 *   - options can optionally specify pinnedIds (Set) and onSelectListing (function).
 * Post-conditions:
 *   - When scatter_points is empty, renders .empty-state inside containerEl and sets tooltipEl.hidden = true.
 *   - When scatter_points has items, renders responsive SVG with clipped OLS trendline,
 *     P25 Buy-Zone rect, reference lines, and keyboard accessible .frontier-node elements.
 *   - Binds click, mouseenter, mousemove, mouseleave, focus, blur, and keyboard events
 *     (ArrowLeft, ArrowRight, Enter, Space) with callback to options.onSelectListing(id).
 *
 * @param {HTMLElement} containerEl - Target DOM container.
 * @param {HTMLElement|null} tooltipEl - Target floating tooltip DOM element.
 * @param {object} cohortData - Cohort aggregate dataset with scatter_points.
 * @param {object} [options={}] - Interactive options (pinnedIds, onSelectListing).
 */
export function renderFrontierChart(containerEl, tooltipEl, cohortData, options = {}) {
  if (!containerEl) {
    return;
  }

  const rawPoints = cohortData?.scatter_points;
  if (!Array.isArray(rawPoints) || rawPoints.length === 0) {
    if (tooltipEl) {
      tooltipEl.hidden = true;
    }
    containerEl.innerHTML = `
      <div class="empty-state">
        <p class="empty-state__title">No Active Market Listings</p>
        <p class="empty-state__text">Cohort dataset contains no scatter points for valuation frontier analysis.</p>
      </div>
    `.trim();
    return;
  }

  const points = rawPoints.filter((p) => p && Number.isFinite(Number(p.price)));
  if (points.length === 0) {
    if (tooltipEl) {
      tooltipEl.hidden = true;
    }
    containerEl.innerHTML = `
      <div class="empty-state">
        <p class="empty-state__title">No Active Market Listings</p>
        <p class="empty-state__text">Cohort dataset contains no scatter points for valuation frontier analysis.</p>
      </div>
    `.trim();
    return;
  }

  // Mileage bounds (X axis)
  let maxMileage = 0;
  for (let i = 0; i < points.length; i++) {
    const m = Number(points[i].mileage) || 0;
    if (m > maxMileage) maxMileage = m;
  }
  const xMin = 0;
  const xMax = Math.max(20000, Math.ceil((maxMileage * 1.08) / 10000) * 10000);

  // Price bounds (Y axis)
  let minPrice = Infinity;
  let maxPrice = -Infinity;
  for (let i = 0; i < points.length; i++) {
    const pr = Number(points[i].price) || 0;
    if (pr < minPrice) minPrice = pr;
    if (pr > maxPrice) maxPrice = pr;
  }
  if (!Number.isFinite(minPrice)) minPrice = 10000;
  if (!Number.isFinite(maxPrice) || maxPrice <= minPrice) maxPrice = minPrice + 40000;

  if (cohortData.p25 && Number(cohortData.p25) < minPrice) minPrice = Number(cohortData.p25);
  if (cohortData.p50 && Number(cohortData.p50) > maxPrice) maxPrice = Number(cohortData.p50);
  if (cohortData.min_price && Number(cohortData.min_price) < minPrice) minPrice = Number(cohortData.min_price);
  if (cohortData.max_price && Number(cohortData.max_price) > maxPrice) maxPrice = Number(cohortData.max_price);

  const pricePad = Math.max(2000, (maxPrice - minPrice) * 0.08);
  const yMin = Math.max(0, Math.floor((minPrice - pricePad) / 5000) * 5000);
  const yMax = Math.ceil((maxPrice + pricePad) / 5000) * 5000;

  function scaleX(m) {
    const frac = (m - xMin) / (xMax - xMin || 1);
    return 76 + Math.max(0, Math.min(1, frac)) * 772;
  }

  function scaleY(pr) {
    const frac = (pr - yMin) / (yMax - yMin || 1);
    return 360 - Math.max(0, Math.min(1, frac)) * 332;
  }

  function scaleYRaw(pr) {
    const frac = (pr - yMin) / (yMax - yMin || 1);
    return 360 - frac * 332;
  }

  // Gridlines and Ticks
  const xTicksCount = 5;
  let xTicksSvg = '';
  for (let i = 0; i <= xTicksCount; i++) {
    const val = xMin + (i / xTicksCount) * (xMax - xMin);
    const x = scaleX(val);
    xTicksSvg += `<line class="frontier-gridline" x1="${x.toFixed(1)}" y1="28" x2="${x.toFixed(1)}" y2="360" />`;
    xTicksSvg += `<text class="chart-tick" x="${x.toFixed(1)}" y="378" text-anchor="middle">${formatTickMileage(val)}</text>`;
  }

  const yTicksCount = 4;
  let yTicksSvg = '';
  for (let i = 0; i <= yTicksCount; i++) {
    const val = yMin + (i / yTicksCount) * (yMax - yMin);
    const y = scaleY(val);
    yTicksSvg += `<line class="frontier-gridline" x1="76" y1="${y.toFixed(1)}" x2="848" y2="${y.toFixed(1)}" />`;
    yTicksSvg += `<text class="chart-tick" x="68" y="${(y + 4).toFixed(1)}" text-anchor="end">${formatTickPrice(val)}</text>`;
  }

  const axesSvg = `
    <line class="frontier-axis" x1="76" y1="360" x2="848" y2="360" />
    <line class="frontier-axis" x1="76" y1="28" x2="76" y2="360" />
    <text class="chart-tick" x="462" y="405" text-anchor="middle">Odometer (miles)</text>
    <text class="chart-tick" transform="rotate(-90)" x="-194" y="24" text-anchor="middle">Listed Price (USD)</text>
  `;

  // Buy-Zone rectangle (below P25)
  let buyZoneSvg = '';
  const p25 = Number(cohortData.p25);
  if (Number.isFinite(p25) && p25 > yMin) {
    const p25Y = scaleY(p25);
    const buyTop = Math.max(28, p25Y);
    const buyHeight = Math.max(0, 360 - buyTop);
    buyZoneSvg = `<rect class="frontier-buyzone" x="76" y="${buyTop.toFixed(1)}" width="772" height="${buyHeight.toFixed(1)}" />`;
  }

  // Reference lines for P25 (solid) and P50 (dashed)
  let refLinesSvg = '';
  if (Number.isFinite(p25)) {
    const p25Y = scaleY(p25);
    refLinesSvg += `<line class="frontier-p25-line" x1="76" y1="${p25Y.toFixed(1)}" x2="848" y2="${p25Y.toFixed(1)}" />`;
  }
  const p50 = Number(cohortData.p50);
  if (Number.isFinite(p50)) {
    const p50Y = scaleY(p50);
    refLinesSvg += `<line class="frontier-p50-line" x1="76" y1="${p50Y.toFixed(1)}" x2="848" y2="${p50Y.toFixed(1)}" />`;
  }

  // OLS regression line or Insufficient sample notice
  let olsSvg = '';
  const sampleSize = Number(cohortData.sample_size ?? points.length);
  let slope = cohortData.ols_trendline?.slope_per_1k_miles ?? cohortData.ols_trendline?.slope;
  let intercept = cohortData.ols_trendline?.intercept;

  if (sampleSize >= 3) {
    if (
      slope === undefined ||
      intercept === undefined ||
      !Number.isFinite(Number(slope)) ||
      !Number.isFinite(Number(intercept))
    ) {
      const computed = computeOls(points);
      if (computed) {
        slope = computed.slope_per_1k_miles;
        intercept = computed.intercept;
      }
    }
  }

  if (sampleSize >= 3 && Number.isFinite(Number(slope)) && Number.isFinite(Number(intercept))) {
    const s = Number(slope);
    const ic = Number(intercept);
    const yVal1 = ic + s * (xMin / 1000.0);
    const yVal2 = ic + s * (xMax / 1000.0);
    const x1 = scaleX(xMin);
    const y1 = scaleYRaw(yVal1);
    const x2 = scaleX(xMax);
    const y2 = scaleYRaw(yVal2);
    olsSvg = `<line class="frontier-ols-line" x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" />`;
  } else {
    olsSvg = `<text class="chart-tick" x="462" y="194" text-anchor="middle">Insufficient sample (n &lt; 3) for OLS regression</text>`;
  }

  // Sort points by mileage ascending so keyboard ArrowLeft/ArrowRight navigates monotonically
  const sortedPoints = [...points].sort(
    (a, b) => (Number(a.mileage) || 0) - (Number(b.mileage) || 0)
  );

  const nodesSvg = sortedPoints
    .map((pt, i) => {
      const cx = scaleX(Number(pt.mileage) || 0);
      const cy = scaleY(Number(pt.price) || 0);
      const id = String(pt.id || '');
      const isPinned = Boolean(
        options.pinnedIds &&
          typeof options.pinnedIds.has === 'function' &&
          (options.pinnedIds.has(id) || options.pinnedIds.has(pt.id))
      );
      const score = Number(pt.deal_score ?? 0);
      const nodeColor =
        score >= 85
          ? 'var(--status-excellent)'
          : score >= 75
          ? 'var(--status-info)'
          : 'var(--status-danger)';
      const label = `${pt.year || ''} ${pt.title || pt.make + ' ' + pt.model || 'Listing'} - ${formatCurrency(
        pt.price
      )}, ${Math.round(Number(pt.mileage) || 0).toLocaleString('en-US')} mi, Score ${Math.round(score)}`;

      return `
        <g class="frontier-node" tabindex="0" role="button" data-listing-id="${escapeSvgText(id)}" data-index="${i}" aria-label="${escapeSvgText(label)}">
          <circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="14" fill="transparent" />
          ${
            isPinned
              ? `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="8.5" fill="none" stroke="var(--text-primary)" stroke-width="2" class="frontier-node-pin" />`
              : ''
          }
          <circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="5.5" fill="${nodeColor}" />
        </g>
      `.trim();
    })
    .join('\n');

  const svgHtml = `
<svg id="frontier-svg" class="frontier-svg" viewBox="0 0 880 420" role="img" aria-labelledby="frontier-title" aria-describedby="frontier-desc">
  <title id="frontier-title">Price vs Mileage Valuation Frontier</title>
  <desc id="frontier-desc">Empirical cohort scatter plot evaluating vehicle pricing efficiency against odometer mileage with OLS regression and P25 buy-zone boundaries.</desc>
  <defs>
    <clipPath id="frontier-plot-clip">
      <rect x="76" y="28" width="772" height="332" />
    </clipPath>
  </defs>
  <g class="frontier-gridlines">
    ${xTicksSvg}
    ${yTicksSvg}
  </g>
  <g class="frontier-axes">
    ${axesSvg}
  </g>
  <g clip-path="url(#frontier-plot-clip)">
    ${buyZoneSvg}
    ${refLinesSvg}
    ${olsSvg}
  </g>
  <g class="frontier-nodes">
    ${nodesSvg}
  </g>
</svg>
  `.trim();

  containerEl.innerHTML = svgHtml;

  // Bind interactive events and keyboard navigation
  const nodeEls = Array.from(containerEl.querySelectorAll('.frontier-node'));
  nodeEls.forEach((nodeEl, idx) => {
    const pt = sortedPoints[idx];
    if (!pt) return;

    function showTooltip() {
      if (!tooltipEl) return;
      updateTooltip(tooltipEl, pt, containerEl, nodeEl);
    }

    function hideTooltip() {
      if (tooltipEl) {
        tooltipEl.hidden = true;
      }
    }

    nodeEl.addEventListener('mouseenter', showTooltip);
    nodeEl.addEventListener('mousemove', showTooltip);
    nodeEl.addEventListener('mouseleave', hideTooltip);

    nodeEl.addEventListener('focus', showTooltip);
    nodeEl.addEventListener('blur', hideTooltip);

    nodeEl.addEventListener('click', () => {
      if (typeof options.onSelectListing === 'function') {
        options.onSelectListing(pt.id);
      }
    });

    nodeEl.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight') {
        e.preventDefault();
        const nextIdx = (idx + 1) % nodeEls.length;
        nodeEls[nextIdx].focus();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        const prevIdx = (idx - 1 + nodeEls.length) % nodeEls.length;
        nodeEls[prevIdx].focus();
      } else if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
        e.preventDefault();
        if (typeof options.onSelectListing === 'function') {
          options.onSelectListing(pt.id);
        }
      }
    });
  });
}

/**
 * Renders an inline or expanded pure SVG price sparkline trajectory.
 *
 * Pre-conditions:
 *   - snapshots is an array of snapshot records or price numbers.
 *   - options can optionally specify width (number), height (number), and compact (boolean).
 * Post-conditions:
 *   - Returns clean, valid SVG markup string conforming to .price-sparkline token rules.
 *   - Handles 0 snapshots, 1 snapshot baseline, and >= 2 polyline + polygon snapshots.
 *
 * @param {Array<object|number>} snapshots - Chronological price snapshot records.
 * @param {object} [options={}] - Layout configuration options.
 * @returns {string} SVG markup string.
 */
export function renderPriceSparkline(snapshots, options = {}) {
  const width = typeof options.width === 'number' ? options.width : 560;
  const height = typeof options.height === 'number' ? options.height : 110;
  const compact = Boolean(options.compact);

  const rawList = Array.isArray(snapshots) ? snapshots : [];
  const valid = rawList
    .map((s) => {
      const price = typeof s === 'number' ? s : Number(s?.price);
      const recorded_at = s && typeof s === 'object' ? (s.time || s.recorded_at || s.timestamp || null) : null;
      return { price, recorded_at };
    })
    .filter((s) => Number.isFinite(s.price));

  if (valid.length === 0) {
    const midY = (height / 2).toFixed(1);
    return `<svg class="price-sparkline" viewBox="0 0 ${width} ${height}" role="img" aria-label="No price snapshots recorded"><line x1="0" y1="${midY}" x2="${width}" y2="${midY}" stroke="var(--border-subtle)" stroke-dasharray="3 3" /><text class="chart-tick" x="${(width / 2).toFixed(1)}" y="${(height / 2 + 4).toFixed(1)}" fill="var(--text-muted)" font-family="var(--font-mono)" font-size="11" text-anchor="middle">No price snapshots recorded</text></svg>`;
  }

  if (valid.length === 1) {
    const midY = (height / 2).toFixed(1);
    const p0 = Math.round(valid[0].price);
    const r = compact ? 3 : 4.5;
    const labelY = (height / 2 + (compact ? 12 : 20)).toFixed(1);
    const fontSize = compact ? 9 : 11;
    return `<svg class="price-sparkline" viewBox="0 0 ${width} ${height}" role="img" aria-label="1 snapshot recorded: $${p0.toLocaleString('en-US')}"><line x1="12" y1="${midY}" x2="${width - 12}" y2="${midY}" stroke="var(--border-subtle)" stroke-dasharray="3 3" /><circle cx="${(width / 2).toFixed(1)}" cy="${midY}" r="${r}" fill="var(--text-muted)" stroke="var(--bg-canvas)" stroke-width="1.5" /><text class="chart-tick" x="${(width / 2).toFixed(1)}" y="${labelY}" fill="var(--text-muted)" font-family="var(--font-mono)" font-size="${fontSize}" text-anchor="middle">1 snapshot recorded</text></svg>`;
  }

  // Sort chronologically if recorded_at strings present
  if (valid.every((s) => s.recorded_at)) {
    valid.sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime());
  }

  const firstPrice = valid[0].price;
  const lastPrice = valid[valid.length - 1].price;
  const priceDelta = lastPrice - firstPrice;

  let trendColor = 'var(--text-muted)';
  let areaOpacity = '0.08';
  if (priceDelta < 0) {
    trendColor = 'var(--status-cut)';
    areaOpacity = '0.12';
  } else if (priceDelta > 0) {
    trendColor = 'var(--status-danger)';
    areaOpacity = '0.12';
  }

  const padX = compact ? 6 : 48;
  const padTop = compact ? 4 : 22;
  const padBottom = compact ? 4 : 24;
  const plotW = Math.max(10, width - padX * 2);
  const plotH = Math.max(10, height - padTop - padBottom);

  const prices = valid.map((v) => v.price);
  let minP = Math.min(...prices);
  let maxP = Math.max(...prices);
  if (minP === maxP) {
    minP -= 100;
    maxP += 100;
  }

  const coords = valid.map((v, i) => {
    const x = padX + (i / (valid.length - 1)) * plotW;
    const y = padTop + plotH - ((v.price - minP) / (maxP - minP)) * plotH;
    return { x, y, price: v.price, recorded_at: v.recorded_at };
  });

  const polylinePoints = coords.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');
  const baselineY = (padTop + plotH).toFixed(1);
  const areaPoints = `${coords[0].x.toFixed(1)},${baselineY} ${polylinePoints} ${coords[coords.length - 1].x.toFixed(1)},${baselineY}`;

  const nodesMarkup = coords
    .map((c, i) => {
      const isTerminal = i === coords.length - 1;
      if (isTerminal) {
        const termR = compact ? 3 : 4.5;
        return `<circle cx="${c.x.toFixed(1)}" cy="${c.y.toFixed(1)}" r="${termR}" fill="${trendColor}" stroke="var(--bg-canvas)" stroke-width="1.5" />`;
      }
      if (compact) return '';
      const nodeColor =
        i === 0
          ? 'var(--text-muted)'
          : c.price < coords[i - 1].price
          ? 'var(--status-cut)'
          : c.price > coords[i - 1].price
          ? 'var(--status-danger)'
          : 'var(--text-muted)';
      return `<circle cx="${c.x.toFixed(1)}" cy="${c.y.toFixed(1)}" r="2.5" fill="${nodeColor}" />`;
    })
    .join('');

  let labelsMarkup = '';
  if (!compact) {
    const pStartFormatted = `$${Math.round(firstPrice).toLocaleString('en-US')}`;
    const pEndFormatted = `$${Math.round(lastPrice).toLocaleString('en-US')}`;
    const topLabelY = (padTop - 6).toFixed(1);
    labelsMarkup += `<text class="chart-tick" x="${padX}" y="${topLabelY}" text-anchor="start">${pStartFormatted}</text>`;
    labelsMarkup += `<text class="chart-tick" x="${width - padX}" y="${topLabelY}" text-anchor="end">${pEndFormatted}</text>`;

    if (valid[0].recorded_at && valid[valid.length - 1].recorded_at) {
      const d0 = formatDateLabel(valid[0].recorded_at);
      const d1 = formatDateLabel(valid[valid.length - 1].recorded_at);
      const botLabelY = (height - 6).toFixed(1);
      labelsMarkup += `<text class="chart-tick" x="${padX}" y="${botLabelY}" text-anchor="start">${escapeSvgText(d0)}</text>`;
      labelsMarkup += `<text class="chart-tick" x="${width - padX}" y="${botLabelY}" text-anchor="end">${escapeSvgText(d1)}</text>`;
    }
  }

  const deltaDesc =
    priceDelta < 0
      ? `cut by $${Math.abs(Math.round(priceDelta)).toLocaleString('en-US')}`
      : priceDelta > 0
      ? `increased by $${Math.round(priceDelta).toLocaleString('en-US')}`
      : 'unchanged';
  const ariaLabel = `Price sparkline from $${Math.round(firstPrice).toLocaleString('en-US')} to $${Math.round(lastPrice).toLocaleString('en-US')}, ${deltaDesc}`;

  return `
<svg class="price-sparkline" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeSvgText(ariaLabel)}">
  <polygon points="${areaPoints}" fill="${trendColor}" fill-opacity="${areaOpacity}" />
  <polyline points="${polylinePoints}" fill="none" stroke="${trendColor}" stroke-width="${compact ? '1.5' : '2'}" stroke-linejoin="round" stroke-linecap="round" />
  ${nodesMarkup}
  ${labelsMarkup}
</svg>
  `.trim();
}

/**
 * Renders cohort valuation distribution range bar component HTML.
 *
 * Pre-conditions:
 *   - deal is an object representing vehicle listing with optional price, deal_score,
 *     and cohort analytics or distribution percentiles.
 * Post-conditions:
 *   - Returns pure HTML/CSS string using exact components.css selectors.
 *   - Clamps marker position within 2%..98% bounds.
 *   - Gracefully handles inverted or flat ranges where max <= min.
 *
 * @param {object} deal - Vehicle deal object.
 * @returns {string} Pure HTML string for cohort range bar component.
 */
export function renderCohortRangeBarHtml(deal) {
  const d = deal || {};
  const price = Math.round(Number(d.price ?? d.listing_price ?? 0));
  const dealScore = Number(d.deal_score ?? d.score ?? 0);
  const cohort = d.cohort || d.analytics || {};

  let min = Math.round(Number(d.cohort_min ?? cohort.cohort_min ?? cohort.min_price ?? cohort.min ?? 0));
  let p25 = Math.round(Number(d.cohort_p25 ?? cohort.cohort_p25 ?? cohort.p25 ?? cohort.fair_low ?? 0));
  let p50 = Math.round(Number(d.cohort_p50 ?? cohort.cohort_p50 ?? cohort.p50 ?? cohort.fair_median ?? cohort.median ?? 0));
  let p75 = Math.round(Number(d.cohort_p75 ?? cohort.cohort_p75 ?? cohort.p75 ?? cohort.fair_high ?? 0));
  let max = Math.round(Number(d.cohort_max ?? cohort.cohort_max ?? cohort.max_price ?? cohort.max ?? 0));

  // Safe bounds handling when max <= min
  if (max <= min) {
    if (price > 0) {
      min = Math.max(0, Math.round(price * 0.7));
      max = Math.round(price * 1.3);
    } else {
      min = 0;
      max = 100000;
    }
  }

  const range = max - min || 1;
  if (p25 <= min || p25 >= max) p25 = Math.round(min + range * 0.25);
  if (p50 <= p25 || p50 >= max) p50 = Math.round(min + range * 0.5);
  if (p75 <= p50 || p75 >= max) p75 = Math.round(min + range * 0.75);

  function toPct(v) {
    return Math.max(0, Math.min(100, ((v - min) / range) * 100));
  }

  const buyWidth = toPct(p25).toFixed(1);
  const iqrLeft = toPct(p25).toFixed(1);
  const iqrWidth = Math.max(0, toPct(p75) - toPct(p25)).toFixed(1);
  const medianLeft = toPct(p50).toFixed(1);

  // Marker clamped 2%..98%
  const rawMarkerPct = toPct(price);
  const markerLeft = Math.max(2, Math.min(98, rawMarkerPct)).toFixed(1);

  let markerModifier = 'cohort-marker--fair';
  if (dealScore >= 85 || (p25 > 0 && price <= p25)) {
    markerModifier = 'cohort-marker--excellent';
  } else if (dealScore < 60 || (p75 > 0 && price > p75)) {
    markerModifier = 'cohort-marker--danger';
  } else {
    markerModifier = 'cohort-marker--fair';
  }

  const pctl = d.cohort_percentile ?? cohort.cohort_percentile;
  const pctlVal = pctl != null ? `Pctl: ${Math.round(Number(pctl))}%` : `$${price.toLocaleString('en-US')}`;

  return `
<div class="cohort-range-bar">
  <div class="cohort-range-header">
    <span class="cohort-range-label">Cohort Valuation Range</span>
    <span class="cohort-range-val">${escapeSvgText(pctlVal)}</span>
  </div>
  <div class="cohort-track">
    <div class="cohort-buyzone" style="left: 0%; width: ${buyWidth}%;"></div>
    <div class="cohort-iqr" style="left: ${iqrLeft}%; width: ${iqrWidth}%;"></div>
    <div class="cohort-median" style="left: ${medianLeft}%;"></div>
    <div class="cohort-marker ${markerModifier}" style="left: ${markerLeft}%;" title="Listing Price: $${price.toLocaleString('en-US')}"></div>
  </div>
  <div class="cohort-range-footer">
    <span>$${min.toLocaleString('en-US')}</span>
    <span>P25: $${p25.toLocaleString('en-US')}</span>
    <span>P50: $${p50.toLocaleString('en-US')}</span>
    <span>$${max.toLocaleString('en-US')}</span>
  </div>
</div>
  `.trim();
}
