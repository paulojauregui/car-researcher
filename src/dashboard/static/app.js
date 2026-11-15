/**
 * Automotive Telemetry Dashboard - Client Orchestration Controller (app.js)
 *
 * Architectural Invariants:
 * - Pure vanilla ES module importing exclusively from ./views.js and ./charts.js (zero CDNs).
 * - Strictly zero emoji glyphs across all logic, templates, comments, and strings.
 * - Design by Contract (DbC) docstrings on all functions.
 * - WCAG 2.2 AA accessibility: roving tabindex, focus management, focus trapping, aria attributes.
 * - Optimistic UI updates with rollback and polite screen-reader announcements.
 * - Renders 4 primary workspaces: Deal Workbench, Market Intelligence, Arbitrage, Comparator.
 */

import {
  escapeHtml,
  formatCurrency,
  formatSignedCurrency,
  formatNumber,
  renderDealsSectionHtml,
  renderWorkbenchLoadingHtml,
  renderMarketLoadingHtml,
  renderArbitrageLoadingHtml,
  renderCompareLoadingHtml,
  renderWorkspaceErrorHtml,
  renderMarketWorkspaceHtml,
  renderArbitrageWorkspaceHtml,
  renderComparatorWorkspaceHtml,
  renderAnalysisDrawerHtml,
  renderCompareTrayHtml,
  renderDegradedBannerHtml,
  renderScanStatusBannerHtml,
} from './views.js';

import {
  renderFrontierChart,
} from './charts.js';

export const STORAGE_KEY_PINS = 'car_researcher_compare_pins';
export const SCAN_POLL_INTERVAL_MS = 2000;
export const SEARCH_DEBOUNCE_MS = 250;
export const MAX_COMPARE_PINS = 3;

/**
 * Global client state tree.
 */
export const state = {
  activeWorkspace: 'workbench',
  deals: [],
  kpis: {},
  filters: {
    q: '',
    make: '',
    max_price: '',
    max_mileage: '',
    max_distance: '',
    sort: 'score_desc',
    tab: 'all',
    view: 'grid',
  },
  provenance: {},
  marketOverview: null,
  cohortsData: null,
  selectedCohortKey: 'ALL',
  dealersData: null,
  compareData: null,
  pinnedIds: new Set(),
  scanIntervalId: null,
  lastFocusedTrigger: null,
  isHydrating: false,
};

let searchDebounceTimer = null;

/**
 * Announces a textual message politely to assistive technologies via #live-announcer.
 *
 * Pre-conditions:
 *   - message is a non-empty string.
 * Post-conditions:
 *   - Updates the #live-announcer DOM element content after a brief tick.
 *
 * @param {string} message - Text announcement.
 */
export function announce(message) {
  const el = document.getElementById('live-announcer');
  if (el) {
    el.textContent = '';
    setTimeout(() => {
      el.textContent = message;
    }, 50);
  }
}

/**
 * Persists currently pinned listing IDs into localStorage.
 *
 * Pre-conditions:
 *   - state.pinnedIds is a Set of string IDs.
 * Post-conditions:
 *   - Saves JSON array under STORAGE_KEY_PINS (capped at MAX_COMPARE_PINS).
 */
export function savePinsToStorage() {
  try {
    const ids = Array.from(state.pinnedIds).slice(0, MAX_COMPARE_PINS);
    localStorage.setItem(STORAGE_KEY_PINS, JSON.stringify(ids));
  } catch (err) {
    console.warn('Unable to persist compare pins to localStorage', err);
  }
}

/**
 * Restores pinned listing IDs from localStorage into state.
 *
 * Pre-conditions:
 *   - localStorage is available or fails gracefully.
 * Post-conditions:
 *   - state.pinnedIds populated with restored IDs (max 3).
 */
export function loadPinsFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_PINS);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        state.pinnedIds = new Set(parsed.map(String).slice(0, MAX_COMPARE_PINS));
      }
    }
  } catch (err) {
    console.warn('Unable to load compare pins from localStorage', err);
    state.pinnedIds = new Set();
  }
}

/**
 * Updates the compare tab badge count indicator (#compare-tab-badge).
 *
 * Pre-conditions:
 *   - state.pinnedIds is initialized.
 * Post-conditions:
 *   - #compare-tab-badge displays "N/3" where N is pinned count.
 */
export function updateCompareTabBadge() {
  const badge = document.getElementById('compare-tab-badge');
  if (badge) {
    badge.textContent = `${state.pinnedIds.size}/${MAX_COMPARE_PINS}`;
  }
}

/**
 * Builds a fast lookup map of known listings by ID.
 *
 * Pre-conditions:
 *   - state.deals is an array of deal objects.
 * Post-conditions:
 *   - Returns a dictionary mapping listingId to deal object.
 *
 * @returns {Record<string, object>} Map of listing objects by ID.
 */
function getDealsByIdMap() {
  const map = {};
  if (Array.isArray(state.deals)) {
    for (let i = 0; i < state.deals.length; i++) {
      const d = state.deals[i];
      const lid = String(d.id || d.platform_id || d.vin || '');
      if (lid) {
        map[lid] = d;
      }
    }
  }
  if (state.compareData && Array.isArray(state.compareData.deals)) {
    for (let i = 0; i < state.compareData.deals.length; i++) {
      const d = state.compareData.deals[i];
      const lid = String(d.id || d.platform_id || d.vin || '');
      if (lid && !map[lid]) {
        map[lid] = d;
      }
    }
  }
  return map;
}

/**
 * Updates the floating bottom compare tray (#compare-tray).
 *
 * Pre-conditions:
 *   - state.pinnedIds and deals lookup are available.
 * Post-conditions:
 *   - Renders HTML via renderCompareTrayHtml and toggles hidden attribute.
 */
export function updateCompareTray() {
  const tray = document.getElementById('compare-tray');
  const mainEl = document.getElementById('main-content');
  if (!tray) {
    if (mainEl) {
      mainEl.classList.remove('is-tray-visible');
    }
    return;
  }
  const shouldHide = state.pinnedIds.size === 0 || state.activeWorkspace === 'compare';
  if (shouldHide) {
    tray.hidden = true;
    tray.innerHTML = '';
    if (mainEl) {
      mainEl.classList.remove('is-tray-visible');
    }
    return;
  }
  const dealsById = getDealsByIdMap();
  tray.innerHTML = renderCompareTrayHtml(dealsById, Array.from(state.pinnedIds));
  tray.hidden = false;
  if (mainEl) {
    mainEl.classList.add('is-tray-visible');
  }
}

/**
 * Synchronizes pin button states and card highlight classes across the document.
 *
 * Pre-conditions:
 *   - DOM contains [data-action="pin"] buttons and .deal-card elements.
 * Post-conditions:
 *   - aria-pressed and is-pinned classes reflect state.pinnedIds.
 */
export function updatePinButtonsUI() {
  const pinButtons = document.querySelectorAll('[data-action="pin"]');
  for (let i = 0; i < pinButtons.length; i++) {
    const btn = pinButtons[i];
    const lid = btn.getAttribute('data-listing-id');
    const isPinned = state.pinnedIds.has(lid);
    btn.setAttribute('aria-pressed', String(isPinned));
    if (btn.classList.contains('btn')) {
      btn.textContent = isPinned ? 'Pinned' : 'Compare';
    }
  }

  const cards = document.querySelectorAll('.deal-card');
  for (let i = 0; i < cards.length; i++) {
    const card = cards[i];
    const lid = card.getAttribute('data-listing-id');
    card.classList.toggle('is-pinned', state.pinnedIds.has(lid));
  }
}

