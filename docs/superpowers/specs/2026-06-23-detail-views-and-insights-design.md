# Detail Views, Evolution Graphs & Insights — Design

**Date:** 2026-06-23
**Status:** Approved (design); pending implementation plan
**Branch:** build-dashboard

A Whoop-style upgrade: clicking any metric opens a slide-in **detail panel** with
its evolution over time, summary stats, and insights; plus four "fun + useful"
features — auto-insights, streaks, a weekly recap, and correlations — all computed
from the user's real stored data.

## Goals

1. **Drill-down on everything:** every gauge, stat tile, and trend card opens a
   detail panel with an up-to-90-day evolution graph, summary stats, metric-specific
   extras, and relevant insights.
2. **Richer activity detail:** per-split HR and pace graphs (from already-stored
   lap data — no new Garmin calls).
3. **Insights engine:** auto-insights, streaks/milestones, weekly recap, and
   correlations, surfaced on Overview and inside detail panels.

## Non-goals / preserved principles (MUST)

- **No fabricated data.** Every number is computed from stored data. Sparse data
  yields explicit "Not enough history yet" states — never a placeholder value.
- **Capability-gated.** Detail panels and insights never appear for metrics the
  watch doesn't report (the existing `caps` rules govern; hidden cards/tabs stay
  hidden, and their detail panels are unreachable).
- **Custom metrics labeled.** Recovery and Strain keep their "estimated · custom"
  labels in panels too.
- **Local-first, never crashes.** Insights/perf come from local SQLite; fetch
  failures keep last-good UI. No new third-party network calls.
- **No new dependencies.** Reuse React, framer-motion, recharts.

## Data available (no new Garmin probing required)

- `GET /api/trends?days=N` returns `days` (full daily_metrics rows for the last N)
  plus `hrv` / `rhr` series. Any daily field's 90-day evolution derives from `days`.
  The frontend fetches up to 90 days on demand when a panel opens.
- Intraday (HR, stress, body battery, overnight HRV) is today-only via
  `/api/intraday` — used for "today's curve" in panels.
- Activity `splits` (lapDTOs: distance, duration, averageSpeed, averageHR,
  elevationGain) are already stored per activity — used for per-split graphs.
- Performance history (VO₂max/endurance/race) needs exposing (one perf row is
  stored per sync day): add a `perf` series to `/api/trends`.

## Component & module design

### Backend

**`backend/db.py`** — add `get_perf_history(path, days) -> list[dict]` (perf rows
within the last `days`, ascending). Read-only; no schema change.

**`backend/api.py`**
- `/api/trends` response gains `"perf": db.get_perf_history(db_path, days)`.
- New `GET /api/insights` → `{weekly, streaks, insights, correlations}` from
  `backend/insights.py`, computed from stored daily rows (+ activities). No Garmin
  calls.

**`backend/insights.py`** (new, fully unit-tested) — pure functions over a list of
daily rows (ascending) and activity rows:

- `weekly_recap(daily) -> dict`: averages of `recovery_score`, `sleep_score`,
  `strain_score`, `hrv_last_night`, `rhr` for the last 7 days vs the prior 7, with
  per-metric delta; plus workout count and total strain per week. Each field only
  averaged over non-null days; `null` delta when a side has no data.
- `streaks(daily, activities) -> dict`: current run-lengths ending today/most-recent —
  `green_recovery` (recovery_score ≥ 67), `worn` (any data present), `workout`
  (a day has ≥1 activity), `sleep_goal` (sleep_score ≥ 70). Each returns the current
  length (0 when broken).
- `auto_insights(daily) -> list[dict]`: ranked `{text, tone}` observations, each
  emitted only when its inputs have enough non-null history:
  - HRV 7-day-avg vs prior-7 % change ("HRV trending up 8%"), same for RHR (lower
    is better wording).
  - "Best `<metric>` in N days" for recovery/sleep/hrv when today is the max over
    ≥10 days of history.
  - Recovery 7-day trend direction (up/down/flat).
  - Returns `[]` when history is too thin; the UI shows a "building insights" note.
- `correlations(daily) -> list[dict]`: fixed, descriptive pairings computed only
  with ≥ `MIN_PAIRS` (e.g. 8) paired days and a meaningful gap:
  - Sleep duration (sum of stage seconds) > median split → avg **next-day**
    recovery, high vs low group, reported as "+X points".
  - Strain > median split → avg next-day recovery.
  Each result: `{text, detail}`; omitted when not enough data or the gap is < a
  small threshold. Descriptive language only (no causal claims).

