# Garmin Recovery Dashboard — Design

**Date:** 2026-06-20
**Status:** Approved (design); pending implementation plan

A personal, fully-local desktop app (Electron + local web frontend) that pulls
Garmin Connect data for a Garmin Forerunner 970 and displays it in a Whoop-style
recovery dashboard.

## Goal

Display a daily Recovery score (custom/estimated), Sleep score, Strain/load score,
HRV trend, and resting-heart-rate trend, sourced entirely from Garmin Connect via
the unofficial `garminconnect` Python library.

## Non-goals (explicit scope locks)

- No direct Bluetooth/ANT+ watch communication.
- No official Garmin Health API.
- No user accounts, cloud sync, social features, or notifications.
- No data sent to any third party other than Garmin Connect itself.
- No extra files, abstractions, libraries, or features beyond this spec. Stop and
  ask before adding any dependency not listed here, and before any destructive
  command.

## Data source

`garminconnect` v0.3.6 (garth-based auth). Confirmed: all target metrics are
supported on the Forerunner 970.

### Method / field map (verified against library source + recorded fixtures)

| Metric | Method | Key fields |
|---|---|---|
| Daily summary (steps, calories, RHR, stress avg, body battery) | `get_user_summary(date)` | `totalSteps`, `totalKilocalories`, `activeKilocalories`, `restingHeartRate`, `averageStressLevel`, `bodyBatteryMostRecentValue` |
| Sleep | `get_sleep_data(date)` | `dailySleepDTO.deepSleepSeconds`, `.lightSleepSeconds`, `.remSleepSeconds`, `.awakeSleepSeconds`; `sleepScores.overall.value` |
| HRV | `get_hrv_data(date)` | `hrvSummary.lastNightAvg`, `.weeklyAvg`, `.status`, `.baseline` (returns `None` on no-data days) |
| Resting HR | `get_heart_rates(date)` / `get_rhr_day(date)` | `restingHeartRate`, `lastSevenDaysAvgRestingHeartRate` |
| Body Battery | `get_body_battery(start,end)` (list) + `get_body_battery_events(date)` | `charged`, `drained`, `bodyBatteryValuesArray` |
| Training Readiness | `get_training_readiness(date)` (list) | `score`, `level` |
| Stress | `get_stress_data(date)` | `avgStressLevel`, `maxStressLevel` |
| Activities (30d) | `get_activities_by_date(start,end)` | `activityType.typeKey`, `duration`, `averageHR`, `maxHR`, `activityTrainingLoad`, `aerobicTrainingEffect`, `anaerobicTrainingEffect` |
| VO2 max (running) | `get_max_metrics(date)` | `generic.vo2MaxValue` |

### "No data" handling (critical)

`garminconnect` is inconsistent about missing data: some methods return `None`,
some return `[]`, and some return a dict with `null` fields. The sync layer MUST
null-check every return and every field, store missing values as SQL `NULL`, and
log the metric as "unavailable" in the sync log — never crash, never fabricate.

### Auth & credentials

- Credentials only via `GARMIN_EMAIL` / `GARMIN_PASSWORD` in a gitignored `.env`.
  Never hardcoded. Never printed to logs/console, including in error handling.
- Persisted garth token store at `data/.garth/` so email/password are used only on
  first login; later runs resume tokens.
- Catch `GarminConnectAuthenticationError`, `GarminConnectConnectionError`, and
  `GarminConnectTooManyRequestsError` (HTTP 429). On failure: keep last good cached
  data, surface "last synced X ago" + manual retry. Constructor retry/backoff stays
  enabled (`retry_attempts=3`).