/**
 * Toggles the pinned status of a listing ID with a strict 3-item limit.
 *
 * Pre-conditions:
 *   - listingId is a non-empty string.
 * Post-conditions:
 *   - If already pinned, removes pin.
 *   - If not pinned and count < 3, adds pin.
 *   - If not pinned and count >= 3, warns user via live announcement.
 *   - Persists state, updates badges, tray, button UI, and active Comparator.
 *
 * @param {string} listingId - ID of vehicle listing.
 */
export function togglePin(listingId) {
  if (!listingId) {
    return;
  }
  const strId = String(listingId);
  if (state.pinnedIds.has(strId)) {
    unpinListing(strId);
    return;
  }
  if (state.pinnedIds.size >= MAX_COMPARE_PINS) {
    announce('Comparison limit reached: maximum 3 vehicles can be compared simultaneously.');
    return;
  }

  state.pinnedIds.add(strId);
  savePinsToStorage();
  updateCompareTabBadge();
  updateCompareTray();
  updatePinButtonsUI();
  announce(`Vehicle added to comparison queue (${state.pinnedIds.size}/${MAX_COMPARE_PINS})`);

  if (state.activeWorkspace === 'compare') {
    loadCompareWorkspace(true);
  }
}

/**
 * Removes a listing from the comparison queue.
 *
 * Pre-conditions:
 *   - listingId is a string ID.
 * Post-conditions:
 *   - Removes ID from state.pinnedIds, persists, and refreshes UI.
 *
 * @param {string} listingId - ID of vehicle listing.
 */
export function unpinListing(listingId) {
  if (!listingId) {
    return;
  }
  const strId = String(listingId);
  state.pinnedIds.delete(strId);
  savePinsToStorage();
  updateCompareTabBadge();
  updateCompareTray();
  updatePinButtonsUI();
  announce(`Vehicle removed from comparison queue (${state.pinnedIds.size}/${MAX_COMPARE_PINS})`);

  if (state.activeWorkspace === 'compare') {
    loadCompareWorkspace(true);
  }
}

/**
 * Clears all pinned listings from the comparison queue.
 *
 * Pre-conditions:
 *   - None.
 * Post-conditions:
 *   - Empties state.pinnedIds, clears storage, and updates UI.
 */
export function clearAllPins() {
  state.pinnedIds.clear();
  savePinsToStorage();
  updateCompareTabBadge();
  updateCompareTray();
  updatePinButtonsUI();
  announce('All vehicles removed from comparison queue');

  if (state.activeWorkspace === 'compare') {
    loadCompareWorkspace(true);
  }
}

/**
 * Switches the active primary workspace tab and updates roving tabindex.
 *
 * Pre-conditions:
 *   - workspaceKey is one of 'workbench', 'market', 'arbitrage', 'compare'.
 *   - shouldFocus determines whether focus moves to the active tab button.
 * Post-conditions:
 *   - Sets aria-selected, tabindex, hidden on panels, replaces history URL,
 *     announces workspace switch, and triggers workspace lazy loading.
 *
 * @param {string} workspaceKey - Target workspace identifier.
 * @param {boolean} [shouldFocus=false] - Whether to focus tab button.
 */
export function switchWorkspace(workspaceKey, shouldFocus = false) {
  const validWorkspaces = ['workbench', 'market', 'arbitrage', 'compare'];
  if (!validWorkspaces.includes(workspaceKey)) {
    return;
  }
  state.activeWorkspace = workspaceKey;

  const tabWorkbench = document.getElementById('tab-workbench');
  const tabMarket = document.getElementById('tab-market');
  const tabArbitrage = document.getElementById('tab-arbitrage');
  const tabCompare = document.getElementById('tab-compare');

  const panelWorkbench = document.getElementById('workspace-workbench');
  const panelMarket = document.getElementById('workspace-market');
  const panelArbitrage = document.getElementById('workspace-arbitrage');
  const panelCompare = document.getElementById('workspace-compare');

  const tabs = [
    { key: 'workbench', tab: tabWorkbench, panel: panelWorkbench, label: 'Deal Workbench' },
    { key: 'market', tab: tabMarket, panel: panelMarket, label: 'Market Intelligence' },
    { key: 'arbitrage', tab: tabArbitrage, panel: panelArbitrage, label: 'Dealer and Channel Arbitrage' },
    { key: 'compare', tab: tabCompare, panel: panelCompare, label: 'Side-by-Side Comparator' },
  ];

  let activeTabEl = null;
  let activeLabel = 'Workspace';

  for (let i = 0; i < tabs.length; i++) {
    const item = tabs[i];
    const isActive = item.key === workspaceKey;
    if (item.tab) {
      item.tab.setAttribute('aria-selected', String(isActive));
      item.tab.setAttribute('tabindex', isActive ? '0' : '-1');
      if (isActive) {
        activeTabEl = item.tab;
        activeLabel = item.label;
      }
    }
    if (item.panel) {
      item.panel.hidden = !isActive;
    }
  }

  if (shouldFocus && activeTabEl) {
    activeTabEl.focus();
  }

  // Update query parameter ?workspace=<key> preserving other params
  try {
    const url = new URL(window.location.href);
    url.searchParams.set('workspace', workspaceKey);
    window.history.replaceState(null, '', url.toString());
  } catch (err) {
    console.warn('History replaceState failed', err);
  }

  announce(`Switched to ${activeLabel} workspace`);
  updateCompareTray();

  // Workspace lazy hydration
  if (workspaceKey === 'market') {
    loadMarketWorkspace();
  } else if (workspaceKey === 'arbitrage') {
    loadArbitrageWorkspace();
  } else if (workspaceKey === 'compare') {
    loadCompareWorkspace();
  }
}

/**
 * Handles keyboard arrow navigation across the primary workspace tablist.
 *
 * Pre-conditions:
 *   - e is a KeyboardEvent fired from a workspace tab button.
 * Post-conditions:
 *   - Implements roving tabindex for ArrowLeft, ArrowRight, Home, and End.
 *
 * @param {KeyboardEvent} e - Keydown event.
 */
export function handleWorkspaceTabKeydown(e) {
  const tabKeys = ['workbench', 'market', 'arbitrage', 'compare'];
  const tabWorkbench = document.getElementById('tab-workbench');
  const tabMarket = document.getElementById('tab-market');
  const tabArbitrage = document.getElementById('tab-arbitrage');
  const tabCompare = document.getElementById('tab-compare');
  const tabElements = [tabWorkbench, tabMarket, tabArbitrage, tabCompare];

  const currentIndex = tabKeys.indexOf(state.activeWorkspace);
  if (currentIndex === -1) {
    return;
  }

  let targetIndex = -1;
  if (e.key === 'ArrowRight') {
    e.preventDefault();
    targetIndex = (currentIndex + 1) % tabKeys.length;
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault();
    targetIndex = (currentIndex - 1 + tabKeys.length) % tabKeys.length;
  } else if (e.key === 'Home') {
    e.preventDefault();
    targetIndex = 0;
  } else if (e.key === 'End') {
    e.preventDefault();
    targetIndex = tabKeys.length - 1;
  }

  if (targetIndex !== -1) {
    const targetKey = tabKeys[targetIndex];
    switchWorkspace(targetKey, true);
    if (tabElements[targetIndex]) {
      tabElements[targetIndex].focus();
    }
  }
}

/**
 * Lazy loads and renders Market Intelligence workspace data (#workspace-market).
 *
 * Pre-conditions:
 *   - DOM element #workspace-market exists.
 *   - forceRefresh boolean determines whether to bypass memory caches.
 * Post-conditions:
 *   - Renders overview + cohorts data and instantiates pure SVG valuation frontier chart.
 *
 * @param {boolean} [forceRefresh=false] - Force cache bypass.
 */
