# Dashboard Customization & Settings Redesign — Design

Date: 2026-07-16
Status: approved (user: "Do all the things you just included")

Two features, built as two sequential releases:
- **v4.2 — Customization**: widget system, custom tabs, Minecraft-inventory palette, jiggle-mode tab reorder/hide.
- **v4.3 — Settings**: tabbed Settings redesign + all new options.

They share a small backend surface (settings.json keys) and a design language, so
this single spec covers both; each ships and is verified independently.

---

## Feature 1 — Dashboard customization (v4.2)

### Goal
Let the user (a) reorder and hide/show the top tabs by long-pressing into a
"jiggle" edit mode (Apple-home-screen style), and (b) create their own named
custom tabs composed of individual widgets dragged from a Minecraft-style
inventory palette, arranged in a resizable snap-to grid. Built-in tabs keep
their current fixed layouts.

### Core concepts

**Widget** — an atomic, self-contained dashboard card. Each has:
`{ id, name, icon, category, defaultW (1|2 cols), minH, render(ctx) }`.
Many existing cards are already standalone components (`SleepDebt`, `CompareChart`,
`LongTrends`, `SportVolume`, `MonthHeatmap`, `WeekReview`, `Journal`, `CoachText`
brief, `RouteMap`); the gauges/rings/stat-tiles currently inline in tabs are
extracted into small widget components. The registry lives in
`frontend/src/widgets/registry.jsx` and is the single source of truth for what
can be placed.

**DashboardContext** — a React context that provides everything a widget needs to
render without prop-drilling: `{ metrics (primary day), trends, caps, units,
insights, perf, records, activities, onOpen }`. `App.jsx` already holds all of
this state; the active view is wrapped in `<DashboardProvider value={…}>`.
Widgets read from context via a `useDashboard()` hook. Built-in tabs are
refactored to consume the same context (no behavior change), so a widget renders
identically whether it's on its home tab or a custom tab.

**Widget catalog (initial set)** — Recovery gauge, Sleep score ring, Sleep stages,
Sleep debt, HRV trend, RHR trend, Body Battery, Training readiness, Strain
breakdown, Weekly volume, Recovery-vs-Sleep/Strain compare, Month heatmap,
Long-term trends, VO₂max/perf tiles, Running tolerance, Race predictions,
Personal records, Coach brief, Journal, Weekly review, and a set of single-metric
stat tiles (SpO₂, skin temp, recovery time, resting HR, respiration). Each entry
declares its data dependency so it can gray out with "No data" honestly (never
fabricated) when the metric is absent.

### Layout & persistence
- Custom-tab layout uses **react-grid-layout** (`react-grid-layout` npm) — a
  purpose-built resizable/draggable dashboard grid with responsive breakpoints.
  Widgets snap to a column grid, span 1–2 columns, drag to reorder, drag a corner
  to resize (height in row units). Reflows to a single column on phone width.
- Persistence is entirely in `settings.json` (no new health data, no new API):
  - `tab_order`: ordered list of tab keys, including built-ins and custom-tab ids.
  - `hidden_tabs`: existing key, extended to any tab key.
  - `custom_tabs`: `[{ id, name, icon, layout: [{ i: widgetId, x, y, w, h }] }]`
    where `layout` is the react-grid-layout array.
- All custom-tab content is rendered client-side from existing endpoints
  (`/api/today`, `/api/trends`, `/api/insights`, `/api/coach/*`), so a custom tab
  is pure configuration.

### Jiggle / edit mode
- Enter via long-press on the tab bar OR an explicit "Edit tabs" (pencil) affordance;
  exit via a "Done" button. In edit mode:
  - Tabs wobble (framer-motion keyframe rotation, respects
    `prefers-reduced-motion`), show a drag handle to reorder and a ✕ to hide.
  - A ＋ chip creates a new custom tab (prompts name + icon from an emoji/icon set).
  - Inside a custom tab, each widget shows a remove (✕) and resize handle, and an
    **"＋ Add widget"** button opens the inventory palette.
- Tab reordering uses `@dnd-kit/sortable` (lightweight, accessible) for the
  horizontal tab strip. (react-grid-layout handles the in-tab grid.)

### Minecraft inventory palette
- A modal styled like the Minecraft creative inventory: a dark grid of square,
  beveled "item slots", each showing a widget's icon + short name. Hover
  highlights the slot; category chips (Recovery / Sleep / Training / Activities /
  Coach) filter the grid; a search box filters by name. Drag a slot into the grid
  (or click to append). Slots already placed on the current tab are dimmed with a
  "✓ added" marker. Styling is on-theme (pixel border, slot bevel) but stays
  legible in light/dark and on mobile (grid reflows, becomes tap-to-add).