Constants (`MIN_*`, thresholds) live at the top of `insights.py`.

### Frontend

**`src/detail/registry.js`** — `METRICS`: map of metric key →
`{label, field, unit, accent, band?, intraday?, custom?, extras?, insightKeys?}`.
Drives the panel for: recovery, sleep, strain, body_battery, rhr, hrv,
training_readiness, stress, steps, floors, intensity, vo2max, endurance, race,
plus the HRV/RHR trend cards. `field` indexes into a daily row (or `perf.*`).

**`src/detail/DetailPanel.jsx`** — slide-in overlay (framer-motion: x-slide on wide,
full-screen fade on narrow; Esc/✕/scrim-click closes). On open, fetches
`getTrends(90)` once (cached in App and passed down). Renders:
- Header (label, current value + unit, accent; custom-metric note when `custom`).
- `EvolutionChart`: line/area of `days[].<field>` (or `perf[].<field>`) with a
  dashed average reference line; "Not enough history yet" when < 2 points.
- `StatRow`: current, 7-day avg, 30-day avg, min, max, Δ-vs-avg (all from the series,
  null-safe).
- `extras`: optional render hook per metric — Recovery → HRV & RHR mini-trends;
  Sleep → stage-composition stacked area + Sleep Need; metrics with `intraday` →
  today's intraday curve (existing `/api/intraday`).
- `InsightList`: insights whose `insightKeys` match this metric.

**Click-wiring** — Overview gauges/tiles, Sleep/Training/Trends cards and tiles get
an `onClick` that calls `openDetail(metricKey)` (lifted to App). Cursor/hover affordance
added. Gated cards remain non-rendered (so unreachable), preserving capability rules.

**Activities** — `Detail` gains two small charts from `data.splits`: HR-per-split and
pace-per-split (reusing `MiniArea`/a simple bar). Shown only when splits exist.

**Overview insights section** — a compact block of cards:
- `InsightsCard` (top 2–3 auto-insights, rotating),
- `StreaksCard` (current streaks with a framer-motion pop when extended),
- `WeeklyRecapCard` (this-week vs last-week deltas),
- `CorrelationCard` (one highlighted correlation).
Each shows a graceful "building…" state when its data is thin. The section is
capability-aware (e.g. no recovery streak if recovery is unsupported).

**`src/api.js`** — add `getInsights()`; `getTrends` already parameterized by days.

## Data flow

1. App fetches `/api/today`, `/api/trends?days=14` (overview), `/api/insights`,
   `/api/capabilities`, `/api/settings` as today.
2. Opening a detail panel triggers a one-time `/api/trends?days=90` fetch (cached);
   the panel reads the metric's series from it, plus `/api/intraday` for today's
   curve where relevant.
3. Insights/streaks/recap/correlations come from `/api/insights` (recomputed each
   load from local data; no Garmin calls).

## Testing

- `backend/insights.py`: unit tests for `weekly_recap`, `streaks`, `auto_insights`,
  `correlations` — including thin-data → empty/zero results (no fabrication),
  delta signs, streak breaks, and the correlation min-pairs/threshold gates.
- `backend/db.get_perf_history` + `/api/trends perf` + `/api/insights`: API tests
  with seeded rows.
- Frontend verified by build + live preview (DOM snapshots): panel opens for a
  gauge and a tile, shows an evolution graph and stats, closes; Overview shows the
  insights section; activity detail shows split charts.
- All existing backend tests (80) still pass.

## Implementation order (for the plan)

1. Backend: `get_perf_history` + `perf` in `/api/trends`; `insights.py` + `/api/insights` (+ tests).
2. Frontend foundation: `registry.js`, `EvolutionChart`/`StatRow`, `DetailPanel`, `getInsights`, App wiring to open/close + 90-day cache.
3. Click-wiring across Overview/Sleep/Training/Trends; metric extras (Recovery/Sleep/intraday).
4. Activities per-split charts.
5. Overview insights section (insights/streaks/weekly recap/correlations cards).
6. Build + live verification.

## Deliverable

Clicking any metric opens a Whoop-style detail panel with up-to-90-day evolution,
stats, and insights; activities show per-split graphs; and Overview gains a tested
insights/streaks/weekly-recap/correlations section — all from real local data, with
honest empty states and capability gating intact.