export async function loadMarketWorkspace(forceRefresh = false) {
  const panel = document.getElementById('workspace-market');
  if (!panel) {
    return;
  }

  if (!forceRefresh && state.marketOverview && state.cohortsData) {
    renderMarketWorkspaceContent();
    return;
  }

  panel.innerHTML = renderMarketLoadingHtml();

  try {
    const cohortParam = encodeURIComponent(state.selectedCohortKey || 'ALL');
    const [ovResp, chResp] = await Promise.all([
      fetch('/api/market/overview', { headers: { Accept: 'application/json' } }),
      fetch(`/api/market/cohorts?cohort=${cohortParam}`, { headers: { Accept: 'application/json' } }),
    ]);

    if (!ovResp.ok || !chResp.ok) {
      throw new Error(`HTTP Error: overview=${ovResp.status}, cohorts=${chResp.status}`);
    }

    state.marketOverview = await ovResp.json();
    state.cohortsData = await chResp.json();
    renderMarketWorkspaceContent();
  } catch (err) {
    console.error('Failed to load market intelligence data', err);
    panel.innerHTML = renderWorkspaceErrorHtml('Failed to load market intelligence data.', 'retry-market');
  }
}

/**
 * Helper rendering populated Market Intelligence HTML and Frontier SVG chart.
 *
 * Pre-conditions:
 *   - state.marketOverview and state.cohortsData are loaded.
 * Post-conditions:
 *   - Injects HTML and calls renderFrontierChart with interactivity options.
 */
function renderMarketWorkspaceContent() {
  const panel = document.getElementById('workspace-market');
  if (!panel) {
    return;
  }

  panel.innerHTML = renderMarketWorkspaceHtml(
    state.marketOverview,
    state.cohortsData,
    state.selectedCohortKey,
    state.pinnedIds
  );

  const containerEl = document.getElementById('frontier-svg-container');
  const tooltipEl = document.getElementById('frontier-tooltip');
  const selectedCohort = state.cohortsData?.selected_cohort
    || state.cohortsData?.cohorts?.[state.selectedCohortKey]
    || state.cohortsData?.all_scatter
    || {};

  renderFrontierChart(containerEl, tooltipEl, selectedCohort, {
    pinnedIds: state.pinnedIds,
    onSelectListing: (listingId) => openAnalysisDrawer(listingId),
  });
}

/**
 * Lazy loads and renders Dealer & Channel Arbitrage workspace data (#workspace-arbitrage).
 *
 * Pre-conditions:
 *   - DOM element #workspace-arbitrage exists.
 * Post-conditions:
 *   - Fetches /api/market/dealers and renders platform comparisons and dealer matrix.
 *
 * @param {boolean} [forceRefresh=false] - Force cache bypass.
 */
export async function loadArbitrageWorkspace(forceRefresh = false) {
  const panel = document.getElementById('workspace-arbitrage');
  if (!panel) {
    return;
  }

  if (!forceRefresh && state.dealersData) {
    panel.innerHTML = renderArbitrageWorkspaceHtml(state.dealersData);
    return;
  }

  panel.innerHTML = renderMarketLoadingHtml();

  try {
    const resp = await fetch('/api/market/dealers', { headers: { Accept: 'application/json' } });
    if (!resp.ok) {
      throw new Error(`HTTP Error: dealers=${resp.status}`);
    }
    state.dealersData = await resp.json();
    panel.innerHTML = renderArbitrageWorkspaceHtml(state.dealersData);
  } catch (err) {
    console.error('Failed to load dealer arbitrage data', err);
    panel.innerHTML = renderWorkspaceErrorHtml('Failed to load dealer arbitrage data.', 'retry-arbitrage');
  }
}

/**
 * Lazy loads and renders Side-by-Side Comparator workspace data (#workspace-compare).
 *
 * Pre-conditions:
 *   - DOM element #workspace-compare exists.
 * Post-conditions:
 *   - Toggles outer toolbar, fetches /api/compare?ids=... when pins > 0, and renders matrix.
 *
 * @param {boolean} [forceRefresh=false] - Force cache bypass.
 */
export async function loadCompareWorkspace(forceRefresh = false) {
  const container = document.getElementById('compare-matrix-container');
  const outerToolbar = document.querySelector('#workspace-compare > .compare-toolbar');

  if (outerToolbar) {
    outerToolbar.hidden = state.pinnedIds.size > 0;
  }

  if (!container) {
    return;
  }

  if (state.pinnedIds.size === 0) {
    container.innerHTML = renderComparatorWorkspaceHtml({}, []);
    return;
  }

  if (!forceRefresh && state.compareData && state.compareData.deals) {
    const ids = Array.from(state.pinnedIds);
    const cachedIds = state.compareData.deals.map((d) => String(d.id || d.platform_id || d.vin));
    if (ids.length === cachedIds.length && ids.every((id) => cachedIds.includes(id))) {
      container.innerHTML = renderComparatorWorkspaceHtml(state.compareData, ids);
      return;
    }
  }

  container.innerHTML = renderCompareLoadingHtml();

  try {
    const idsParam = Array.from(state.pinnedIds).map(encodeURIComponent).join(',');
    const resp = await fetch(`/api/compare?ids=${idsParam}`, {
      headers: { Accept: 'application/json' },
    });
    if (!resp.ok) {
      throw new Error(`HTTP Error: compare=${resp.status}`);
    }
    state.compareData = await resp.json();
    container.innerHTML = renderComparatorWorkspaceHtml(state.compareData, Array.from(state.pinnedIds));
  } catch (err) {
    console.error('Failed to load comparison data', err);
    container.innerHTML = renderWorkspaceErrorHtml('Failed to load comparison data. Please try again.', 'retry-compare');
  }
}

/**
 * Fetches filtered and sorted vehicle listings from GET /api/deals and renders #deals-container.
 *
 * Pre-conditions:
 *   - state.filters contains active search and sorting criteria.
 * Post-conditions:
 *   - Updates state.deals and state.kpis, renders renderDealsSectionHtml, announces count.
 */
export async function fetchDeals() {
  const container = document.getElementById('deals-container');
  if (container) {
    container.innerHTML = renderWorkbenchLoadingHtml(state.filters.view);
  }

  const params = new URLSearchParams();
  for (const [key, val] of Object.entries(state.filters)) {
    if (val !== null && val !== undefined && val !== '') {
      params.set(key, String(val));
    }
  }

  try {
    const resp = await fetch(`/api/deals?${params.toString()}`, {
      headers: { Accept: 'application/json' },
    });
    if (!resp.ok) {
      throw new Error(`HTTP Error: deals=${resp.status}`);
    }
    const data = await resp.json();
    state.deals = Array.isArray(data.deals) ? data.deals : [];
    state.kpis = data.kpis || {};
    if (data.filters) {
      state.filters = Object.assign({}, state.filters, data.filters);
    }
    if (data.provenance) {
      state.provenance = data.provenance;
      syncDegradedBanner(data.provenance);
    }
    if (container) {
      container.innerHTML = renderDealsSectionHtml(state.deals, state.kpis, state.filters, state.pinnedIds);
    }
    updateCompareTray();
    announce(`Showing ${state.deals.length} listings in Deal Workbench`);
  } catch (err) {
    console.error('Failed to fetch deals', err);
    if (container) {
      container.innerHTML = renderWorkspaceErrorHtml('Failed to load listings. Please check connection and try again.', 'retry-deals');
    }
  }
}

/**
 * Performs optimistic bookmark or dismiss triage toggle with automatic rollback on failure.
 *
 * Pre-conditions:
 *   - listingId is a non-empty string.
 *   - action is 'bookmark' or 'dismiss'.
 * Post-conditions:
 *   - Optimistically updates listing flag and KPI counters in UI.
 *   - Dispatches POST /api/listing/{id}/{action} with Accept: application/json.
 *   - Reverts state and announces error notice if request fails.
 *
 * @param {string} listingId - Target vehicle listing identifier.
 * @param {string} action - 'bookmark' or 'dismiss'.
 */
