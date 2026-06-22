# Phase 2 — Tabbed UI + Animations + Visual Polish

> Builds on Phase 1 (backend serves all metrics). Verified by `npm run build` + a live preview/screenshot pass (UI is not unit-tested).

**Goal:** Replace the single dashboard view with a polished, animated, five-tab Whoop-style app on the real Phase 1 data.

**Tech:** React 18 + Vite + Tailwind, framer-motion (transitions/animation), recharts (charts), date-fns (formatting). Dark theme.

## Design system

- `src/theme.js` — tokens: band colors (green `#22c55e`, yellow `#eab308`, red `#ef4444`), accents, neutral scale, zone colors.
- `src/index.css` — base dark background, font smoothing, custom scrollbar, keyframe utilities.
- Primitives in `src/components/ui/`:
  - `Card.jsx` — rounded `bg-neutral-900/60` panel with subtle border + hover lift (framer-motion `whileHover`).
  - `AnimatedGauge.jsx` — circular gauge with arc-draw on mount + count-up number (framer-motion `useSpring`/`animate`); null → "No data"/"Building baseline".
  - `Ring.jsx` — small progress ring (intensity minutes, goals).
  - `StatTile.jsx` — label + animated value + optional sub/trend.
  - `Sparkline.jsx` / `MiniArea.jsx` — recharts wrappers for intraday curves with `connectNulls={false}`.
  - `ZoneBar.jsx` — HR-zone / load-focus stacked bar.
  - `NoData.jsx` — consistent empty state.
  - `SectionTitle.jsx`, `Badge.jsx`.
- `src/format.js` — `secsToPace`, `secsToHms` (race times), `secsToHm` (durations), `minutesToHm` (sleep need), date helpers via date-fns.

## API client (`src/api.js` additions)

`getIntraday(date, metric)`, `getPerformance()`, `getActivity(id)`. Keep existing `getToday/getTrends/getSyncStatus/postSync`.

## Shell (`src/App.jsx`)

- Sticky top bar: title + "Estimated · custom metric" disclaimer link + `SyncHeader` (last-synced + Retry).
- Tab bar: Overview / Sleep / Strain & Training / Activities / Trends, with an animated active-pill (framer-motion `layoutId`).
- `AnimatePresence` page transition (fade + 8px slide) on tab change.
- Single poll of `/api/today` + `/api/trends?days=14` on mount + 60s interval; tabs read from a shared `data` context/prop. Activity detail + intraday fetched per-tab on demand.
- Skeleton loaders while first load is pending; never crash on fetch error (keep last good).

## Tabs (all honor "No data" + custom-metric labeling)

1. **Overview** (`tabs/Overview.jsx`) — three `AnimatedGauge`s (Recovery band-colored + "Building baseline" gating, Sleep, Strain) with the custom-metric caption; tiles: Body Battery, Resting HR, intensity-minutes `Ring`, calories (active/resting split), floors, Training Readiness; recent-activities mini-list. Cards stagger-in.
2. **Sleep** (`tabs/Sleep.jsx`) — Sleep score gauge + Sleep Need (actual vs baseline, minutes→h:m); stage breakdown bar + component sub-scores (deep/REM/light/restlessness) as small rings; overnight curves from `/api/intraday` (HRV readings vs baseline band, respiration); restlessness/awake count tiles.
3. **Strain & Training** (`tabs/Training.jsx`) — Training Status badge; **ACWR gauge** (acute vs chronic load with optimal band); load-focus `ZoneBar` (aerobic-low/high/anaerobic vs targets); Training Readiness with sub-factor breakdown bars (sleep/recovery/ACWR/HRV/stress factor %); intensity-minutes weekly progress; all-day stress curve (`/api/intraday`).
4. **Activities** (`tabs/Activities.jsx`) — activity list (type, date, duration, avg HR, distance, training load); selecting one loads `/api/activity/<id>` → summary + splits table + HR-zone `ZoneBar` + pace. (Map added in Phase 3 — leave a placeholder slot.)
5. **Trends** (`tabs/Trends.jsx`) — 14-day HRV (with baseline band) + RHR line charts; VO2max + Fitness Age tiles; **race predictions** (5K/10K/HM/M as paces/times); Endurance Score gauge with classification ladder; **personal records** list.

## Animations (framer-motion, "polished & smooth")

- Page/tab transitions via `AnimatePresence`.
- Gauges: arc draws + number counts up on mount/value change.
- Cards: stagger-in (`staggerChildren`), `whileHover` lift, `whileTap` press.
- Active tab pill via shared `layoutId`.
- Charts fade/grow in. Respect reduced-motion (`useReducedMotion`).

## Verification

- `npm run build` succeeds.
- Live preview (dev server or Electron) + screenshots of each tab on real data; confirm "No data"/"Building baseline" states render where data is absent (e.g., Recovery, sparse trends) and rich states render where present (today's sleep, HR curve, ACWR, race predictions, the 06-20 run).

## Constraints carried forward

- No fabricated data; graceful empty states everywhere. Recovery/Strain labeled custom.
- Only the approved deps (framer-motion, date-fns; leaflet in Phase 3).
- Frontend reads only the local API.
