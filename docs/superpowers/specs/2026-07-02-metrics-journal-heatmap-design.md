# v3.4.0 — Recovery fix, all-day Strain, Journal, Calendar heatmap

Date: 2026-07-02
Status: Approved (design)

## Problems (diagnosed against the user's real data)

1. **Recovery never loads.** `recovery_score` hardcodes `BASELINE_MIN_DAYS = 14`,
   but the user's `baseline_window_days` setting is 7 — history can never reach
   14 within a 7-day window, so a score is mathematically impossible. Even at 30
   days the user had 13 HRV days (one short). Scores are also computed once at
   sync time and never recomputed, so fixes/settings changes don't heal history.
2. **Strain is workout-only.** 30 days of data → strain on exactly 1 day. Daily
   life (steps, intensity minutes, active calories) counts for nothing.

## Fixes & features

### 1. Recovery that loads (and heals)

- Minimum history scales with the window: `min_days = min(14, max(4, window // 2))`
  → a 7-day window needs 4 days; large windows still cap at 14.
- `recovery_score(...)` gains a `min_days` parameter (default keeps old behavior
  for callers that pass nothing).
- **Rescore pass**: `rescore_history(db_path, window)` recomputes recovery AND
  strain for every stored day from already-stored data (no Garmin calls),
  called at the end of every `run_sync` and after `POST /api/settings` changes
  `baseline_window_days`. This instantly fills history after this release.
- **Progress surfaced**: `/api/today` gains
  `baseline: {have: <days of HRV+RHR history>, need: <min_days>}`; the Recovery
  gauge shows "Baseline 3/4 days" instead of a vague "Building baseline".

### 2. All-day Strain

`strain_score(activities_for_day, day_metrics=None)` combines:
- workout load (unchanged: `training_load`, fallback duration×HR), plus
- **daily-life load** from stored day metrics:
  `intensity_load = moderate + 2×vigorous` (Garmin's own weighting) and
  `steps_load = 2.5 × (steps / 1000)`.
- Same saturating curve `100·(1−exp(−total/150))` on the combined total.
- Returns a score when ANY component has data (a 0-step day scores ~0; a day
  with no steps, no intensity, and no workouts stays `None` — no fabrication).
- Known approximation (documented in the docstring): workouts also raise steps
  and intensity minutes, so components overlap slightly; acceptable for a
  0–100 wellness estimate.
- Historical days get strain wherever stored data allows (via the rescore pass);
  backfilled days that only have HRV/RHR/sleep stay `None`.

### 3. Journal (Whoop-style, local-only)

- New table `journal(date TEXT PRIMARY KEY, tags TEXT json, note TEXT,
  updated_at TEXT)`.
- **Fixed tag set (v1, no custom tags):** `alcohol, caffeine_late, late_meal,
  high_stress, sick, travel, screens_in_bed, nap`.
- API:
  - `GET /api/journal/<date>` → `{date, tags, note, saved}` — when the date has
    no entry, `tags` are **pre-filled from the most recent saved entry before
    that date** (user requirement: "saves your past answers by default; change
    only what changed") and `saved` is `false`.
  - `POST /api/journal/<date>` `{tags, note}` → upsert, returns saved entry.
- UI: a Journal card on the **Today tab** (both morning/afternoon views): tag
  chips you toggle + a one-line note; saves on change; shows "prefilled from
  last entry" until first save of the day.
- **Correlations**: `insights.journal_correlations(daily, entries)` — for each
  tag with ≥4 tagged and ≥4 untagged days that have next-day recovery, report
  the mean delta when ≥3 points ("Alcohol days: next-day recovery −12").
  Merged into the existing `/api/insights` `correlations` list.

### 4. Calendar heatmap (Trends tab)

- New `MonthHeatmap` component at the top of the Trends tab: a month grid
  (Mon–Sun columns), colored by the selected metric — Recovery (band colors),
  Sleep (purple scale), Strain (orange scale); gray = no data. Metric toggle +
  prev/next month arrows. Fetches `getTrends(180)` itself (existing endpoint).
- Clicking a day is out of scope for v1 (the Trends tab is not day-browsable).

## Out of scope (YAGNI)
Custom journal tags, editing past days' journals from the UI, notifications,
per-tag charts.

## Testing
TDD for: min-days scaling, rescore pass (fills a synthetic history), all-day
strain (components, no-fabrication, monotonicity), journal CRUD + prefill
semantics + correlations, `/api/today.baseline`. Existing 121 tests stay green.
Frontend verified in the preview (Today journal card, Trends heatmap, gauge
progress label) in both themes.

## Release
v3.4.0; rescore heals history on first launch after update.