export async function toggleUserFlag(listingId, action) {
  if (!listingId || (action !== 'bookmark' && action !== 'dismiss')) {
    return;
  }
  const strId = String(listingId);
  const deal = state.deals.find((d) => String(d.id || d.platform_id || d.vin) === strId);

  const prevBookmarked = deal ? Boolean(deal.is_bookmarked) : false;
  const prevDismissed = deal ? Boolean(deal.is_dismissed) : false;
  const prevKpis = Object.assign({}, state.kpis);

  // Apply optimistic mutation
  if (deal) {
    if (action === 'bookmark') {
      deal.is_bookmarked = !prevBookmarked;
      state.kpis.saved_count = Math.max(0, (state.kpis.saved_count || 0) + (deal.is_bookmarked ? 1 : -1));
      announce(deal.is_bookmarked ? 'Vehicle saved' : 'Vehicle removed from saved');
    } else if (action === 'dismiss') {
      deal.is_dismissed = !prevDismissed;
      state.kpis.dismissed_count = Math.max(0, (state.kpis.dismissed_count || 0) + (deal.is_dismissed ? 1 : -1));
      announce(deal.is_dismissed ? 'Vehicle hidden' : 'Vehicle restored');
    }
  }

  const container = document.getElementById('deals-container');
  if (container) {
    container.innerHTML = renderDealsSectionHtml(state.deals, state.kpis, state.filters, state.pinnedIds);
  }

  try {
    const resp = await fetch(`/api/listing/${encodeURIComponent(strId)}/${action}`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(state.filters),
    });

    if (!resp.ok) {
      throw new Error(`HTTP Error: toggle=${resp.status}`);
    }

    const data = await resp.json();
    if (data.kpis) {
      state.kpis = data.kpis;
    }
    if (deal && data.value !== undefined) {
      if (action === 'bookmark') {
        deal.is_bookmarked = Boolean(data.value);
      } else if (action === 'dismiss') {
        deal.is_dismissed = Boolean(data.value);
      }
    }
    if (container) {
      container.innerHTML = renderDealsSectionHtml(state.deals, state.kpis, state.filters, state.pinnedIds);
    }
  } catch (err) {
    console.error('Optimistic update failed, reverting state', err);
    if (deal) {
      deal.is_bookmarked = prevBookmarked;
      deal.is_dismissed = prevDismissed;
    }
    state.kpis = prevKpis;
    if (container) {
      container.innerHTML = renderDealsSectionHtml(state.deals, state.kpis, state.filters, state.pinnedIds);
    }
    announce(`Action failed: unable to update ${action}. State reverted.`);
  }
}

/**
 * Opens the slide-over valuation drawer (#analysis-drawer) with focus trap.
 *
 * Pre-conditions:
 *   - listingId is a non-empty string.
 * Post-conditions:
 *   - Stores lastFocusedTrigger, renders loading state, focuses close button,
 *     fetches /api/listings/{id}/analysis, and renders complete 7-section dossier.
 *
 * @param {string} listingId - Target vehicle listing identifier.
 */
export async function openAnalysisDrawer(listingId) {
  if (!listingId) {
    return;
  }
  const strId = String(listingId);
  if (state.activeDrawerRequestId === strId) {
    return;
  }
  state.activeDrawerRequestId = strId;
  state.lastFocusedTrigger = document.activeElement;

  const drawerEl = document.getElementById('analysis-drawer');
  if (!drawerEl) {
    return;
  }
  const backdropEl = document.getElementById('drawer-backdrop');
  const panelEl = drawerEl.querySelector('.drawer-panel');

  if (panelEl) {
    panelEl.innerHTML = `
      <div class="drawer-header p-4 border-b border-default flex items-center justify-between">
        <h2 id="drawer-title" class="drawer-title">Loading Vehicle Dossier...</h2>
        <button type="button" id="drawer-close-btn" class="drawer-close" data-action="close-drawer" aria-label="Close valuation drawer">&times;</button>
      </div>
      <div class="p-8 text-center text-muted">
        <div class="loading-skeleton p-6">Loading valuation analytics...</div>
      </div>
    `;
  }

  if (backdropEl) {
    backdropEl.hidden = false;
  }
  drawerEl.hidden = false;
  const initialCloseBtn = document.getElementById('drawer-close-btn');
  if (initialCloseBtn) {
    initialCloseBtn.focus();
  }

  try {
    const resp = await fetch(`/api/listings/${encodeURIComponent(strId)}/analysis`, {
      headers: { Accept: 'application/json' },
    });
    if (!resp.ok) {
      throw new Error(`HTTP Error: analysis=${resp.status}`);
    }
    const data = await resp.json();
    if (panelEl) {
      panelEl.innerHTML = renderAnalysisDrawerHtml(data, state.pinnedIds);
    }
    announce(`Opened valuation analysis for ${data.deal?.title || 'vehicle'}`);
    const closeBtn = document.getElementById('drawer-close-btn');
    if (closeBtn) {
      closeBtn.focus();
    }
  } catch (err) {
    console.error('Failed to load listing analysis', err);
    if (panelEl) {
      panelEl.innerHTML = `
        <div class="drawer-header p-4 border-b border-default flex items-center justify-between">
          <h2 id="drawer-title" class="drawer-title text-danger">Error Loading Dossier</h2>
          <button type="button" id="drawer-close-btn" class="drawer-close" data-action="close-drawer" aria-label="Close valuation drawer">&times;</button>
        </div>
        <div class="p-6">
          <p class="text-secondary text-sm">Failed to retrieve valuation analysis for this listing.</p>
          <button type="button" class="btn btn-secondary text-xs mt-4" data-action="retry-analysis" data-listing-id="${escapeHtml(strId)}">Retry</button>
        </div>
      `;
    }
    const closeBtn = document.getElementById('drawer-close-btn');
    if (closeBtn) {
      closeBtn.focus();
    }
  } finally {
    if (state.activeDrawerRequestId === strId) {
      state.activeDrawerRequestId = null;
    }
  }
}

/**
 * Closes the slide-over valuation drawer and restores trigger focus.
 *
 * Pre-conditions:
 *   - None.
 * Post-conditions:
 *   - Hides #analysis-drawer and #drawer-backdrop and restores focus to state.lastFocusedTrigger.
 */
export function closeAnalysisDrawer() {
  const drawerEl = document.getElementById('analysis-drawer');
  if (drawerEl) {
    drawerEl.hidden = true;
  }
  const backdropEl = document.getElementById('drawer-backdrop');
  if (backdropEl) {
    backdropEl.hidden = true;
  }
  if (state.lastFocusedTrigger && typeof state.lastFocusedTrigger.focus === 'function') {
    try {
      state.lastFocusedTrigger.focus();
    } catch (err) {
      console.warn('Failed to restore focus', err);
    }
  }
}

/**
 * Traps Tab and Shift+Tab key navigation inside the open valuation drawer.
 *
 * Pre-conditions:
 *   - e is a KeyboardEvent.
 * Post-conditions:
 *   - Wraps focus to keep it strictly contained inside #analysis-drawer.
 *
 * @param {KeyboardEvent} e - Keydown event.
 */
