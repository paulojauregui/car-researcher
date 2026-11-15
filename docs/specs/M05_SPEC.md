# Milestone M05 Specification: Automotive Telemetry Design System CSS (`tokens.css` & `components.css`)

## Target Files
- `src/dashboard/static/tokens.css`
- `src/dashboard/static/components.css`
- `tests/test_static_assets_unittest.py`

## Non-Negotiable Constraints
- Strictly align with `docs/DESIGN_SYSTEM.md` and `docs/UX_SPEC.md`.
- Strictly ZERO emojis in CSS comments, content properties, or test files.
- Strictly ZERO external CDN imports (`@import url("http...")`).
- `src/dashboard/static/tokens.css` defines all CSS custom properties (`--bg-*`, `--border-*`, `--text-*`, `--accent-*`, `--status-*`, `--font-*`, `--text-*`, `--space-*`, `--radius-*`, `--z-*`, `--duration-*`, `--ease-*`) plus base reset, `overflow-x: clip`, `.tabular-nums`, `.mono-readout`, `:focus-visible`, and `@media (prefers-reduced-motion: reduce)`.
- `src/dashboard/static/components.css` MUST consume CSS custom properties from `tokens.css` exclusively with **zero hardcoded hex colors** (`#...` colors prohibited in `components.css` except via `var(--...)`).

---

## 1. `src/dashboard/static/tokens.css` Requirements
Include the complete canonical token contract from `docs/DESIGN_SYSTEM.md` Section 2.2:
- 4-tier dark slate/graphite surface elevation + inset + overlay:
  - `--bg-canvas: #080B10`, `--bg-inset: #0B0F15`, `--bg-surface: #0F141C`, `--bg-surface-hover: #151C26`, `--bg-elevated: #1B2330`, `--bg-overlay: rgba(4, 7, 12, 0.80)`
- Structural hairline borders:
  - `--border-subtle`, `--border-default`, `--border-strong`, `--border-focus: #38BDF8`
- WCAG 2.2 AA Ink hierarchy:
  - `--text-primary: #F1F5F9`, `--text-secondary: #B4C0D0`, `--text-muted: #8B9BB0`, `--text-inverse: #080B10`
- Brand & Telemetry Accent tokens:
  - `--accent-primary: #0EA5E9`, `--accent-primary-hover: #38BDF8`, `--accent-primary-bg`, `--accent-telemetry: #22D3EE`, `--accent-telemetry-bg`
- Semantic Automotive Valuation Status tokens (each with foreground, `-bg`, `-border`):
  - `--status-excellent: #34D399`
  - `--status-info: #38BDF8`
  - `--status-cut: #FBBF24`
  - `--status-warn: #FB923C`
  - `--status-danger: #F87171`
- Typography (`--font-sans`, `--font-mono`), numeric scale (`--text-2xs` .. `--text-2xl`), spacing (`--space-1` .. `--space-12`), radii (`--radius-sm/md/lg`), `--container-max: 1600px`, shadows, z-index layers, motion tokens, `.skip-link`, `.sr-only`, `.tabular-nums`, `.mono-readout`, `:focus-visible`, `@media (prefers-reduced-motion: reduce)`.

---

