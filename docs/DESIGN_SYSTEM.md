# Design System Specification: Automotive Telemetry & Quantitative Valuation Desk

**Version:** `2.0.0` (`v2-market-intelligence`)  
**Target Assets:** `src/dashboard/static/tokens.css`, `src/dashboard/static/components.css`  
**Upstream Specs:** [`docs/MARKET_ANALYSIS_SPEC.md`](file:///home/tron/workspace/car-researcher/docs/MARKET_ANALYSIS_SPEC.md), [`docs/UX_SPEC.md`](file:///home/tron/workspace/car-researcher/docs/UX_SPEC.md), [`src/dashboard/templates.py`](file:///home/tron/workspace/car-researcher/src/dashboard/templates.py)

---

## 1. Aesthetic Direction & Architectural Principles

The `car-researcher` dashboard operates as a **Precision Automotive Telemetry & Quantitative Valuation Desk**. It treats Bay Area EV inventory as an empirical financial asset class tracked against TimescaleDB snapshots, cohort percentiles, OLS depreciation frontiers, and federal NHTSA/EPA telemetry.

### Core Visual Principles
1. **Dark Graphite-Slate Surface Discipline**: Four intentional dark elevation tiers (`#080B10` -> `#0F141C` -> `#151C26` -> `#1B2330`) separated by `1px` structural hairlines rather than drop-shadow haze or blurred decorative gradients.
2. **Restrained Precision Accents**: Cool steel-blue (`#0EA5E9` / `#38BDF8`) and instrument cyan (`#22D3EE`) denote interactive controls, active telemetry links, and OLS regression trendlines. Semantic color is reserved exclusively for empirical valuation alpha, liquidity risk, price-cut momentum, and safety posture.
3. **Tabular Numeric Rigor**: Every price, FMV delta, cohort percentile (`P10`/`P25`/`P50`/`P75`), `$/1k mi` metric, deal score, leverage score, odometer reading, distance, days on market (DOM), 3-year TCO projection, EPA MPGe/range, and 17-character VIN enforces `font-variant-numeric: tabular-nums` so columns align vertically and remain jitter-free across HTMX updates.
4. **Zero-CDN Self-Contained Styling**: All production UI rules live locally in `src/dashboard/static/tokens.css` and `src/dashboard/static/components.css`, removing dependency on external runtime Tailwind CDN scripts and eliminating unstyled flash or external egress failures.

### Explicit Anti-Patterns & Iconography Rule
- **No Generic Purple-Gradient SaaS Aesthetics**: Legacy `indigo-600` fills, glowing shadow blobs, and radial hero gradients from v1 `templates.py` are strictly prohibited.
- **Strictly Zero Emojis**: Unicode pictographs/emojis previously embedded in `src/dashboard/templates.py` (lightning bolts, fire, sparkles, charts, shields, hourglasses, rockets, warning triangles, stars, magnifying glasses) MUST NOT appear anywhere in HTML templates, CSS `content`, JS strings, or technical documentation.
- **Geometric SVG Iconography**: Replace all legacy emojis with crisp inline `<svg>` glyphs (`width="14" height="14"` or `16px`, `viewBox="0 0 16 16"`, `fill="none"`, `stroke="currentColor"`, `stroke-width="1.5"`, `stroke-linecap="round"`, `stroke-linejoin="round"`, `aria-hidden="true"`), or crisp `6px` circular status dots.

---

## 2. Design Token Contract (`src/dashboard/static/tokens.css`)

### 2.1 WCAG 2.2 AA Contrast Verification Matrix

Every ink and semantic foreground token was empirically verified against all 4 dark elevation tiers (`#080B10`, `#0F141C`, `#151C26`, `#1B2330`) and against composited tinted `--status-*-bg` surfaces on `--bg-elevated` (`#1B2330`):

| Token | Hex / Value | vs `--bg-canvas` (`#080B10`) | vs `--bg-elevated` (`#1B2330`) | vs Tinted Status BG on Elevated | Pairing Constraint |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `--text-primary` | `#F1F5F9` | `17.99:1` | `14.42:1` | `>= 11.24:1` | Primary text; never use on solid `--accent-primary` fill |
| `--text-secondary` | `#B4C0D0` | `10.69:1` | `8.57:1` | -- | Subheads, axis labels, table labels |
| `--text-muted` | `#8B9BB0` | `6.96:1` | `5.58:1` | -- | Captions, placeholders, timestamps (`>= 4.5:1` everywhere) |
| `--text-inverse` | `#080B10` | -- | -- | `7.11:1` on `--accent-primary` | Mandatory ink on filled `--accent-primary` / `--accent-primary-hover` buttons |
| `--accent-primary` | `#0EA5E9` | `7.11:1` | `5.70:1` | -- | Links, active borders, solid CTA fill (with `--text-inverse`) |
| `--accent-primary-hover` | `#38BDF8` | `9.20:1` | `7.37:1` | -- | Hover CTA fill (with `--text-inverse`), focus rings |
| `--accent-telemetry` | `#22D3EE` | `10.90:1` | `8.74:1` | -- | OLS trendline, scan active pulse, telemetry crosshairs |
| `--status-excellent` | `#34D399` | `10.25:1` | `8.22:1` | `6.54:1` | `BELOW P25`, Strong Buy (`>= 85`), clean title |
| `--status-info` | `#38BDF8` | `9.20:1` | `7.37:1` | `5.94:1` | Good Value (`75..84.9`), `USED_EV_TAX_CREDIT`, scan status |
| `--status-cut` | `#FBBF24` | `11.80:1` | `9.46:1` | `7.37:1` | `FRESH_PRICE_CUT`, `HIGH_LEVERAGE`, price reduction delta |
| `--status-warn` | `#FB923C` | `8.71:1` | `6.98:1` | `5.77:1` | `STALE_INVENTORY_30D`, `MODERATE` risk, `#degraded-banner` |
| `--status-danger` | `#F87171` | `7.12:1` | `5.71:1` | `4.94:1` | Overpriced (`> P75`), salvage/rebuilt, `ELEVATED` safety risk |
| `--border-strong` | `rgba(148, 163, 184, 0.55)` | `3.28:1` | `2.65:1` (`3.03:1` on `--bg-surface`) | -- | Interactive inputs, selects, control borders |

### 2.2 Canonical `src/dashboard/static/tokens.css`

```css
/* ==========================================================================
   car-researcher Design Token Contract (v2-market-intelligence)
   Aesthetic: Precision Automotive Telemetry & Quantitative Valuation Desk
   ========================================================================== */

:root {
  color-scheme: dark;

  /* ------------------------------------------------------------------------
     1. 4-Tier Dark Surface Elevation Hierarchy & Overlay
     ------------------------------------------------------------------------ */
  --bg-canvas: #080B10;           /* Tier 0: Viewport root canvas */
  --bg-inset: #0B0F15;            /* Recessed well: inputs, VIN chips, table head alt */
  --bg-surface: #0F141C;          /* Tier 1: Primary cards, KPI tiles, filter bar, panels */
  --bg-surface-hover: #151C26;    /* Tier 2: Hover rows, interactive sub-wells, secondary btns */
  --bg-elevated: #1B2330;         /* Tier 3: Sticky headers, slide-over drawer, tooltips, tray */
  --bg-overlay: rgba(4, 7, 12, 0.80); /* Backdrop scrim behind drawer and modal */

  /* ------------------------------------------------------------------------
     2. Structural Hairline Border Hierarchy
     ------------------------------------------------------------------------ */
  --border-subtle: rgba(148, 163, 184, 0.12);   /* Internal dividers, table row hairlines */
  --border-default: rgba(148, 163, 184, 0.22);  /* Card frames, panels, tab rails */
  --border-strong: rgba(148, 163, 184, 0.55);   /* Form controls, interactive outlines (>= 3:1 on surface) */
  --border-focus: #38BDF8;                      /* High-visibility keyboard focus ring */

  /* ------------------------------------------------------------------------
     3. Ink / Text Hierarchy (WCAG AA >= 4.5:1 across all 4 surface tiers)
     ------------------------------------------------------------------------ */
  --text-primary: #F1F5F9;        /* Primary metrics, titles, active tab labels */
  --text-secondary: #B4C0D0;      /* Body metadata, axis ticks, column headers */
  --text-muted: #8B9BB0;          /* Timestamps, captions, placeholders, helper copy */
  --text-inverse: #080B10;        /* Dark ink for filled --accent-primary / status solid buttons */

  /* ------------------------------------------------------------------------
     4. Brand & Telemetry Accent Tokens
     ------------------------------------------------------------------------ */
  --accent-primary: #0EA5E9;              /* Primary CTA fill (with --text-inverse), active markers */
  --accent-primary-hover: #38BDF8;        /* Hover CTA fill, interactive link emphasis */
  --accent-primary-bg: rgba(14, 165, 233, 0.14);
  --accent-telemetry: #22D3EE;            /* OLS frontier line, active telemetry pulse, crosshair */
  --accent-telemetry-bg: rgba(34, 211, 238, 0.12);

  /* ------------------------------------------------------------------------
     5. Semantic Automotive Valuation Status Tokens
     ------------------------------------------------------------------------ */
  /* Excellent / BELOW P25 / Strong Buy (>= 85) / Clean Title */
  --status-excellent: #34D399;
  --status-excellent-bg: rgba(16, 185, 129, 0.14);
  --status-excellent-border: rgba(52, 211, 153, 0.36);

  /* Info / Good Value (75..84.9) / USED_EV_TAX_CREDIT / Active Telemetry */
  --status-info: #38BDF8;
  --status-info-bg: rgba(14, 165, 233, 0.14);
  --status-info-border: rgba(56, 189, 248, 0.36);

  /* Price Cut / Motivated Seller / FRESH_PRICE_CUT / HIGH_LEVERAGE */
  --status-cut: #FBBF24;
  --status-cut-bg: rgba(245, 158, 11, 0.14);
  --status-cut-border: rgba(251, 191, 36, 0.38);

  /* Warn / STALE_INVENTORY_30D / MODERATE Risk / Degraded DB Fallback */
  --status-warn: #FB923C;
  --status-warn-bg: rgba(249, 115, 22, 0.14);
  --status-warn-border: rgba(251, 146, 60, 0.38);

  /* Danger / Overpriced (> P75) / Salvage / ELEVATED Safety Risk / Scan Error */
  --status-danger: #F87171;
  --status-danger-bg: rgba(239, 68, 68, 0.15);
  --status-danger-border: rgba(248, 113, 113, 0.38);

  /* ------------------------------------------------------------------------
     6. Typography & Tabular Precision Scale
     ------------------------------------------------------------------------ */
  --font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-mono: "JetBrains Mono", "SFMono-Regular", ui-monospace, Menlo, Monaco, Consolas, "Liberation Mono", monospace;

  --text-2xs: 0.6875rem;   /* 11px: micro labels, badge text, table headers */
  --text-xs: 0.75rem;      /* 12px: dense table cells, filter controls, metadata */
  --text-sm: 0.8125rem;    /* 13px: secondary body, drawer sections */
  --text-base: 0.875rem;   /* 14px: primary UI copy, vehicle titles */
  --text-lg: 1rem;         /* 16px: section titles, drawer headings */
  --text-xl: 1.25rem;      /* 20px: modal/drawer hero price */
  --text-2xl: 1.5rem;      /* 24px: KPI figures, primary card price */

  --leading-tight: 1.2;
  --leading-normal: 1.45;
  --tracking-tight: -0.015em;
  --tracking-label: 0.06em;

  /* ------------------------------------------------------------------------
     7. 4px / 8px Spatial Scale
     ------------------------------------------------------------------------ */
  --space-1: 0.25rem;   /*  4px */
  --space-2: 0.5rem;    /*  8px */
  --space-3: 0.75rem;   /* 12px */
  --space-4: 1rem;      /* 16px */
  --space-5: 1.25rem;   /* 20px */
  --space-6: 1.5rem;    /* 24px */
  --space-8: 2rem;      /* 32px */
  --space-10: 2.5rem;   /* 40px */
  --space-12: 3rem;     /* 48px */

  /* ------------------------------------------------------------------------
     8. Radii, Layout Caps & Elevation Shadows
     ------------------------------------------------------------------------ */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --container-max: 1600px;

  --shadow-elevated: 0 12px 32px rgba(2, 6, 12, 0.55);
  --shadow-drawer: -12px 0 36px rgba(2, 6, 12, 0.65);

  /* ------------------------------------------------------------------------
     9. Z-Index Layers
     ------------------------------------------------------------------------ */
  --z-base: 1;
  --z-sticky: 20;     /* Top app header, sticky table column headers */
  --z-tray: 35;       /* Fixed bottom Compare Pin Tray (#compare-tray) */
  --z-overlay: 40;    /* Scrim behind slide-over drawer & modals */
  --z-drawer: 50;     /* Slide-over valuation drawer & compare modal */
  --z-tooltip: 60;    /* Interactive SVG scatter chart focus tooltip */

  /* ------------------------------------------------------------------------
     10. Motion Tokens
     ------------------------------------------------------------------------ */
  --ease-telemetry: cubic-bezier(0.16, 1, 0.3, 1);
  --duration-fast: 120ms;
  --duration-normal: 180ms;
  --duration-drawer: 220ms;
}

/* ==========================================================================
   Base Reset, Overflow Protection & Tabular Numerals Enforcement
   ========================================================================== */

*,
*::before,
*::after {
  box-sizing: border-box;
}

html,
body {
  margin: 0;
  padding: 0;
  background-color: var(--bg-canvas);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 16px;
  line-height: var(--leading-normal);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  overflow-x: clip;
}

/* Strict Tabular Numerals Utility & Domain Selectors */
.tabular-nums,
[data-numeric],
.kpi-value,
.price-readout,
.delta-readout,
.cohort-stat,
.metric-cell,
.score-pill,
.vin-chip,
.dom-readout,
.tco-value,
.epa-value,
.chart-tick,
.chart-tooltip-val {
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum" 1, "zero" 1;
}

.mono-readout,
.vin-chip {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum" 1, "zero" 1;
}

:focus-visible {
  outline: 2px solid var(--border-focus);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --duration-fast: 0.01ms;
    --duration-normal: 0.01ms;
    --duration-drawer: 0.01ms;
  }

  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

### 2.3 Mandatory Tabular Numeral Selector Coverage

All CSS rules and rendered templates MUST apply `.tabular-nums` (or semantic element classes bound above) to every numeric telemetry element:
- **Pricing & Valuation**: Listing `price`, `market_value` (FMV), `price_delta` (`-$X` / `+$X`), `pct_savings`, `estimated_msrp`, `msrp_discount_pct`, `suggested_offer_low`, `suggested_offer_target`.
- **Cohort Distribution**: `sample_size`, `min_price`, `p10`, `p25`, `p50`, `p75`, `max_price`, `iqr`, `cohort_percentile`, `cohort_z_score`, `price_per_1k_miles` (`$/1k mi`), `slope_per_1k_miles`, `r2`.
- **Scoring & Liquidity**: `deal_score`, 4-factor sub-scores (`price_score`, `history_score`, `leverage_score`, `proximity_score`), `negotiation_leverage_score`, `days_on_market` (DOM), `price_change`, `price_drop_total`, `price_velocity_per_week`.
- **Vehicle & Ownership Telemetry**: `mileage` (odometer), `distance_miles`, `projected_3yr_depreciation`, `projected_3yr_residual`, `energy_cost_3yr`, `total_3yr_ownership_delta`, `range_miles`, `comb_mpge`, `annual_fuel_cost`, `recalls_count`, `complaints_count`, and 17-character `vin` readouts.

---

## 3. Component Specifications (`src/dashboard/static/components.css`)

All classes below MUST strictly consume custom properties from `tokens.css` with **zero hardcoded hex colors**.

### 3.1 App Shell, Header & Scan Banner

- **`.skip-link` & `.sr-only`**:
  - `.skip-link`: Visually clipped off-canvas at rest; on `:focus-visible`, anchors at `position: fixed; top: var(--space-3); left: var(--space-3); z-index: calc(var(--z-tooltip) + 10); padding: var(--space-2) var(--space-3); background: var(--accent-primary); color: var(--text-inverse); border-radius: var(--radius-md); font-weight: 600;`.
  - `.sr-only`: `1px x 1px` clip utility used by `#live-announcer` (`aria-live="polite"`) and screen-reader `<label>` text.
- **`.app-shell`**: `min-height: 100dvh; display: flex; flex-direction: column; background: var(--bg-canvas);`
- **`.app-container` / `#main-content`**: `width: 100%; max-width: var(--container-max); margin-inline: auto; padding-inline: var(--space-4);` (`padding-inline: var(--space-6)` at `>= 1024px`). Reserves bottom clearance (`padding-bottom: 88px`) when `#compare-tray` is visible.
- **`#console-header` (`.console-header`)**: Sticky top bar (`position: sticky; top: 0; z-index: var(--z-sticky); background: rgba(8, 11, 16, 0.92); backdrop-filter: blur(8px); border-bottom: 1px solid var(--border-default);`). Contains:
  - Geometric vector emblem (`28px x 28px`, `--bg-elevated`, `1px solid var(--border-default)`, `--accent-telemetry` SVG waveform/gauge stroke).
  - Scope badge (`.scope-chip`): `ZIP 94103 | 60 mi` in `--font-mono`, `--text-2xs`, `--status-info-bg`, `--status-info-border`, `--status-info`.
  - Provenance pill: `LIVE: TIMESCALEDB` (`--status-excellent`) or `OFFLINE SAMPLE` (`--status-warn`) or `TEST FIXTURE` (`--text-secondary`).
  - Temporal Scan Trigger form (`#scan-trigger-form`, `select.control-select` + `button.btn-primary` with `--accent-primary` fill and `--text-inverse` ink). Optional `TEMPORAL_UI_URL` link rendered only when configured.
- **`#scan-status-banner` / `#active-scan-poller`**:
  - Running state: `--status-info-bg`, `1px solid var(--status-info-border)`, left `3px solid var(--accent-telemetry)`, `.tabular-nums` counters for `scraped` and `scored` counts. Pulsing indicator dot uses opacity animation disabled under `prefers-reduced-motion: reduce`.
  - Completed state: `--status-excellent-bg`, `1px solid var(--status-excellent-border)`, `--status-excellent`.
  - Error / Unavailable state: `--status-danger-bg`, `1px solid var(--status-danger-border)`, `--status-danger`.

### 3.2 Degraded / Offline Banner (`id="degraded-banner"`)

Rendered immediately beneath `<header>` inside `<main>` whenever API `provenance` is `"offline-sample"` or `"fixture"` (PostgreSQL / TimescaleDB unreachable or unconfigured).

- **Geometry & Surface**:
  - `display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--space-3);`
  - `padding: var(--space-3) var(--space-4); margin-bottom: var(--space-4);`
  - `background: var(--status-warn-bg); border: 1px solid var(--status-warn-border); border-left: 3px solid var(--status-warn); border-radius: var(--radius-md);`
- **Anatomy**:
  - Left: `16px` triangle-alert inline SVG (`stroke: var(--status-warn)`) + status tag (`DEGRADED MODE // OFFLINE SAMPLE`, `--font-mono`, `--text-xs`, uppercase, `--status-warn`) + plain-language explanation (`Database telemetry unavailable; serving 24 deterministic Bay Area EV sample listings. Live scraping & persistence paused.`).
  - Right: Compact diagnostic metadata (`PROVENANCE: OFFLINE-SAMPLE` in `--font-mono`, `--text-2xs`, `--text-secondary`) and optional `Retry DB` / `Health` link (`GET /api/health`).

### 3.3 KPI Telemetry Strip (`#kpi-bar` / `.kpi-strip`)

- **Layout**:
  - Mobile (`< 768px`): `display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3);`
  - Desktop (`>= 1024px`): `grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-4);`
- **Tile Anatomy (`.kpi-card`)**:
  - `background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: var(--radius-lg); padding: var(--space-4);`
  - High-conviction highlight variant (`.kpi-card--excellent`): `border-top: 2px solid var(--status-excellent);`
  - **Label (`.kpi-label`)**: `--text-2xs`, `font-weight: 600`, uppercase, `letter-spacing: var(--tracking-label)`, `--text-muted`.
  - **Primary Value (`.kpi-value`)**: `--text-2xl`, `font-weight: 700`, `line-height: var(--leading-tight)`, `--text-primary` (or `--status-excellent` / `--status-cut`), strictly `.tabular-nums`.
  - **Sub-Readout (`.kpi-sub`)**: `--text-xs`, `--text-secondary`, right-aligned or stacked baseline metric (e.g., `Median $/1k mi: $1,840`, `Avg discount: -$9,420`, `Price-cut share: 29.2%`).

### 3.4 Workspace Tab Bar (`.workspace-nav` / `.workspace-tabs` & `.triage-tabs`)

Two cleanly separated tab levels preserve spatial clarity and backward compatibility with `setFilterTab(...)`:

1. **Primary Analytical Workspace Tabs (`.workspace-nav [role="tablist"]`, `role="tablist"`)**:
   - Tabs (`#tab-workbench`, `#tab-market`, `#tab-arbitrage`, `#tab-compare`): `Deal Workbench` | `Market Intelligence` | `Dealer & Channel Arbitrage` | `Side-by-Side Comparator`
   - Container: `display: flex; gap: var(--space-1); border-bottom: 1px solid var(--border-default); margin-bottom: var(--space-4); overflow-x: auto; scrollbar-width: none;`
   - Tab Button (`.workspace-tab`): `padding: var(--space-2) var(--space-4); min-height: 40px; font-size: var(--text-sm); font-weight: 600; color: var(--text-secondary); background: transparent; border: none; border-bottom: 2px solid transparent; white-space: nowrap; cursor: pointer; display: inline-flex; align-items: center; gap: var(--space-2); transition: color var(--duration-fast) var(--ease-telemetry), border-color var(--duration-fast) var(--ease-telemetry);`
   - Hover: `color: var(--text-primary);`
   - Active (`[aria-selected="true"]` / `.is-active`): `color: var(--text-primary); border-bottom-color: var(--accent-telemetry); background: linear-gradient(to top, var(--accent-telemetry-bg), transparent);`
   - Dynamic Count Pill (`.workspace-tab__count`): `--font-mono`, `--text-2xs`, `.tabular-nums`, `padding: 1px 6px; border-radius: var(--radius-sm); background: var(--bg-elevated); color: var(--text-secondary);`.

2. **Inventory Triage Sub-Tabs (`.triage-tabs`)**:
   - Tabs: `All Active`, `Excellent >=85`, `Good >=75`, `Price Drops`, `Saved`, `Dismissed`
   - Container: `display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-4);`
   - Pill Button (`.triage-tab`): `padding: var(--space-1) var(--space-3); min-height: 32px; border-radius: var(--radius-md); border: 1px solid var(--border-default); background: var(--bg-surface); color: var(--text-secondary); font-size: var(--text-xs); font-weight: 500;`
   - Active (`.is-active`): `background: var(--bg-elevated); border-color: var(--accent-primary); color: var(--accent-primary-hover);`
   - Count suffix rendered inside `<span class="triage-count tabular-nums">`.

### 3.5 Filter Bar (`#filter-form` / `.filter-bar`)

- **Container**: `background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: var(--radius-lg); padding: var(--space-4); margin-bottom: var(--space-5);`
- **Grid Rhythm**:
  - `375px` mobile: `1 column`, `gap: var(--space-3)`
  - `768px` tablet: `2 columns`, `gap: var(--space-3)`
  - `1280px+` desktop: `grid-template-columns: 2fr 1fr 1fr 1fr 1.25fr; gap: var(--space-3); align-items: end;`
- **Controls (`.control-input`, `.control-select`)**:
  - `width: 100%; min-height: 36px; padding: var(--space-1) var(--space-3);`
  - `background: var(--bg-inset); border: 1px solid var(--border-strong); border-radius: var(--radius-md);`
  - `color: var(--text-primary); font-size: var(--text-xs); font-family: var(--font-sans);`
  - Placeholder: `color: var(--text-muted);`
  - Focus: `border-color: var(--border-focus); box-shadow: 0 0 0 1px var(--border-focus); outline: none;`
- **View Mode Segmented Control (`.view-toggle`)**:
  - Paired `Grid` / `Table` buttons (`min-width: 36px; min-height: 36px;`) sharing a `1px solid var(--border-strong)` pill group; active view highlighted with `--bg-elevated` and `--accent-telemetry` icon stroke.

### 3.6 Card Grid & Precision Table

#### 3.6.1 Card Grid (`.deals-grid`)
- **Responsive Grid**:
  - Mobile (`< 768px`): `1 column`
  - Tablet (`768px..1279px`): `2 columns`
  - Desktop (`1280px..1599px`): `3 columns`
  - Ultrawide (`>= 1600px` inside `max-width: 1600px` cap): `3` or `4` columns via `grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: var(--space-5);`
- **Card Container (`.deal-card`)**:
  - `display: flex; flex-direction: column; justify-content: space-between;`
  - `background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: var(--radius-lg); overflow: hidden;`
  - `transition: border-color var(--duration-fast) var(--ease-telemetry), background-color var(--duration-fast) var(--ease-telemetry);`
  - Hover: `border-color: var(--border-strong);`
  - Pinned for Compare (`.is-pinned`): `border-color: var(--accent-telemetry); box-shadow: inset 0 2px 0 0 var(--accent-telemetry);`
- **Media Frame (`.deal-card__media`)**:
  - Fixed aspect/height reservation (`height: 176px; width: 100%; background: var(--bg-inset); position: relative; overflow: hidden; border-bottom: 1px solid var(--border-subtle);`) preventing image load layout shift (`CLS = 0`).
  - Missing-photo fallback: clean technical vector vehicle wireframe silhouette (`stroke: var(--text-muted)`, `opacity: 0.45`) over subtle `16px` grid-line SVG background — zero emoji placeholders.
  - Overlay chips use `background: rgba(8, 11, 16, 0.88); border: 1px solid var(--border-default);` for guaranteed readability over bright vehicle photography.
- **Card Body Sections**:
  1. Title & Platform/Trim line (`--text-base`, `font-weight: 600`, `line-clamp-1`).
  2. Price Header Row: Listing Price (`--text-2xl`, `font-weight: 700`, `.tabular-nums`), Est. FMV (`--text-xs`, `--text-muted`), Dollar & Pct Delta (`--status-excellent` if `< 0`, `--status-warn` / `--status-danger` if `> 0`).
  3. Embedded **Cohort Range Bar** (`.cohort-range-bar`, see Section 3.7).
  4. **Market Badges** strip (max 3 visible chips + `+N` overflow indicator, see Section 3.8).
  5. 4-Factor Telemetry Bars (`Price`, `Hist`, `DOM`, `Prox`): `height: 4px; background: var(--bg-elevated); border-radius: var(--radius-sm);` with semantic fill (`--status-excellent`, `--status-info`, `--accent-telemetry`, `--status-cut`).
  6. Key-Value Telemetry Table: `Odometer & Title`, `Location`, `Dealer`, `3-Yr TCO / EV Credit`, and `VIN` copy button (`.vin-chip`).
  7. Footer Bar (`.deal-card__footer`): `background: var(--bg-inset); border-top: 1px solid var(--border-subtle); padding: var(--space-2) var(--space-4);` containing `Save`, `Pin` (compare), `Hide`, `Analysis` (opens slide-over drawer), and `View` external link.

#### 3.6.2 Precision Table (`.precision-table-wrap`)
- **Scroll Container**:
  - `width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch;`
  - `background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: var(--radius-lg);`
- **Table Structure (`.precision-table`)**:
  - `width: 100%; min-width: 960px; border-collapse: collapse; text-align: left;`
  - **Sticky Header (`thead th`)**:
    - `position: sticky; top: 0; z-index: var(--z-sticky);`
    - `background: var(--bg-elevated); color: var(--text-secondary);`
    - `font-size: var(--text-2xs); font-weight: 600; text-transform: uppercase; letter-spacing: var(--tracking-label);`
    - `padding: var(--space-3) var(--space-3); border-bottom: 1px solid var(--border-strong); white-space: nowrap;`
  - **Rows (`tbody tr`)**:
    - `border-bottom: 1px solid var(--border-subtle); font-size: var(--text-xs); transition: background-color var(--duration-fast) var(--ease-telemetry);`
    - Hover: `background: var(--bg-surface-hover);`
    - Pinned (`tr.is-pinned`): `background: var(--accent-telemetry-bg); box-shadow: inset 3px 0 0 0 var(--accent-telemetry);`
  - **Numeric Alignment Rule**: Columns `#`, `Score`, `Price`, `Est. FMV`, `vs FMV`, `Cohort Pctl`, `$/1k mi`, `Mileage`, `DOM`, and `Distance` MUST apply `text-align: right; white-space: nowrap;` and `.tabular-nums`.

### 3.7 Cohort Range Bar (`.cohort-range-bar`)

Visualizes a listing's price position against its empirical cohort (`min`/`p10` through `p25`, `p50`, `p75`, `max`).

- **Container**: `padding: var(--space-2) 0; display: flex; flex-direction: column; gap: var(--space-1);`
- **Header Line**: Left label `COHORT BAND (N=X)` or `MODEL FALLBACK` (`--text-2xs`, `--text-muted`) + Right percentile readout (`P18 • -$4,210 vs P50`, `--font-mono`, `.tabular-nums`).
- **Track Geometry (`.cohort-track`)**:
  - `position: relative; height: 8px; width: 100%; background: var(--bg-elevated); border-radius: var(--radius-sm); overflow: visible;`
  - **Buy-Zone Fill (`p10 .. p25`)**: `position: absolute; top: 0; bottom: 0; background: var(--status-excellent-bg); border-left: 1px solid var(--status-excellent);`
  - **IQR Fair Band (`p25 .. p75`)**: `position: absolute; top: 0; bottom: 0; background: rgba(148, 163, 184, 0.16); border-left: 1px solid var(--border-strong); border-right: 1px solid var(--border-strong);`
  - **P50 Median Tick**: `position: absolute; top: -2px; bottom: -2px; width: 1px; background: var(--text-secondary);`
  - **Current Listing Marker (`.cohort-marker`)**:
    - `position: absolute; top: 50%; width: 10px; height: 10px; transform: translate(-50%, -50%) rotate(45deg); border: 1.5px solid var(--bg-canvas); border-radius: 2px;`
    - Color logic: `--status-excellent` when `price <= p25`; `--accent-telemetry` when `p25 < price <= p75`; `--status-danger` when `price > p75`.
- **Footer Scale**: `display: flex; justify-content: space-between; font-family: var(--font-mono); font-size: var(--text-2xs); color: var(--text-muted);` displaying `P25 $XXk`, `P50 $XXk`, `P75 $XXk` with `.tabular-nums`.

### 3.8 Market Badges (`.market-badge`)

All 5 deterministic `market_badges` tokens defined in `docs/MARKET_ANALYSIS_SPEC.md` map to consistent pill geometry (`display: inline-flex; align-items: center; gap: var(--space-1); padding: 2px var(--space-2); border-radius: var(--radius-sm); font-size: var(--text-2xs); font-weight: 600; letter-spacing: 0.03em; line-height: 1.3; border: 1px solid; white-space: nowrap;`):

| Backend Enum Key | Display Label | Foreground Token | Background Token | Border Token | Leading Indicator |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `BELOW_P25_COHORT` | `BELOW P25` | `--status-excellent` | `--status-excellent-bg` | `--status-excellent-border` | `6px` emerald dot |
| `FRESH_PRICE_CUT` | `PRICE CUT` | `--status-cut` | `--status-cut-bg` | `--status-cut-border` | `10px` down-arrow SVG |
| `STALE_INVENTORY_30D` | `30D+ DOM` | `--status-warn` | `--status-warn-bg` | `--status-warn-border` | `10px` clock SVG |
| `HIGH_LEVERAGE` | `HIGH LEVERAGE` | `--status-cut` | `--status-cut-bg` | `--status-cut-border` | `10px` gauge/slider SVG |
| `USED_EV_TAX_CREDIT` | `EV CREDIT -$4K` | `--status-info` | `--status-info-bg` | `--status-info-border` | `10px` check-shield SVG |

**Deal Score & Safety Posture Badges**:
- `deal_score >= 85`: `--status-excellent` / `--status-excellent-bg` / `--status-excellent-border`
- `75 <= deal_score < 85`: `--status-info` / `--status-info-bg` / `--status-info-border`
- `60 <= deal_score < 75`: `--status-cut` / `--status-cut-bg` / `--status-cut-border`
- `deal_score < 60`: `--status-danger` / `--status-danger-bg` / `--status-danger-border`
- `safety_posture == "ELEVATED"` or non-clean title: `--status-danger` / `--status-danger-bg` / `--status-danger-border`
- `safety_posture == "MODERATE"`: `--status-warn` / `--status-warn-bg` / `--status-warn-border`
- `safety_posture == "LOW"`: `--status-excellent` / `--status-excellent-bg` / `--status-excellent-border`

### 3.9 SVG Price-vs-Mileage Scatter Frontier (`#frontier-chart`, `#frontier-svg`) & Analytical Panels

Visualizes cohort valuation efficiency across `(mileage / 1000.0, price)` with OLS regression and empirical buy-zone boundaries inside `#workspace-market`.

- **Wrapper (`#frontier-chart` / `.frontier-panel`)**: `background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: var(--radius-lg); padding: var(--space-4); position: relative;`
- **SVG Element (`svg#frontier-svg` inside `#frontier-chart`)**:
  - `width: 100%; height: auto; min-height: 280px; max-height: 440px; display: block; overflow: visible;`
  - **Gridlines (`.frontier-gridline`)**: `stroke: var(--border-subtle); stroke-width: 1; stroke-dasharray: 2 4;`
  - **Axes (`.frontier-axis`)**: `stroke: var(--border-strong); stroke-width: 1;`
  - **Axis Ticks (`.chart-tick`)**: `fill: var(--text-muted); font-family: var(--font-mono); font-size: 11px;` (X-axis: `0k`..`80k mi`; Y-axis: `$20k`..`$65k`).
  - **Buy-Zone Shading (`.frontier-buyzone`)**: `<polygon>` / `<rect>` spanning lower region below `p25_line` (or below OLS `- 10%` threshold) with `fill: var(--status-excellent); fill-opacity: 0.07; pointer-events: none;`.
  - **Reference Lines**:
    - `p50_line`: `stroke: var(--text-muted); stroke-width: 1; stroke-dasharray: 4 4;`
    - `p25_line`: `stroke: var(--status-excellent); stroke-width: 1.25; stroke-dasharray: 3 3;`
    - **OLS Trendline (`.frontier-ols-line`)**: `stroke: var(--accent-telemetry); stroke-width: 2; fill: none;`
  - **Interactive Nodes (`.frontier-node`, `.frontier-point`)**:
    - `<g class="frontier-node frontier-point" tabindex="0" role="button" aria-label="...">` containing a `14px` transparent hit target circle around a visible `<circle r="5.5">`.
    - Color mapping: `fill: var(--status-excellent)` (below P25 / Buy Zone), `fill: var(--accent-primary-hover)` (fair mid-band), `fill: var(--status-danger)` (above P75). Selected/pinned node highlighted with outer ring `stroke: var(--text-primary); stroke-width: 2;`.
    - Hover / Keyboard `:focus-visible`: outer halo `stroke: var(--border-focus); stroke-width: 2.5;` without changing layout or causing adjacent pointer jitter.
- **Focus Tooltip (`#frontier-tooltip` / `.chart-tooltip`)**:
  - `position: absolute; z-index: var(--z-tooltip); pointer-events: none; min-width: 210px; max-width: 260px;`
  - `background: var(--bg-elevated); border: 1px solid var(--border-strong); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); box-shadow: var(--shadow-elevated);`
  - Displays vehicle title, Price vs OLS expected residual, Mileage, `$/1k mi`, and `Cohort Pctl` using `.tabular-nums`.
- **Regression Telemetry Footer (`.frontier-stats`)**:
  - Inline monospace summary pills: `OLS SLOPE: -$412 / 1k mi`, `R^2: 0.74`, `BUY CUTOFF (P25): $36,400`, `COHORT N = 12`.
- **Companion Workspace Cards (`#cohort-leaderboard`, `#momentum-feed`, `#platform-comparison`, `#distance-bands`, `#dealer-matrix`)**:
  - `#cohort-leaderboard` and `#dealer-matrix` reuse `.precision-table-wrap` + `.precision-table` tokens (`--bg-surface`, sticky `--bg-elevated` headers, right-aligned `.tabular-nums` cells).
  - `#momentum-feed` and `#platform-comparison` use 2-column `.panel-grid` (`1` col `< 1024px`, `2` cols `>= 1024px`, `gap: var(--space-4)`) inside `--bg-surface` cards with `1px solid var(--border-default)`.
  - `#distance-bands` renders a 4-tier grid (`2x2` mobile, `4x1` tablet/desktop) with inline horizontal relative discount bars (`height: 4px`, `--accent-telemetry` / `--status-excellent`).

### 3.10 SVG Price Sparkline (`.price-sparkline`)

Renders chronological TimescaleDB `price_snapshots` trajectories in both table/card compact cells (`96px x 26px`) and drawer detail charts (`100% x 110px`).

- **Geometry**:
  - Compact inline: `width: 96px; height: 26px; display: inline-block; vertical-align: middle;`
  - Expanded drawer chart: `width: 100%; height: 110px; display: block;`
- **Polyline & Area Semantics**:
  - Price dropped (`last < first`): `stroke: var(--status-cut);` (or `--status-excellent` when drop also pushes below FMV), area fill `var(--status-cut)` at `opacity: 0.12`.
  - Flat (`last == first`): `stroke: var(--text-muted); stroke-dasharray: 2 2;`.
  - Price increased (`last > first`): `stroke: var(--status-danger);`, area fill `var(--status-danger)` at `opacity: 0.12`.
- **Terminal Node**: `<circle cx="..." cy="..." r="2.75">` at most recent snapshot filled with active stroke color and `1px solid var(--bg-canvas)` halo. Single-snapshot listings render a horizontal dashed baseline with centered terminal point and `1 SNAPSHOT` accessible label.

### 3.11 Slide-Over Valuation Drawer (`#analysis-drawer` / `.valuation-drawer`)

Replaces cramped centered modal inspections for deep quantitative analysis (`/api/listings/{id}/analysis`) while maintaining `#detail-modal` compatibility for legacy tests.

- **Backdrop (`.drawer-backdrop`)**: `position: fixed; inset: 0; z-index: var(--z-overlay); background: var(--bg-overlay);`
- **Panel Geometry (`#analysis-drawer`)**:
  - **Mobile (`< 768px`)**: `position: fixed; inset: 0; width: 100%; height: 100dvh; z-index: var(--z-drawer);`
  - **Desktop (`>= 768px`)**: `position: fixed; top: 0; right: 0; bottom: 0; width: clamp(480px, 38vw, 560px); height: 100dvh; z-index: var(--z-drawer);`
  - Surface: `background: var(--bg-elevated); border-left: 1px solid var(--border-default); box-shadow: var(--shadow-drawer); display: flex; flex-direction: column;`
  - Slide transition: `transform var(--duration-drawer) var(--ease-telemetry)` (`translateX(100%)` closed -> `translateX(0)` open).
- **Internal Zones**:
  1. **Sticky Drawer Header (`.drawer-header`)**: `padding: var(--space-4) var(--space-5); border-bottom: 1px solid var(--border-default); background: var(--bg-elevated);` with Platform + VIN copy chip, Vehicle Title (`#drawer-title`), Ask Price vs FMV (`tabular-nums`), and `36px x 36px` (`44px x 44px` on mobile) `Close` button (`Escape` closes, restores trigger focus).
  2. **Scrollable Telemetry Body (`.drawer-body`)**: `flex: 1; overflow-y: auto; padding: var(--space-5); display: flex; flex-direction: column; gap: var(--space-5);` containing:
     - Composite Score & 4-Factor Breakdown Bars
     - Cohort Distribution Band + Range Bar (`P10`..`P75`)
     - Price Velocity & Expanded SVG Sparkline + Snapshot History Table
     - Negotiation Leverage Card (`leverage_score / 100`, `suggested_offer_low` to `suggested_offer_target`)
     - 3-Year TCO, Depreciation & Used EV Tax Credit (`$4,000`) Eligibility Table
     - NHTSA Recalls, ODI Complaints & EPA Efficiency Panel
  3. **Sticky Action Footer (`.drawer-footer`)**: `padding: var(--space-3) var(--space-5); border-top: 1px solid var(--border-default); background: var(--bg-surface); display: flex; align-items: center; justify-content: space-between; gap: var(--space-2);` (`Save`, `Pin to Compare`, `Open Listing`).

### 3.12 Compare Pin Tray (`id="compare-tray"`) & Side-by-Side Matrix (`#workspace-compare`)

Allows operators to pin up to `3` vehicles and invoke `/api/compare?ids=a,b,c`.

- **Position & Surface (`#compare-tray`)**:
  - `position: fixed; bottom: 0; left: 0; right: 0; z-index: var(--z-tray);`
  - `background: var(--bg-elevated); border-top: 1px solid var(--border-strong); box-shadow: 0 -8px 24px rgba(2, 6, 12, 0.55);`
  - Hidden state (`[hidden]` or `.is-empty`): `transform: translateY(100%); pointer-events: none; visibility: hidden;`
- **Inner Container**: `max-width: var(--container-max); margin-inline: auto; padding: var(--space-3) var(--space-4); display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--space-3);`
- **Pinned Slots (`.compare-slots`)**:
  - `display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-2); flex: 1; min-width: 280px;`
  - Filled chip (`.compare-slot--filled`): `background: var(--bg-surface); border: 1px solid var(--accent-telemetry); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); display: flex; align-items: center; justify-content: space-between; gap: var(--space-2);` with model title, `.tabular-nums` price/score, and unpin `button`.
  - Empty slot (`.compare-slot--empty`): `background: var(--bg-inset); border: 1px dashed var(--border-default); border-radius: var(--radius-md); color: var(--text-muted); font-size: var(--text-xs);`
- **Action Cluster**:
  - `Compare Now (N/3)` (`button.btn-primary`, disabled until `N >= 1`, opens `#workspace-compare`, `--accent-primary` + `--text-inverse`)
  - `Clear All` (`button.btn-ghost`)
- **Comparison Matrix (`#workspace-compare`)**: 10-dimension `.precision-table` matrix highlighting best-in-category winner cells (`lowest_price`, `highest_score`, `lowest_mileage`, `lowest_tco`, `highest_leverage`, `longest_range`) with `1px solid var(--status-excellent-border)`, `--status-excellent-bg` tint, and an explicit `BEST` inline micro-pill (`--status-excellent`) so color is never the sole indicator.

### 3.13 Loading Skeletons (`CLS = 0` Geometry-Matched Shimmer)

Every asynchronous HTMX or JSON fetch region reserves exact layout height to achieve `Cumulative Layout Shift (CLS) = 0`.

- **Shimmer Keyframe**:
  ```css
  .skeleton {
    background: linear-gradient(
      90deg,
      var(--bg-surface) 0%,
      var(--bg-surface-hover) 50%,
      var(--bg-surface) 100%
    );
    background-size: 200% 100%;
    border-radius: var(--radius-sm);
    animation: telemetry-shimmer 1.4s infinite linear;
  }

  @keyframes telemetry-shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  @media (prefers-reduced-motion: reduce) {
    .skeleton {
      animation: none;
      background: var(--bg-surface-hover);
    }
  }
  ```
- **Geometry-Matched Presets**:
  - `.skeleton-kpi`: `min-height: 92px; border: 1px solid var(--border-subtle); border-radius: var(--radius-lg);`
  - `.skeleton-card`: `min-height: 468px; border: 1px solid var(--border-subtle); border-radius: var(--radius-lg);` with `176px` `.skeleton-card__media` block matching `.deal-card__media`.
  - `.skeleton-table-row`: `height: 48px;` rows matching `.precision-table` column cadence.
  - `.skeleton-chart`: `aspect-ratio: 16 / 9; min-height: 280px; max-height: 440px; border-radius: var(--radius-lg);` matching `#frontier-chart`.

---

## 4. Responsive Breakpoints & Viewport Matrix

All views enforce zero horizontal document overflow (`html, body { overflow-x: clip; }`). Wide tables scroll strictly inside `.precision-table-wrap`.

| Viewport Tier | Breakpoint Width | Container Cap & Padding | KPI Strip | Filter Bar Grid | Deals Card Grid | Scatter & Arbitrage Split | Slide-Over Drawer | Compare Tray (`#compare-tray`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Mobile** | `375px` (`< 768px`) | `100%`, `16px` (`--space-4`) | `2 cols x 2 rows` | `1 col` stacked | `1 col` stack | Stacked `1 col` (`min-height: 280px` chart) | `100%` width, `100dvh` | Compact count summary + 1-line CTA + scrollable slots |
| **Tablet** | `768px` (`768px..1279px`) | `100%`, `20px` (`--space-5`) | `2 cols x 2 rows` | `2 cols` (`Search` full-span) | `2 cols` | Stacked `1 col`, 2-col KPI stats beneath | `480px` right dock | `3-slot` compact grid + CTA side-by-side |
| **Desktop** | `1280px` (`1280px..1599px`) | `100%`, `24px` (`--space-6`) | `4 cols x 1 row` | `5-6 cols` inline | `3 cols` | `2fr` Frontier Chart / `1fr` Cohort Stats | `520px` right dock | Full `3-slot` strip + action buttons |
| **Ultrawide** | `2560px` (`>= 1600px`) | `max-width: 1600px` centered | `4 cols x 1 row` | `5-6 cols` inline | `3–4 cols` (`minmax(360px, 1fr)`) | `2fr` Frontier Chart / `1fr` Cohort Stats | `560px` right dock | Centered inside `1600px` cap |

### Media Query Breakpoint Tokens
- Mobile baseline: `< 768px` (default mobile-first rules)
- `@media (min-width: 768px)`: Tablet 2-column grid, `480px` slide-over drawer, horizontal workspace tab alignment.
- `@media (min-width: 1024px)`: 4-column KPI telemetry strip, `24px` container padding.
- `@media (min-width: 1280px)`: Desktop multi-column filter bar, 3-column card grid, `520px` drawer, `2fr / 1fr` frontier + cohort summary layout.
- `@media (min-width: 1600px)`: Ultrawide cap enforcement (`max-width: var(--container-max)`), `560px` drawer max width, 4-column card allowance where grid tracks fit `>= 360px`.

---

## 5. Legacy Template Migration Contract (`src/dashboard/templates.py`)

When migrating existing templates from Tailwind/HTMX CDN dependencies to self-contained `tokens.css` + `components.css`:

1. **Preserve Existing DOM IDs & JS Hooks**: Keep `#kpi-bar`, `#filter-form`, `#search-input`, `#tab-input`, `#view-input`, `#deals-container`, `#scan-status-banner`, `#active-scan-poller`, `#detail-modal`, `#modal-body`, `setFilterTab(...)`, `toggleViewMode(...)`, `openModal()`, and `closeModal()` intact so all existing SSR routes and unit tests in [`tests/test_dashboard_unittest.py`](file:///home/tron/workspace/car-researcher/tests/test_dashboard_unittest.py) remain 100% green.
2. **Add v2 Landmark & Component IDs**: Mount `#console-header`, `#live-announcer`, `#degraded-banner`, `#workspace-workbench`, `#workspace-market`, `#workspace-arbitrage`, `#workspace-compare`, `#frontier-chart`, `#frontier-svg`, `#frontier-tooltip`, `#cohort-leaderboard`, `#momentum-feed`, `#platform-comparison`, `#distance-bands`, `#dealer-matrix`, `#analysis-drawer`, and `#compare-tray` using semantic HTML5 landmarks (`<header>`, `<nav>`, `<main>`, `<section>`, `<aside>`, `<footer>`).
3. **Strip External CDNs, Magic Hex Colors & Hardcoded Localhost Links**: Remove `<script src="https://cdn.tailwindcss.com"></script>`, `<script src="https://unpkg.com/htmx.org@1.9.12"></script>`, inline `<style>body { background-color: #060913; ... }</style>`, and hardcoded `http://localhost:8080` Temporal links (gating Temporal UI links strictly on optional `TEMPORAL_UI_URL`). Serve `<link rel="stylesheet" href="/static/tokens.css" />` and `<link rel="stylesheet" href="/static/components.css" />` locally.
4. **Strip All Emojis**: Replace every emoji character in `templates.py` and `app.py` with inline geometric SVGs (`aria-hidden="true"`) or clean monospaced markers while keeping test-asserted text strings (`Bay Area EV Deal Surveillance`, `Scan Marketplace`, `TimescaleDB Price Snapshots`, vehicle titles, VINs, prices) unchanged.