export function trapFocusInDrawer(e) {
  const drawerEl = document.getElementById('analysis-drawer');
  if (!drawerEl || drawerEl.hidden) {
    return;
  }
  if (e.key !== 'Tab') {
    return;
  }

  const focusable = drawerEl.querySelectorAll(
    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
  );
  if (focusable.length === 0) {
    return;
  }

  const first = focusable[0];
  const last = focusable[focusable.length - 1];

  if (e.shiftKey) {
    if (document.activeElement === first) {
      e.preventDefault();
      last.focus();
    }
  } else {
    if (document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
}

/**
 * Formats and copies comparison data as a high-density Markdown table.
 *
 * Pre-conditions:
 *   - state.compareData is loaded or populated from state.deals.
 * Post-conditions:
 *   - Copies table to navigator.clipboard and announces success to screen reader.
 */
export function copyCompareMarkdown() {
  const deals = state.compareData?.deals || state.compareData?.items || [];
  if (!deals || deals.length === 0) {
    announce('No comparison data available to copy.');
    return;
  }

  const headers = ['Dimension', ...deals.map((d, i) => d.title || `Vehicle ${i + 1}`)];
  const rows = [
    ['Price', ...deals.map((d) => formatCurrency(d.price))],
    ['Est. FMV', ...deals.map((d) => formatCurrency(d.market_value))],
    ['Delta vs FMV', ...deals.map((d) => formatSignedCurrency(d.price_delta))],
    ['Mileage', ...deals.map((d) => `${formatNumber(d.mileage)} mi`)],
    ['Deal Score', ...deals.map((d) => Number(d.deal_score || 0).toFixed(1))],
    ['Days on Market', ...deals.map((d) => `${d.days_on_market ?? 'N/A'}d`)],
    ['VIN', ...deals.map((d) => d.vin || 'N/A')],
    ['Platform', ...deals.map((d) => (d.platform || 'N/A').toUpperCase())],
    ['Dealer', ...deals.map((d) => d.seller_name || 'N/A')],
    ['Location', ...deals.map((d) => d.location_city || 'N/A')],
  ];

  const markdown = [
    `# Side-by-Side EV Comparison (${deals.length} Vehicles)`,
    '',
    `| ${headers.join(' | ')} |`,
    `| ${headers.map(() => '---').join(' | ')} |`,
    ...rows.map((row) => `| ${row.join(' | ')} |`),
    '',
  ].join('\n');

  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    navigator.clipboard.writeText(markdown)
      .then(() => announce('Comparison markdown summary copied to clipboard'))
      .catch(() => announce('Failed to copy markdown to clipboard'));
  } else {
    announce('Clipboard API unavailable');
  }
}

/**
 * Copies a 17-character VIN string to the system clipboard and announces it.
 *
 * Pre-conditions:
 *   - vin is a string.
 * Post-conditions:
 *   - Writes VIN to clipboard and updates live announcer.
 *
 * @param {string} vin - Vehicle Identification Number.
 */
export function copyVin(vin) {
  if (!vin) {
    return;
  }
  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    navigator.clipboard.writeText(vin)
      .then(() => announce(`VIN ${vin} copied to clipboard`))
      .catch(() => announce(`Failed to copy VIN ${vin}`));
  } else {
    announce(`VIN ${vin}`);
  }
}

/**
 * Synchronizes the degraded/offline fallback banner (#degraded-banner) with provenance metadata.
 *
 * Pre-conditions:
 *   - provenance is an object describing mode ('timescaledb', 'offline-sample', or 'fixture').
 * Post-conditions:
 *   - Updates #degraded-banner markup and toggles its hidden state dynamically.
 *
 * @param {object} provenance - Backend telemetry provenance metadata.
 */
export function syncDegradedBanner(provenance) {
  const el = document.getElementById('degraded-banner');
  if (!el) {
    return;
  }
  const prov = provenance || {};
  const mode = prov.mode || '';
  if (mode === 'offline-sample') {
    const temp = document.createElement('div');
    temp.innerHTML = renderDegradedBannerHtml(prov);
    const rendered = temp.firstElementChild;
    if (rendered) {
      el.innerHTML = rendered.innerHTML;
      el.className = rendered.className;
      el.hidden = false;
    }
  } else {
    el.hidden = true;
  }
}

/**
 * Checks database connectivity via GET /api/health for degraded mode recovery.
 *
 * Pre-conditions:
 *   - /api/health endpoint is reachable.
 * Post-conditions:
 *   - If mode is nominal, reloads the page; otherwise updates degraded banner and notifies operator.
 */
export async function checkLiveStatus() {
  try {
    const resp = await fetch('/api/health');
    const data = await resp.json();
    const prov = data.provenance || { mode: data.mode || '' };
    state.provenance = prov;
    syncDegradedBanner(prov);
    const mode = prov.mode || '';
    if (mode === 'timescaledb') {
      window.location.reload();
    } else {
      announce('Database still offline. Operating in sample mode.');
    }
  } catch (err) {
    console.warn('Live health check failed', err);
    announce('Connection check failed.');
  }
}

/**
 * Acknowledges and dismisses the degraded mode notice (#degraded-banner).
 *
 * Pre-conditions:
 *   - DOM element #degraded-banner exists.
 * Post-conditions:
 *   - Hides banner element.
 */
export function acknowledgeDegradedBanner() {
  const el = document.getElementById('degraded-banner');
  if (el) {
    el.hidden = true;
  }
}

/**
 * Intercepts scan submission form (#scan-trigger-form) and polls Temporal status.
 *
 * Pre-conditions:
 *   - e is an Event from form submission.
 * Post-conditions:
 *   - Submits POST /api/scan, displays banner, polls every 2000ms until complete.
 *
 * @param {Event} e - Submit event.
 */
export async function triggerScan(e) {
  if (e) {
    e.preventDefault();
  }
  const select = document.getElementById('scan-target-select');
  const target = select ? select.value : 'ALL';
  const submitBtn = document.getElementById('scan-submit-btn');
  const banner = document.getElementById('scan-status-banner');

  if (submitBtn) {
    submitBtn.disabled = true;
  }
  if (banner) {
    banner.hidden = false;
    banner.innerHTML = renderScanStatusBannerHtml({ status: 'submitting', target_model: target });
  }

  try {
    const formData = new URLSearchParams();
    formData.set('target', target);

    const resp = await fetch('/api/scan?format=json', {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData.toString(),
    });

    const data = await resp.json();

    if (!resp.ok || data.started === false || data.status === 'unavailable' || !data.workflow_id) {
      if (submitBtn) {
        submitBtn.disabled = false;
      }
      if (banner) {
        banner.innerHTML = renderScanStatusBannerHtml(
          {
            status: 'unavailable',
            target_model: target,
            message: data.error || data.message || 'Temporal server unreachable',
          },
          data.temporal_ui_url || null
        );
      }
      announce('Marketplace scan unavailable: Temporal cluster is offline.');
      return;
    }

    const wfId = data.workflow_id;
    if (banner) {
      banner.innerHTML = renderScanStatusBannerHtml(
        {
          status: 'running',
          workflow_id: wfId,
          target_model: target,
          scraped_count: 0,
          scored_count: 0,
          top_deals_count: 0,
        },
        data.temporal_ui_url || null
      );
    }

    if (state.scanIntervalId) {
      clearInterval(state.scanIntervalId);
    }

    state.scanIntervalId = setInterval(async () => {
      try {
        const pollResp = await fetch(`/api/scan/${encodeURIComponent(wfId)}/status?format=json`, {
          headers: { Accept: 'application/json' },
        });
        const pollData = await pollResp.json();
        const summary = pollData.summary || pollData || {};
        const scrapedCount = summary.total_scraped ?? summary.scraped_count ?? 0;
        const scoredCount = summary.total_scored ?? summary.scored_count ?? 0;
        const topDealsCount = summary.deals_found ?? summary.top_deals_count ?? 0;
        const isCompleted = Boolean(summary.is_completed || pollData.is_completed || summary.status === 'completed');
        const scanErr = summary.error || pollData.error;
        const bannerState = {
          status: scanErr ? 'error' : (isCompleted ? 'completed' : (summary.status || 'running')),
          workflow_id: wfId,
          target_model: target,
          elapsed_seconds: summary.elapsed_seconds,
          scraped_count: scrapedCount,
          scored_count: scoredCount,
          top_deals_count: topDealsCount,
          message: scanErr || summary.message || '',
        };
        if (banner) {
          banner.innerHTML = renderScanStatusBannerHtml(bannerState, pollData.temporal_ui_url || null);
        }

        if (isCompleted) {
          clearInterval(state.scanIntervalId);
          state.scanIntervalId = null;
          if (submitBtn) {
            submitBtn.disabled = false;
          }
          fetchDeals();
          if (state.activeWorkspace === 'market') {
            loadMarketWorkspace(true);
          } else if (state.activeWorkspace === 'arbitrage') {
            loadArbitrageWorkspace(true);
          } else if (state.activeWorkspace === 'compare') {
            loadCompareWorkspace(true);
          }
          announce(`Scan completed: scraped ${scrapedCount} listings`);
        } else if (scanErr || bannerState.status === 'error' || bannerState.status === 'unavailable') {
          clearInterval(state.scanIntervalId);
          state.scanIntervalId = null;
          if (submitBtn) {
            submitBtn.disabled = false;
          }
          announce(`Scan terminated: ${bannerState.message || 'Workflow finished with notice'}`);
        }
      } catch (pollErr) {
        console.error('Scan polling error', pollErr);
        clearInterval(state.scanIntervalId);
        state.scanIntervalId = null;
        if (submitBtn) {
          submitBtn.disabled = false;
        }
      }
    }, SCAN_POLL_INTERVAL_MS);
  } catch (err) {
    console.error('Scan trigger request failed', err);
    if (submitBtn) {
      submitBtn.disabled = false;
    }
    if (banner) {
      banner.innerHTML = renderScanStatusBannerHtml({
        status: 'error',
        target_model: target,
        message: 'Network request to scan controller failed',
      });
    }
  }
}

