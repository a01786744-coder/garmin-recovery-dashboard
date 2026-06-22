# Garmin Dashboard v2 — Expansion Design (tabs, metrics, maps, animations)

**Date:** 2026-06-21
**Builds on:** [2026-06-20-garmin-recovery-dashboard-design.md](2026-06-20-garmin-recovery-dashboard-design.md)
**Status:** Approved (direction); per-phase plans to follow.

Expand the working single-view dashboard into a multi-tab, animated, Whoop-style
app surfacing far more Garmin Forerunner 970 data, including run-route maps. All
method names below are verified present in the installed `garminconnect` 0.3.2.

## Scope decisions (from brainstorming)

- **New dependencies (approved):** `framer-motion` (animations), `leaflet` +
  `react-leaflet` (maps), `date-fns` (date/duration formatting). Ask before
  adding anything beyond these three.
- **Run maps:** dark CartoDB/OSM **basemap tiles** under the route polyline.
  This is a deliberate, documented relaxation of the original "no third-party
  servers" MUST — **for map tiles only.** No health/account data is sent; tile
  requests do reveal the geographic area of runs to the tile host. Documented in
  the README and in code near the map component.
- **Strava:** deferred to a future phase (not built now).
- **Animation style:** polished & smooth (page/tab transitions, gauge
  count-up/arc draws, micro-interactions), not flashy.
- **No-fabrication rule still holds:** every new metric renders "No data" when
  Garmin returns nothing; situational metrics (SpO2, weight, hydration, hill
  score, lactate threshold, etc.) degrade gracefully.

## Phasing (each phase = its own plan + review cycle)

### Phase 1 — Backend metrics & data layer
Fetch, normalize, store, and serve the new data. No UI changes required to ship.

New/expanded data:
- **Expanded daily summary** (from `get_user_summary`): floors, intensity
  minutes (moderate/vigorous + weekly goal via `get_intensity_minutes_data`),
  highly-active/active/sedentary seconds, resting vs active calories, total
  distance.
- **Sleep detail** (from existing `get_sleep_data`): Sleep Need
  (baseline/actual/feedback), per-component sleep scores
  (deep/light/rem/restlessness/awakeCount), restless moments, overnight
  respiration avg, `avgOvernightHrv`, bodyBatteryChange.
- **Training** (`get_training_status`): training status label, acute load,
  chronic load / ACWR ratio, load focus (aerobic low/high, anaerobic),
  weekly load, fitness trend. **Readiness sub-factors**
  (`get_training_readiness` / `get_morning_training_readiness`): sleepScore,
  recoveryTime, hrvFactorPercent, acuteLoad, stressHistoryFactorPercent.
- **Performance trends:** `get_max_metrics` (running + cycling VO2max, fitness
  age, heat/altitude acclimation), `get_fitnessage_data`, `get_race_predictions`
  (5K/10K/HM/marathon), `get_endurance_score`, `get_hill_score` (situational).
- **Respiration** (`get_respiration_data`): waking/sleep averages.
- **Intraday curves** (stored as JSON blobs per date): all-day HR
  (`get_heart_rates`), stress + Body-Battery arrays (`get_stress_data` /
  `get_body_battery`), overnight HRV readings (`get_hrv_data.hrvReadings` +
  baseline band), respiration array.
- **Personal records** (`get_personal_record`), **RHR trend** (`get_rhr_day`),
  **gear/shoe mileage** (`get_gear*`, situational), **device freshness**
  (`get_device_last_used`).
- **Activity detail** (per activity, fetched on demand/cached):
  `get_activity` summary, `get_activity_details` (GPS `geoPolylineDTO.polyline`
  + per-sample HR/pace/elevation/cadence), `get_activity_splits`,
  `get_activity_hr_in_timezones`, `get_activity_weather`.

Storage: extend `daily_metrics` with new scalar columns; add `daily_intraday`
(date, metric, json), `activity_detail` (activity_id, json blobs), `perf_metrics`
(date, vo2max_cycling, fitness_age, race predictions, endurance_score, etc.),
`personal_records`. Keep the paced, 429-tolerant sync model; intraday/activity
detail fetched for recent days only (cost control).

New endpoints: `/api/sleep`, `/api/training`, `/api/performance`,
`/api/activity/<id>`, `/api/intraday?date=&metric=`, plus expanded `/api/today`
and `/api/trends`.

### Phase 2 — Tabbed UI + animations + visual polish
- Tab navigation: **Overview · Sleep · Strain & Training · Activities · Trends**.
- `framer-motion`: tab/page transitions, gauge count-up + arc draw on mount,
  card stagger-in, hover/press micro-interactions, skeleton loading states.
- Refined dark design system (tokens for color/spacing/typography), consistent
  cards, intraday line/area charts (recharts), zone bars, rings.
- Every tab honors the "No data" rule and the "custom metric" labeling for
  Recovery/Strain.

### Phase 3 — Run maps
- `react-leaflet` + CartoDB dark-matter tiles; draw the activity's GPS polyline
  with start/end markers, fit-bounds, elevation/pace context. Splits table +
  HR-zone distribution beside the map. Documented tile-privacy note in-code.

## Constraints carried forward
- Fully local except Garmin Connect (and now map tiles, as noted above).
- Credentials only via gitignored `.env`; never logged.
- No fabricated data; graceful "No data" everywhere.
- Paced + 429-tolerant sync; app never crashes on auth/rate failures.
- Only build what's specified per phase; ask before new dependencies.
