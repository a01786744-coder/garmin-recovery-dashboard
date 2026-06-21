# Garmin Recovery Dashboard

A fully-local, Whoop-style recovery dashboard that pulls your Garmin Connect
data (built and tested for a Garmin Forerunner 970) and shows Recovery, Sleep,
and Strain scores plus HRV and resting-heart-rate trends. **All data stays on
your machine** — the only network calls are to Garmin Connect itself.

> **Recovery and Strain are custom estimates, not official Garmin or Whoop
> metrics.** The Recovery formula (HRV- and RHR-based, compared to your personal
> 30-day baseline) is documented in the comment block above `recovery_score` in
> [`backend/recovery.py`](backend/recovery.py). The UI labels both clearly.

## How it works

- A small **Python backend** logs into Garmin Connect (via the unofficial
  `garminconnect` library), syncs your data on a schedule into a local SQLite
  database (`data/dashboard.db`), and serves it over a local Flask API on
  `127.0.0.1:5057`.
- A **React + Tailwind** single-page dashboard reads that cached data — it never
  talks to Garmin directly.
- An **Electron** shell wraps the dashboard and manages the Python backend as a
  child process (started on launch, terminated on quit).

The dashboard is **"today"-centric, like Whoop**: Garmin files last night's
sleep and HRV under the wake date, so today's card shows last night's Sleep and
your morning Recovery, while Strain and Body Battery accumulate through the day.

## Prerequisites

- **Python 3.11** (the project pins `garminconnect==0.3.2`, the newest release
  that supports Python 3.11; 0.3.3+ require Python 3.12).
- **Node 24+**
- A Garmin Connect account with data synced from your watch.

## Setup

1. **Credentials.** Copy `.env.example` to `.env` and fill in your Garmin login:
   ```
   GARMIN_EMAIL=you@example.com
   GARMIN_PASSWORD=your-password
   ```
   `.env` is gitignored and never committed. Credentials are used only to log in
   to Garmin Connect and are **never logged or printed**, including on errors.

2. **Python backend.** Create the virtual environment and install dependencies:
   ```
   python -m venv .venv
   .venv\Scripts\python -m pip install -r backend\requirements.txt
   ```

3. **Node dependencies** (root for Electron, plus the frontend):
   ```
   npm install
   npm --prefix frontend install
   ```

## Run

```
npm start
```

This builds the frontend, launches the Python backend (Flask API + sync
scheduler), and opens the Electron window. Closing the window terminates the
backend.

### First login & MFA

The first sync logs in with your email/password and caches an authentication
token in `data/.garth/`. After that, syncs resume from the cached token without
re-entering credentials. If your account uses multi-factor authentication, do
the **first** login from a terminal so you can enter the code once:

```
.venv\Scripts\python -m backend.api
```

Enter the MFA code when prompted; the token is then cached and `npm start` works
normally from then on.

## How sync works

- On launch and then **every 30 minutes**, the backend pulls **today's** metrics
  (last night's sleep/HRV + today's live wellness) and your recent activities,
  computes the scores, and stores everything in `data/dashboard.db`.
- **Backfill:** on a fresh database the 14-day trends and the 30-day Recovery
  baseline would be empty, so the backend backfills missing days within the
  baseline window (HRV + RHR per day). Backfill is **paced** and
  **rate-limit-tolerant**: if Garmin returns HTTP 429, the sync keeps what it
  got, marks itself "partial", and resumes on the next run.
- The header shows **"Last synced X ago"** with a **Retry** button for an
  immediate manual sync. If Garmin auth fails or rate-limits, the app keeps
  showing the last cached data and surfaces the error — **it never crashes.**

## What you'll see

- **Recovery** needs **≥14 days of overnight HRV** to compute. Until then it
  shows **"Building baseline."** Nights you don't wear the watch simply have no
  HRV, so those days show no Recovery — the app **never fabricates a number**;
  missing metrics render as **"No data."**
- **Sleep** and **Strain** populate as soon as there's a tracked night / a logged
  workout. HRV and RHR **trend lines** fill in as you accumulate days of wear.

So a brand-new install with limited watch-wear history will show rich data for
*today* but sparse trends and "Building baseline" for Recovery — that is correct
behavior, and it fills in automatically as more days of data accumulate.

## Tests

```
npm run test:backend
```

(Runs the backend `pytest` suite. The frontend is verified via `npm --prefix
frontend run build`.)

## Project layout

```
backend/    Python: garmin_client (auth + fetch), db (SQLite), recovery
            (custom scores), sync (orchestration + backfill), api (Flask + scheduler)
frontend/   React + Tailwind SPA (Vite)
electron/   Electron main process (spawns backend, loads frontend)
data/        dashboard.db + .garth token store (gitignored)
docs/        design spec + implementation plan
```