- Pull "yesterday" for complete daily metrics (today's data is partial).

## Architecture

```
C:\Users\rodri\Documents\garmin-dashboard\
├── .env                    # GARMIN_EMAIL, GARMIN_PASSWORD (gitignored)
├── .env.example
├── .gitignore
├── README.md
├── package.json            # Electron + scripts
├── electron/
│   └── main.js             # spawns Python backend, loads frontend, kills child on quit
├── backend/
│   ├── requirements.txt    # garminconnect, Flask, python-dotenv
│   ├── sync.py             # scheduled pull → normalize → SQLite (every 30 min)
│   ├── garmin_client.py    # auth + wrapped metric pulls w/ "unavailable" logging
│   ├── db.py               # SQLite schema + read/write helpers
│   ├── recovery.py         # custom recovery score (documented formula)
│   └── api.py              # local Flask API
├── frontend/               # React + Tailwind SPA
└── data/
    └── dashboard.db        # SQLite (gitignored)
```

- **Backend:** one Python process that runs the 30-min sync loop AND serves the
  local Flask API. Single child process for Electron to manage.
- **Frontend:** React + Tailwind SPA. Reads cached SQLite data via the API only —
  never calls Garmin directly.
- **Desktop shell:** Electron spawns the Python backend on start, terminates it on
  quit.
- **API framework: Flask** (synchronous, matches the synchronous `garminconnect`
  library; chosen over FastAPI for simplicity).

### API endpoints

- `GET /api/today` — latest day's metrics + recovery/sleep/strain scores.
- `GET /api/trends?days=30` — daily HRV / RHR / scores series.
- `GET /api/sync-status` — last sync timestamp, status, per-metric availability.
- `POST /api/sync` — trigger an immediate manual sync (retry button).

## Data flow

1. Electron spawns the Python backend.
2. Backend loads `.env`, logs into Garmin via persisted token store.
3. Sync runs immediately, then every 30 min: pull yesterday's daily metrics +
   last-30-days activities → normalize → upsert SQLite → write `sync_log` row.
4. On auth failure / 429: log, keep last good cache, surface "last synced X ago" +
   retry. Never crash.
5. Manual retry → `POST /api/sync`.

## SQLite schema

- `daily_metrics(date PK, hrv_last_night, hrv_status, rhr, sleep_score,
  deep_sleep_s, light_sleep_s, rem_sleep_s, awake_sleep_s, steps, calories,
  body_battery, training_readiness_score, stress_avg, vo2max, recovery_score,
  strain_score)` — recovery_score and strain_score computed at write time.
- `activities(activity_id PK, date, type, duration_s, avg_hr, max_hr,
  training_load, aerobic_te, anaerobic_te)`
- `sync_log(id PK, timestamp, status, message, metric_availability JSON)`

Missing values stored as `NULL`. Frontend renders `NULL` as a "no data" state,
never a placeholder number.

## Recovery score (custom — NOT a Garmin or Whoop metric)

The actual Whoop formula is proprietary. Whoop *documents*: HRV is the dominant
driver, RHR secondary, compared against a 30-day personal baseline, with color
bands green ≥67 / yellow 34–66 / red ≤33. This approximation reproduces that
documented behavior.

Documented in a comment block above the function:

```
hrv_std = max(hrv_std_30d, 0.05 * hrv_mean_30d)   # std floor: 5% of mean
rhr_std = max(rhr_std_30d, 2.0)                    # std floor: ~2 bpm
z_hrv     = clamp((hrv_today - hrv_mean_30d) / hrv_std, -3, 3)
z_rhr_inv = clamp(-(rhr_today - rhr_mean_30d) / rhr_std, -3, 3)
z         = 0.7 * z_hrv + 0.3 * z_rhr_inv          # HRV-dominant
score     = round( 100 / (1 + exp(-(1.0*z + 0.3))) )   # sigmoid; +0.3 centers neutral day ~58
```

- Color bands: green ≥67, yellow 34–66, red ≤33.
- Requires ≥14 days of baseline data; before that the UI shows "building baseline,"
  not a score.
- UI label: "Estimated Recovery (custom metric — not a Garmin or Whoop score)."

**Strain/load score** is likewise a custom metric derived from activity training
load + duration/intensity, labeled as custom in the UI.

## UI (dark theme, single dashboard view)

- Top: three circular gauges — Recovery (color-coded), Sleep, Strain/load.
- Below: 14-day HRV line, 14-day RHR line, last-night sleep-stage breakdown bar,
  recent activities list (type, duration, avg HR).
- Header: "Last synced X ago" + manual retry button.
- Any metric without data shows a "no data" state.

## Error handling summary

- Auth failure / 429 / connection error: caught, logged (no credential values),
  last good cache retained, "last synced X ago" + retry shown. App never crashes.
- Missing metric: stored NULL, logged "unavailable", rendered as "no data".

## Testing

- `recovery.py`: unit tests for the formula — neutral day ≈ 58, high HRV → green,
  low HRV/high RHR → red, std-floor guards, <14-day "building baseline" path.
- `garmin_client.py`: tests for the null/`[]`/null-field handling with mocked
  library responses (no live Garmin calls in tests).
- `db.py`: upsert + NULL round-trip.

## Implementation checkpoints (STOP at each)

1. After scaffolding → show project structure, stop.
2. After auth integration → one real login + full data pull, show raw returned
   fields (including any logged "unavailable"), stop for confirmation before UI.
3. After sync + schema working → show a sample of stored data, stop before frontend.
4. No proceeding past any checkpoint without explicit go-ahead.

## Deliverable

A working Electron app launched locally, showing real Garmin data in the dashboard,
with a README covering `.env` setup, `npm start`, and how the 30-min sync interval
works.
