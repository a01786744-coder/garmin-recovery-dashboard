# Changelog

All notable changes to the Garmin Recovery Dashboard. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/). Dates are YYYY-MM-DD.

## [3.2.0] — 2026-06-30

### Added
- **Today tab** — a time-aware daily recap: a **Morning report** before noon and
  an **Afternoon recap** after, with a toggle. Morning shows Recovery / Sleep /
  Training-Readiness gauges, last night's sleep + stages, and HRV / RHR /
  Body-Battery vitals; afternoon shows Body Battery (and how much it has drained
  since the morning), stress, intensity, steps / calories / floors, and the day's
  workouts. A plain-language recap line summarises each, computed from your data
  (no fabrication — clauses without data are dropped).
- **Light / dark theme** — a sun/moon toggle in the header; the choice is
  remembered. Dark mode is unchanged.
- **Custom app icon** — a recovery-ring + heartbeat mark on Windows and macOS,
  replacing the default Electron icon.
- **Browse past days** — a date navigator (Prev / Next / Latest) steps back
  through any previous day's Overview, Sleep, and Strain & Training views.
- **Update notifier** — a dismissible banner when a newer GitHub release exists
  (one anonymous GitHub call on launch; opt out via the `check_updates` setting).

### Distribution
- **macOS support.** A GitHub Actions workflow builds the Windows `.exe` and a
  macOS `.dmg` (Apple Silicon) in the cloud and attaches them to a GitHub Release
  on each version tag — so a Mac build is produced without a Mac. Both are
  unsigned (first-open: Windows "Run anyway"; macOS right-click → Open).
- Cross-platform freeze script (`scripts/freeze.js`); `dist:win` / `dist:mac`.

### Fixed
- electron-builder no longer attempts an auto-publish in CI (it built the
  installer, then failed for lack of a token); publishing is a separate
  tags-only step.

### Notes
- 110 backend tests (added: recap summaries, day-browser endpoints).

## [3.1.3] — 2026-06-23

### Fixed
- **"Can't reach the local service" on launch:** the first sync ran on the main
  thread *before* the API server bound its port, so a long first backfill (made
  longer by the v3.1.2 sleep re-backfill) delayed the server coming up and the UI
  timed out. The startup sync now runs in a background thread so the server binds
  immediately (~1s); the UI also retries the connection for ~30s to cover a cold
  start.

## [3.1.2] — 2026-06-23

### Added
- **Detected watch model** in the header: instead of a hardcoded "Forerunner
  970", the app reads the user's actual device from Garmin (e.g. "Garmin fēnix 7",
  "Garmin Forerunner 165") and displays it.

### Fixed
- **Sleep history was missing:** the backfill only fetched HRV + RHR for past
  days, so the Sleep trend/detail showed only today. The backfill now includes
  sleep, a new **"Sleep score — history"** card was added to the Sleep tab, and a
  one-time re-backfill fills in sleep for installs that already had data.

## [3.1.1] — 2026-06-23

### Fixed
- **Login loop:** a transient auth error during the post-login sync (e.g. a token
  refresh racing a Garmin rate-limit) no longer bounces the user back to the
  login screen. The app now only shows login when there is genuinely no saved
  token; a hiccup stays on the dashboard as "sync failed · Retry".

## [3.1.0] — 2026-06-23

### Added
- **One-click Windows installer** (`npm run dist`): the Python backend is frozen
  with PyInstaller (including `garminconnect` + its native `curl_cffi`) and
  bundled with Electron into an NSIS installer. Recipients need **no Python, no
  Node, no terminal** — they run a single `.exe`, click through the one-time
  (unsigned) SmartScreen prompt, and it installs per-user with a desktop shortcut
  and launches to the login screen. The app still auto-detects each watch's
  capabilities, so one installer works on any Garmin model.

## [3.0.0] — 2026-06-23

Distribution-ready: one build any friend can install and log into, that shows
only the tabs/cards their watch reports — plus Whoop-style drill-down detail
views and a tested insights engine. All data stays local; no fabrication; the
app never crashes on Garmin auth/rate-limit failures.

### Added — Distribution & multi-device
- **Per-user state in the OS user-data dir** (DB, auth token, capability profile,
  settings, logs) — nothing user-specific is written into the project folder.
  Electron passes the path to the backend on spawn.
- **In-app login + MFA**: a first-run login screen; new users authenticate
  entirely through the UI (no `.env` editing). Only Garth OAuth **tokens** are
  stored (owner-only file perms); the password is used once and never persisted
  or logged. Silent token refresh with re-login fallback; logout / switch-account.
- **Watch-capability detection**: tabs and cards render conditionally from a
  detected capability profile. Sticky (once a metric is ever seen it stays) with
  a readiness gate, so a metric absent today still shows "No data" while a metric
  the watch never reports is hidden — and an upgraded watch unlocks tabs
  automatically.
- **Settings panel** (gear): units (metric/imperial), sync interval, Recovery
  baseline window, per-tab visibility toggles, and account switch (which clears
  the previous account's local data for a clean handoff).
- **Distribution polish**: onboarding/backfill progress, redaction-filtered local
  log, **CSV + JSON export** of your own data, local-timezone display of Garmin
  UTC timestamps, and an unofficial/not-medical-advice disclaimer.
- **Double-click launcher** (`Start Dashboard.bat`) + desktop shortcut — no
  terminal needed.

### Added — Detail views & insights
- **Slide-in detail panel** on any metric (gauge, tile, or trend card): up to
  90-day evolution graph with an average reference line, a stat row
  (current / 7-day / 30-day / min / max / Δ-vs-avg), today's intraday curve where
  available, and metric-specific insights.
- **Per-split HR & pace graphs** in activity detail.
- **Tested insights engine** (`/api/insights`): auto-insights (HRV/RHR trends,
  "best in N days"), streaks (green-recovery, workout, days-worn, sleep-goal),
  this-week-vs-last recap, and data-driven correlations (e.g. sleep → next-day
  recovery). Thin data yields "not enough history yet," never invented numbers.
- `/api/trends` gains a performance-metric history series.

### Fixed
- **Empty-morning dashboard**: before the watch uploads last night's sleep/HRV,
  today's row is empty. The dashboard now shows the most recent day with
  last-night data (with an "as of <date>" note) instead of going blank.

### Notes
- No new runtime dependencies beyond those already declared. 96 backend tests.

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

[3.2.0]: #320--2026-06-30
[3.1.3]: #313--2026-06-23
[3.1.2]: #312--2026-06-23
[3.1.1]: #311--2026-06-23
[3.1.0]: #310--2026-06-23
[3.0.0]: #300--2026-06-23
[2.0.0]: #200--2026-06-21
[1.0.0]: #100--2026-06-20