/**
 * Resets all workbench filters to nominal defaults and updates the UI.
 *
 * Pre-conditions:
 *   - None.
 * Post-conditions:
 *   - Clears search inputs, resets selects, and re-queries /api/deals.
 */
export function resetAllFilters() {
  state.filters.q = '';
  state.filters.make = '';
  state.filters.max_price = '';
  state.filters.max_mileage = '';
  state.filters.max_distance = '';
  state.filters.sort = 'score_desc';
  state.filters.tab = 'all';
  state.filters.view = 'grid';

  const searchInput = document.getElementById('search-input');
  if (searchInput) searchInput.value = '';

  const makeSelect = document.getElementById('make-select');
  if (makeSelect) makeSelect.value = '';

  const priceSelect = document.getElementById('max-price-select');
  if (priceSelect) priceSelect.value = '';

  const mileageSelect = document.getElementById('max-mileage-select');
  if (mileageSelect) mileageSelect.value = '';

  const distanceSelect = document.getElementById('max-distance-select');
  if (distanceSelect) distanceSelect.value = '';

  const sortSelect = document.getElementById('sort-select');
  if (sortSelect) sortSelect.value = 'score_desc';

  const tabInput = document.getElementById('tab-input');
  if (tabInput) tabInput.value = 'all';

  const viewInput = document.getElementById('view-input');
  if (viewInput) viewInput.value = 'grid';

  const gridBtn = document.getElementById('view-grid-btn');
  const tableBtn = document.getElementById('view-table-btn');
  if (gridBtn) gridBtn.setAttribute('aria-pressed', 'true');
  if (tableBtn) tableBtn.setAttribute('aria-pressed', 'false');

  fetchDeals();
}

/**
 * Toggles column sort order in table view.
 *
 * Pre-conditions:
 *   - sortKey is a valid sort descriptor string.
 * Post-conditions:
 *   - Toggles asc/desc or sets new sort, updates #sort-select, and refetches deals.
 *
 * @param {string} sortKey - Target sort parameter.
 */
export function toggleSort(sortKey) {
  if (!sortKey) {
    return;
  }
  let newSort = sortKey;
  if (state.filters.sort === sortKey) {
    if (sortKey.endsWith('_asc')) {
      newSort = sortKey.replace('_asc', '_desc');
    } else if (sortKey.endsWith('_desc')) {
      newSort = sortKey.replace('_desc', '_asc');
    }
  }
  state.filters.sort = newSort;

  const sortSelect = document.getElementById('sort-select');
  if (sortSelect) {
    let optionExists = false;
    for (let i = 0; i < sortSelect.options.length; i++) {
      if (sortSelect.options[i].value === newSort) {
        optionExists = true;
        break;
      }
    }
    if (optionExists) {
      sortSelect.value = newSort;
    }
  }

  fetchDeals();
}

/**
 * Global click event delegation router.
 *
 * Pre-conditions:
 *   - e is a MouseEvent.
 * Post-conditions:
 *   - Delegates user actions based on [data-action], prevents default where required.
 *
 * @param {MouseEvent} e - Click event.
 */
export function handleDocumentClick(e) {
  // Backdrop click closes drawer
  if (e.target.id === 'drawer-backdrop' || e.target.classList.contains('drawer-backdrop')) {
    closeAnalysisDrawer();
    return;
  }

  const target = e.target.closest('[data-action], [data-retry-action], .triage-tab, .sort-btn');
  if (!target) {
    return;
  }

  // Handle triage tabs
  if (target.classList.contains('triage-tab')) {
    e.preventDefault();
    const tabKey = target.getAttribute('data-tab');
    if (tabKey) {
      window.setFilterTab(tabKey);
    }
    return;
  }

  // Handle sort buttons
  if (target.classList.contains('sort-btn')) {
    e.preventDefault();
    const sortKey = target.getAttribute('data-sort');
    if (sortKey) {
      toggleSort(sortKey);
    }
    return;
  }

  const action = target.getAttribute('data-action') || target.getAttribute('data-retry-action');
  if (!action) {
    return;
  }

  switch (action) {
    case 'bookmark': {
      e.preventDefault();
      const lid = target.getAttribute('data-listing-id');
      toggleUserFlag(lid, 'bookmark');
      break;
    }
    case 'dismiss': {
      e.preventDefault();
      const lid = target.getAttribute('data-listing-id');
      toggleUserFlag(lid, 'dismiss');
      break;
    }
    case 'pin': {
      e.preventDefault();
      const lid = target.getAttribute('data-listing-id');
      togglePin(lid);
      break;
    }
    case 'unpin': {
      e.preventDefault();
      const lid = target.getAttribute('data-listing-id');
      unpinListing(lid);
      break;
    }
    case 'clear-pins': {
      e.preventDefault();
      clearAllPins();
      break;
    }
    case 'analyze': {
      e.preventDefault();
      const lid = target.getAttribute('data-listing-id');
      openAnalysisDrawer(lid);
      break;
    }
    case 'copy-vin': {
      e.preventDefault();
      const vin = target.getAttribute('data-vin') || target.textContent.trim();
      copyVin(vin);
      break;
    }
    case 'close-drawer': {
      e.preventDefault();
      closeAnalysisDrawer();
      break;
    }
    case 'switch-workspace': {
      e.preventDefault();
      const ws = target.getAttribute('data-workspace');
      if (ws) {
        switchWorkspace(ws, true);
      }
      break;
    }
    case 'subtab':
    case 'set-tab': {
      e.preventDefault();
      const tabKey = target.getAttribute('data-tab');
      if (tabKey) {
        window.setFilterTab(tabKey);
      }
      break;
    }
    case 'reset-filters': {
      e.preventDefault();
      resetAllFilters();
      break;
    }
    case 'copy-compare-markdown': {
      e.preventDefault();
      copyCompareMarkdown();
      break;
    }
    case 'filter-workbench': {
      e.preventDefault();
      const make = target.getAttribute('data-make') || '';
      const model = target.getAttribute('data-model') || '';
      const combined = model ? `${make} ${model}`.trim() : make;
      switchWorkspace('workbench', true);
      const makeSelect = document.getElementById('make-select');
      const searchInput = document.getElementById('search-input');
      let selectedMakeVal = make;
      let queryVal = '';
      if (makeSelect && combined) {
        const hasCombined = Array.from(makeSelect.options).some((opt) => opt.value === combined);
        if (hasCombined) {
          selectedMakeVal = combined;
        } else if (model) {
          queryVal = model;
        }
      }
      state.filters.make = selectedMakeVal;
      state.filters.q = queryVal;
      if (makeSelect) {
        makeSelect.value = selectedMakeVal;
      }
      if (searchInput) {
        searchInput.value = queryVal;
      }
      fetchDeals();
      break;
    }
    case 'plot-frontier': {
      e.preventDefault();
      const cohort = target.getAttribute('data-cohort-key') || target.getAttribute('data-cohort');
      if (cohort) {
        state.selectedCohortKey = cohort;
        loadMarketWorkspace(true);
      }
      break;
    }
    case 'filter-distance': {
      e.preventDefault();
      const maxDist = target.getAttribute('data-max-distance');
      switchWorkspace('workbench', true);
      state.filters.max_distance = maxDist || '';
      const distSelect = document.getElementById('max-distance-select');
      if (distSelect) {
        distSelect.value = maxDist || '';
      }
      fetchDeals();
      break;
    }
    case 'filter-dealer': {
      e.preventDefault();
      const dealer = target.getAttribute('data-dealer');
      switchWorkspace('workbench', true);
      state.filters.q = dealer || '';
      const searchInput = document.getElementById('search-input');
      if (searchInput) {
        searchInput.value = dealer || '';
      }
      fetchDeals();
      break;
    }
    case 'retry-connection': {
      e.preventDefault();
      checkLiveStatus();
      break;
    }
    case 'acknowledge-degraded': {
      e.preventDefault();
      acknowledgeDegradedBanner();
      break;
    }
    case 'retry-deals': {
      e.preventDefault();
      fetchDeals();
      break;
    }
    case 'retry-market': {
      e.preventDefault();
      loadMarketWorkspace(true);
      break;
    }
    case 'retry-arbitrage': {
      e.preventDefault();
      loadArbitrageWorkspace(true);
      break;
    }
    case 'retry-compare': {
      e.preventDefault();
      loadCompareWorkspace(true);
      break;
    }
    case 'retry-analysis': {
      e.preventDefault();
      const lid = target.getAttribute('data-listing-id');
      openAnalysisDrawer(lid);
      break;
    }
    case 'retry-scan': {
      e.preventDefault();
      triggerScan();
      break;
    }
    case 'dismiss-scan-banner': {
      e.preventDefault();
      if (state.scanIntervalId) {
        clearInterval(state.scanIntervalId);
        state.scanIntervalId = null;
      }
      const banner = document.getElementById('scan-status-banner');
      if (banner) {
        banner.innerHTML = '';
        banner.hidden = true;
      }
      break;
    }
    default:
      break;
  }
}