### Backend (v4.2)
- `settings.py`: add `tab_order` (list[str]), `custom_tabs` (list[dict]) to
  DEFAULTS with validation (drop unknown widget ids, clamp grid coords, cap number
  of custom tabs at e.g. 10 and widgets/tab at e.g. 30, sanitize names/icons).
- No new endpoints; everything flows through `/api/settings`.

---

## Feature 2 — Settings redesign (v4.3)

### Goal
Replace the single scrolling Settings modal with a **tabbed Settings** dialog
(left rail on desktop, top segmented control on mobile) and add the option set
below. Existing options are preserved and re-homed.

### Sections & options (✦ = new)

**⚙ General** — units · date style · theme; ✦ accent color (preset palette) ·
✦ extra themes (midnight / slate / high-contrast) · ✦ density (comfortable/compact) ·
✦ default tab on launch · ✦ week starts Mon/Sun · ✦ weather units °C/°F ·
✦ 12/24-hour clock.

**▦ Dashboard & Tabs** — ✦ manage tabs (reorder / hide / show) mirroring jiggle
mode · ✦ create & manage custom tabs · ✦ reset layout to default.

**❤ Recovery & Metrics** — baseline window; ✦ custom band thresholds
(green/amber cutoffs) · ✦ HRV-vs-RHR weighting slider (default 0.70/0.30) ·
✦ sleep-need override · ✦ max HR for zone accuracy.

**⟳ Sync & Data** — sync interval · export JSON/CSV · switch account · data folder;
✦ sync-on-launch toggle · ✦ pause syncing · ✦ backup & restore (single file:
settings + custom tabs + journal).

**🤖 AI Coach** — enable · API key · model picker (Sonnet 5 / Opus 4.8 / Haiku 4.5);
✦ coach tone (concise / detailed / tough-love / encouraging) ·
✦ auto-generate the morning brief · ✦ workout defaults (warmup length, pace-vs-HR
target preference) · ✦ monthly spend reminder.

**📱 Phone & Sharing** — phone access · access PIN · PWA/Tailscale help text.

**ℹ About** — version · changelog · GitHub · watch model · licenses.

### Backend (v4.3)
- `settings.py`: add + validate all new keys (accent_color, theme extended,
  density, default_tab, week_start, weather_units, clock, recovery_bands,
  hrv_weight, sleep_goal_min, max_hr, sync_on_launch, sync_paused, coach_tone,
  coach_auto_brief, coach_warmup_default_s, coach_target_pref, coach_budget_reminder).
- `recovery.py`: `hrv_weight` and `recovery_bands` feed the recovery score and the
  green/amber/red band mapping (currently hard-coded 0.70/0.30 and fixed cutoffs).
  Rescore history when these change (existing rescore path).
- `theme.js` / CSS: accent color and named themes applied as CSS custom
  properties; band colors respect `recovery_bands`.
- `coach.py`: `coach_tone` adjusts the system prompt; `coach_auto_brief` triggers
  brief generation on the daily sync; workout defaults seed the coach prompt.
- Backup/restore: `GET /api/config-backup` (settings + journal + custom_tabs as
  one JSON) and `POST /api/config-restore` (validated merge). Distinct from the
  existing health-data export.
- `sync_paused` / `sync_on_launch` gate the scheduled sync loop.

---

## Non-goals / preserved constraints
- No reordering of cards *inside* built-in tabs (explicitly out of scope).
- Local-first preserved: custom tabs and all settings live in `settings.json`;
  nothing new leaves the machine. No fabricated data — empty widgets show "No data".
- The coach's Garmin-write path and confirm-before-push flow are unchanged.
- TDD for all backend logic; verify against the real installed app; ship each
  release via tag → CI (with the freeze guard) → install.

## Testing
- Backend: settings validation (new keys, clamping, unknown-widget pruning),
  recovery weighting + band math, backup/restore round-trip, coach-tone prompt
  wiring.
- Frontend: widget registry renders every widget from a mock context; custom-tab
  layout persists and reloads; jiggle-mode reorder/hide writes `tab_order`/
  `hidden_tabs`; inventory add/remove updates `custom_tabs`. Playwright screenshots
  on the real installed app for both releases.

## Implementation phases
1. **v4.2**: DashboardContext + widget registry (extract inline cards) → settings
   keys (tab_order/custom_tabs) → jiggle-mode tab reorder/hide (@dnd-kit) → custom
   tab grid (react-grid-layout) → Minecraft inventory palette → verify + release.
2. **v4.3**: tabbed Settings shell → General options (accent/theme/density/etc.) →
   Recovery weighting + bands (recovery.py) → Sync options + backup/restore →
   Coach options (tone/auto-brief/defaults) → verify + release.