## 2. `src/dashboard/static/components.css` Requirements
Cover every component & workspace class across `docs/UX_SPEC.md` and `docs/DESIGN_SYSTEM.md`:
- App shell: `.app-shell`, `.app-container`, `.console-header`, `.brand-emblem`, `.scope-chip`, `.provenance-pill` (`--live`, `--offline`, `--fixture`), `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.btn-danger`, `.btn-icon`, `.control-input`, `.control-select`, `.control-label`
- Banners: `#degraded-banner` (`.degraded-banner`), `#scan-status-banner` (`.scan-banner`, `--running`, `--completed`, `--error`, `--unavailable`)
- Primary Workspace Navigation: `.workspace-nav`, `.workspace-tablist`, `.workspace-tab` (`[aria-selected="true"]`), `.workspace-tab__count`, `.workspace-panel[hidden]`
- Workbench Workspace (`#workspace-workbench`):
  - `.kpi-strip`, `.kpi-card`, `.kpi-card--excellent`, `.kpi-label`, `.kpi-value`, `.kpi-sub`
  - `.filter-bar`, `.filter-grid`, `.view-toggle`, `.view-toggle-btn`
  - `.triage-bar`, `.triage-tabs`, `.triage-tab`, `.triage-count`, `.export-actions`
  - `.deals-grid`, `.deal-card` (`.is-pinned`), `.deal-card__media` (`height: 176px`), `.deal-card__overlay-tl`, `.deal-card__overlay-tr`, `.deal-card__body`, `.deal-card__price-row`, `.deal-card__badges`, `.deal-card__factors`, `.factor-bar`, `.deal-card__meta`, `.deal-card__footer`, `.vin-chip`
  - `.table-scroll` / `.precision-table-wrap`, `.precision-table`, sticky `thead th`, sortable `th button[aria-sort]`, `tr.is-pinned`, `.num-col` (`text-align: right`)
  - `.cohort-range-bar`, `.cohort-track`, `.cohort-buyzone`, `.cohort-iqr`, `.cohort-median`, `.cohort-marker`
  - `.market-badge` (`--excellent`, `--cut`, `--warn`, `--info`), `.score-pill`, `.safety-badge`
- Market Intelligence Workspace (`#workspace-market`):
  - `.market-grid`, `.frontier-panel`, `.frontier-controls`, `.frontier-stats`, `.frontier-svg`, `.frontier-gridline`, `.frontier-axis`, `.frontier-buyzone`, `.frontier-p25-line`, `.frontier-p50-line`, `.frontier-ols-line`, `.frontier-node`, `.chart-tooltip`, `.momentum-grid`, `.momentum-panel`, `.momentum-row`
- Arbitrage Workspace (`#workspace-arbitrage`):
  - `.platform-grid`, `.platform-card`, `.arbitrage-callout`, `.distance-bands-grid`, `.band-card`, `.band-bar-track`, `.band-bar-fill`
- Comparator Workspace (`#workspace-compare`):
  - `.compare-toolbar`, `.compare-matrix-wrap`, `.compare-table`, `.compare-slot-header`, `.compare-slot-empty`, `.compare-cell--winner`, `.compare-winner-pill`
- Floating Compare Tray (`#compare-tray`), Slide-Over Valuation Drawer (`#analysis-drawer`, `.drawer-backdrop`, `.drawer-panel`, `.drawer-header`, `.drawer-body`, `.drawer-footer`, `.price-sparkline`, `.leverage-grid`, `.tco-grid`, `.tax-credit-card`, `.recall-card`, `.complaint-card`), plus `#detail-modal` compatibility styles
- Empty, Error & `CLS = 0` Skeleton States (`.empty-state`, `.error-state`, `.skeleton`, `.skeleton-kpi`, `.skeleton-card`, `.skeleton-table-row`, `.skeleton-chart`)
- Responsive breakpoints (`< 768px`, `>= 768px`, `>= 1024px`, `>= 1280px`, `>= 1600px`) guaranteeing zero horizontal page overflow.

---

## 3. `tests/test_static_assets_unittest.py` Specification
Verify:
- `tokens.css` and `components.css` exist and are non-empty.
- Zero emojis in CSS files.
- Zero external `http://` / `https://` `@import` or `url(...)` CDN references.
- Zero hardcoded hex colors (`#[0-9a-fA-F]{3,8}`) inside `components.css` (all colors come from `var(--...)`).
- Balanced curly braces `{` / `}` in both stylesheets.
- Required tokens (`--bg-canvas`, `--bg-surface`, `--bg-surface-hover`, `--bg-elevated`, `--status-excellent`, `--status-cut`, `--status-warn`, `--status-danger`, `tabular-nums`, `prefers-reduced-motion`, `:focus-visible`) and component selectors (`.cohort-range-bar`, `.precision-table`, `.valuation-drawer` / `#analysis-drawer`, `#compare-tray`, `#degraded-banner`, `.skeleton-card`) are present.