/**
 * Handles global document keyboard shortcuts: Escape, /, and Cmd/Ctrl+K.
 *
 * Pre-conditions:
 *   - e is a KeyboardEvent.
 * Post-conditions:
 *   - Closes drawer on Escape, or routes / and Cmd+K to search input.
 *
 * @param {KeyboardEvent} e - Keydown event.
 */
export function handleGlobalKeydown(e) {
  if (e.key === 'Escape') {
    const drawerEl = document.getElementById('analysis-drawer');
    if (drawerEl && !drawerEl.hidden) {
      e.preventDefault();
      closeAnalysisDrawer();
      return;
    }
    const tooltipEl = document.getElementById('frontier-tooltip');
    if (tooltipEl && !tooltipEl.hidden) {
      tooltipEl.hidden = true;
    }
    return;
  }

  const isFormElement = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)
    || document.activeElement?.isContentEditable;

  if (e.key === '/' && !isFormElement) {
    e.preventDefault();
    if (state.activeWorkspace !== 'workbench') {
      switchWorkspace('workbench');
    }
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
      searchInput.focus();
      searchInput.select();
    }
    return;
  }

  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    if (state.activeWorkspace !== 'workbench') {
      switchWorkspace('workbench');
    }
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
      searchInput.focus();
      searchInput.select();
    }
  }
}

/**
 * Exposes backwards-compatible global helpers onto window for legacy inline callers.
 *
 * Pre-conditions:
 *   - window object is defined.
 * Post-conditions:
 *   - Sets window.setFilterTab, window.toggleViewMode, window.openModal, window.closeModal.
 */
export function registerWindowHelpers() {
  window.setFilterTab = function (tabName) {
    state.filters.tab = tabName || 'all';
    const tabInput = document.getElementById('tab-input');
    if (tabInput) {
      tabInput.value = state.filters.tab;
    }
    fetchDeals();
  };

  window.toggleViewMode = function (mode) {
    state.filters.view = mode === 'table' ? 'table' : 'grid';
    const viewInput = document.getElementById('view-input');
    if (viewInput) {
      viewInput.value = state.filters.view;
    }
    const gridBtn = document.getElementById('view-grid-btn');
    const tableBtn = document.getElementById('view-table-btn');
    if (gridBtn) {
      gridBtn.setAttribute('aria-pressed', String(state.filters.view === 'grid'));
    }
    if (tableBtn) {
      tableBtn.setAttribute('aria-pressed', String(state.filters.view === 'table'));
    }
    const container = document.getElementById('deals-container');
    if (container) {
      container.innerHTML = renderDealsSectionHtml(state.deals, state.kpis, state.filters, state.pinnedIds);
    }
  };

  window.openModal = function (listingId) {
    const fallbackId = state.deals && state.deals.length > 0
      ? String(state.deals[0].id || state.deals[0].platform_id || state.deals[0].vin || '')
      : '';
    const targetId = listingId || document.activeElement?.getAttribute('data-listing-id') || fallbackId;
    if (targetId) {
      openAnalysisDrawer(targetId);
      return;
    }
    const drawer = document.getElementById('analysis-drawer');
    const backdrop = document.getElementById('drawer-backdrop');
    const panelEl = drawer ? drawer.querySelector('.drawer-panel') : null;
    if (panelEl) {
      panelEl.innerHTML = `
        <div class="drawer-header p-4 border-b border-default flex items-center justify-between">
          <h2 id="drawer-title" class="drawer-title">Vehicle Valuation Dossier</h2>
          <button type="button" id="drawer-close-btn" class="drawer-close" data-action="close-drawer" aria-label="Close valuation drawer">&times;</button>
        </div>
        <div class="p-6 text-secondary text-sm">Select a vehicle from the Deal Workbench to inspect its valuation dossier.</div>
      `;
    }
    if (backdrop) backdrop.hidden = false;
    if (drawer) drawer.hidden = false;
  };

  window.closeModal = function () {
    closeAnalysisDrawer();
  };
}

/**
 * Handles ArrowLeft/ArrowRight/Home/End keyboard navigation across workbench triage sub-tabs.
 *
 * Pre-conditions:
 *   - e is a KeyboardEvent fired inside .triage-tabs.
 * Post-conditions:
 *   - Moves focus across .triage-tab elements with roving tabindex and triggers tab activation.
 *
 * @param {KeyboardEvent} e - Keydown event.
 */
export function handleTriageTabKeydown(e) {
  const tabEl = e.target?.closest ? e.target.closest('.triage-tab') : null;
  if (!tabEl) {
    return;
  }
  const tabList = tabEl.closest('.triage-tabs');
  if (!tabList) {
    return;
  }
  const tabs = Array.from(tabList.querySelectorAll('.triage-tab'));
  const currentIdx = tabs.indexOf(tabEl);
  if (currentIdx === -1 || tabs.length === 0) {
    return;
  }

  let nextIdx = -1;
  if (e.key === 'ArrowRight') {
    nextIdx = (currentIdx + 1) % tabs.length;
  } else if (e.key === 'ArrowLeft') {
    nextIdx = (currentIdx - 1 + tabs.length) % tabs.length;
  } else if (e.key === 'Home') {
    nextIdx = 0;
  } else if (e.key === 'End') {
    nextIdx = tabs.length - 1;
  } else {
    return;
  }

  e.preventDefault();
  tabs.forEach((btn, idx) => btn.setAttribute('tabindex', idx === nextIdx ? '0' : '-1'));
  const nextTab = tabs[nextIdx];
  nextTab.focus();
  const tabKey = nextTab.getAttribute('data-tab');
  if (tabKey) {
    window.setFilterTab(tabKey);
  }
}

