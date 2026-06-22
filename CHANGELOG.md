# Changelog

All notable changes to the Garmin Recovery Dashboard. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/). Dates are YYYY-MM-DD.

## [2.0.0] — 2026-06-21

A major expansion from a single dashboard view into a five-tab, animated,
Whoop-style app, with many more Forerunner 970 metrics and an interactive run
route map. All data remains local; no fabrication; the app never crashes on
Garmin auth/rate-limit failures.

### Added — Tabs & UI
- **Five-tab layout:** Overview · Sleep · Strain & Training · Activities · Trends,
  with animated tab transitions (framer-motion) and an animated active-tab pill.
- **Design system / primitives:** `AnimatedGauge` (arc-draw + count-up), `Ring`,
  `StatTile`, `MiniArea`/charts, `ZoneBar`, `Card` (stagger-in + hover lift),
  `Badge`, `NoData`, skeleton loaders. Refined dark theme with gradient backdrop.
- Respects `prefers-reduced-motion`.

### Added — Metrics (backend)
- **Expanded daily:** floors, intensity minutes (+ weekly goal), active/sedentary/
  highly-active seconds, calorie split (active/resting), distance, respiration
  (waking & sleep).
- **Sleep detail:** Sleep Need (actual vs baseline), per-component scores
  (deep/REM/light/restlessness), awakenings, overnight HRV.
- **Training:** training status, **ACWR** (acute & chronic load), load focus
  (aerobic-low/high/anaerobic), Training Readiness + 5 sub-factors.
- **Performance:** VO₂max, fitness age, **race predictions** (5K/10K/HM/Marathon),
  endurance score + classification, heat/altitude acclimation.
- **Intraday curves:** all-day heart rate, stress, Body Battery, and overnight HRV
  readings (with baseline band).
- **Personal records** and **on-demand activity detail** (GPS route, splits,
  HR-zone distribution, weather).

### Added — Run route map
- Interactive **Leaflet** map in the Activities tab drawing each activity's GPS
  polyline with start/finish markers, on a dark CartoDB basemap.
- Privacy trade-off (map tiles are the one non-Garmin network call) documented in
  `frontend/src/components/RouteMap.jsx` and the README; removable to stay fully
  local.

### Added — API endpoints
- `GET /api/intraday?date=&metric=`, `GET /api/performance`,
  `GET /api/activity/<id>`; `GET /api/today` expanded with `perf` + `records`.

### Changed
- SQLite schema expanded (new daily columns + `daily_intraday`, `perf_metrics`,
  `personal_records`, `activity_detail` tables).
- Sync now also fetches today's performance, intraday, and personal-record data
  (today-only, cost-controlled); activity detail is fetched on demand and cached.

### Fixed
- `init_db` now migrates an existing database by adding missing `daily_metrics`
  columns (older DBs no longer error on the new schema).

### Dependencies
- Added `framer-motion`, `date-fns`, `leaflet`, `react-leaflet` (frontend).

## [1.0.0] — 2026-06-20

Initial release.

### Added
- Garmin Connect auth via `garminconnect` 0.3.2 (token-cached, MFA-capable),
  credentials in a gitignored `.env`, never logged.
- **Today-first sync** model (last night's sleep/HRV filed under the wake date),
  with a paced, 429-tolerant 30-day backfill, on a 30-minute schedule, into SQLite.
- **Custom Recovery score** (HRV- & RHR-based vs a 30-day baseline; green ≥67 /
  yellow / red ≤33; "Building baseline" until ≥14 days) and **Strain** score —
  both clearly labeled as estimates, not Garmin or Whoop metrics.
- Local **Flask API** (`/api/today`, `/api/trends`, `/api/sync-status`,
  `POST /api/sync`) and a single-page React + Tailwind dashboard.
- **Electron** shell that launches the Python backend and terminates it on quit.
- No-fabrication guarantee (missing metrics → "No data"); graceful auth/rate-limit
  handling with "last synced X ago" + Retry.

[2.0.0]: #200--2026-06-21
[1.0.0]: #100--2026-06-20