/**
 * Synchronizes Workbench DOM controls with hydrated state.filters.
 *
 * Pre-conditions:
 *   - state.filters is populated.
 * Post-conditions:
 *   - Input values and view toggle aria-pressed match state.filters.
 */
function syncFilterControlsUI() {
  const f = state.filters || {};
  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el && val !== undefined && val !== null) {
      el.value = String(val);
    }
  };
  setVal('search-input', f.q || '');
  setVal('make-select', f.make || '');
  setVal('max-price-select', f.max_price || '');
  setVal('max-mileage-select', f.max_mileage || '');
  setVal('max-distance-select', f.max_distance || '');
  setVal('sort-select', f.sort || 'score_desc');
  setVal('tab-input', f.tab || 'all');
  setVal('view-input', f.view || 'grid');

  const viewMode = f.view === 'table' ? 'table' : 'grid';
  const gridBtn = document.getElementById('view-grid-btn');
  const tableBtn = document.getElementById('view-table-btn');
  if (gridBtn) gridBtn.setAttribute('aria-pressed', String(viewMode === 'grid'));
  if (tableBtn) tableBtn.setAttribute('aria-pressed', String(viewMode === 'table'));
}

/**
 * Initializes the dashboard client application on DOMContentLoaded.
 *
 * Pre-conditions:
 *   - DOM structure matching index.html is loaded.
 * Post-conditions:
 *   - Parses initial state JSON, restores compare pins, binds event listeners,
 *     and activates initial workspace.
 */
export function init() {
  // 1. Parse initial state JSON
  const initialStateEl = document.getElementById('initial-state');
  if (initialStateEl && initialStateEl.textContent) {
    try {
      const raw = JSON.parse(initialStateEl.textContent);
      state.deals = Array.isArray(raw.deals) ? raw.deals : [];
      state.kpis = raw.kpis || {};
      state.filters = Object.assign({}, state.filters, raw.filters || {});
      state.provenance = raw.provenance || {};
      state.marketOverview = raw.market_overview || null;
    } catch (err) {
      console.error('Failed to parse initial-state JSON', err);
    }
  }

  // 2. Restore pins and synchronize initial filter/banner UI
  loadPinsFromStorage();
  updateCompareTabBadge();
  updateCompareTray();
  updatePinButtonsUI();
  syncFilterControlsUI();
  syncDegradedBanner(state.provenance);

  // 3. Register legacy helpers
  registerWindowHelpers();

  // 4. Bind primary workspace tab controls
  const tablist = document.querySelector('.workspace-tablist');
  if (tablist) {
    tablist.addEventListener('keydown', handleWorkspaceTabKeydown);
  }

  const tabWorkbench = document.getElementById('tab-workbench');
  if (tabWorkbench) {
    tabWorkbench.addEventListener('click', () => switchWorkspace('workbench'));
  }
  const tabMarket = document.getElementById('tab-market');
  if (tabMarket) {
    tabMarket.addEventListener('click', () => switchWorkspace('market'));
  }
  const tabArbitrage = document.getElementById('tab-arbitrage');
  if (tabArbitrage) {
    tabArbitrage.addEventListener('click', () => switchWorkspace('arbitrage'));
  }
  const tabCompare = document.getElementById('tab-compare');
  if (tabCompare) {
    tabCompare.addEventListener('click', () => switchWorkspace('compare'));
  }

  // 5. Bind filter form controls
  const filterForm = document.getElementById('filter-form');
  if (filterForm) {
    filterForm.addEventListener('submit', (e) => {
      e.preventDefault();
      fetchDeals();
    });
  }

  const searchInput = document.getElementById('search-input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(() => {
        state.filters.q = e.target.value.trim();
        fetchDeals();
      }, SEARCH_DEBOUNCE_MS);
    });
  }

  const makeSelect = document.getElementById('make-select');
  if (makeSelect) {
    makeSelect.addEventListener('change', (e) => {
      state.filters.make = e.target.value;
      fetchDeals();
    });
  }

  const priceSelect = document.getElementById('max-price-select');
  if (priceSelect) {
    priceSelect.addEventListener('change', (e) => {
      state.filters.max_price = e.target.value;
      fetchDeals();
    });
  }

  const mileageSelect = document.getElementById('max-mileage-select');
  if (mileageSelect) {
    mileageSelect.addEventListener('change', (e) => {
      state.filters.max_mileage = e.target.value;
      fetchDeals();
    });
  }

  const distanceSelect = document.getElementById('max-distance-select');
  if (distanceSelect) {
    distanceSelect.addEventListener('change', (e) => {
      state.filters.max_distance = e.target.value;
      fetchDeals();
    });
  }

  const sortSelect = document.getElementById('sort-select');
  if (sortSelect) {
    sortSelect.addEventListener('change', (e) => {
      state.filters.sort = e.target.value;
      fetchDeals();
    });
  }

  const viewGridBtn = document.getElementById('view-grid-btn');
  if (viewGridBtn) {
    viewGridBtn.addEventListener('click', () => window.toggleViewMode('grid'));
  }
  const viewTableBtn = document.getElementById('view-table-btn');
  if (viewTableBtn) {
    viewTableBtn.addEventListener('click', () => window.toggleViewMode('table'));
  }
  const resetBtn = document.getElementById('reset-filters-btn');
  if (resetBtn) {
    resetBtn.addEventListener('click', resetAllFilters);
  }

  // 6. Bind scan trigger form
  const scanForm = document.getElementById('scan-trigger-form');
  if (scanForm) {
    scanForm.addEventListener('submit', triggerScan);
  }

  // 7. Bind clear pins button in compare workspace
  const compareClearBtn = document.getElementById('compare-clear-btn');
  if (compareClearBtn) {
    compareClearBtn.addEventListener('click', clearAllPins);
  }

  // 8. Bind drawer close button
  const drawerCloseBtn = document.getElementById('drawer-close-btn');
  if (drawerCloseBtn) {
    drawerCloseBtn.addEventListener('click', closeAnalysisDrawer);
  }

  // 9. Bind Market workspace cohort change listener
  const marketPanel = document.getElementById('workspace-market');
  if (marketPanel) {
    marketPanel.addEventListener('change', (e) => {
      if (e.target && e.target.id === 'cohort-select') {
        state.selectedCohortKey = e.target.value;
        loadMarketWorkspace(true);
      }
    });
  }

  // 10. Global document listeners (click, keyboard shortcuts, focus trapping, triage roving tabindex)
  document.addEventListener('click', handleDocumentClick);
  document.addEventListener('keydown', handleGlobalKeydown);
  document.addEventListener('keydown', trapFocusInDrawer);
  const dealsContainer = document.getElementById('deals-container');
  if (dealsContainer) {
    dealsContainer.addEventListener('keydown', handleTriageTabKeydown);
  }

  // 11. Read ?workspace=... URL parameter and activate workspace
  const urlParams = new URLSearchParams(window.location.search);
  const initialWorkspace = urlParams.get('workspace') || 'workbench';
  if (['workbench', 'market', 'arbitrage', 'compare'].includes(initialWorkspace)) {
    switchWorkspace(initialWorkspace, false);
  } else {
    switchWorkspace('workbench', false);
  }
}

// Auto-bootstrap when document is ready
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}
