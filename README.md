# Garmin Recovery Dashboard

A local, Whoop-style recovery dashboard that pulls your Garmin Connect data
(built and tested for a Garmin Forerunner 970) and shows Recovery, Sleep, and
Strain scores, HRV/RHR trends, sleep & training detail, and an interactive
run-route map, across five tabs (Overview · Sleep · Strain & Training ·
Activities · Trends).

**Your health data stays on your machine.** The only network calls are to
Garmin Connect — with two deliberate exceptions:
- The **Activities route map** fetches dark basemap tiles from CartoDB's public
  tile servers. No health or account data is sent (only standard map-tile
  coordinates), but those requests do reveal the geographic area of your runs to
  the tile host. To stay fully local, remove the `<TileLayer>` in
  `frontend/src/components/RouteMap.jsx` (the route still draws on a plain background).
- The **update notifier** makes one anonymous request to the GitHub Releases API
  on launch to check for a newer version. No account or health data is sent. Turn
  it off with the **Check for updates** setting (`check_updates`).

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

## Sharing with a friend (one-click installers, Windows + Mac)

The app ships as a standalone installer that bundles everything (Node/Electron
**and** a frozen Python backend), so the recipient needs **no Python, no Node, no
terminal**. They sign in with **their own** Garmin account on a login screen, and
their credentials and data stay entirely on their machine. The app
**auto-detects what their watch supports** and hides tabs/cards their device
doesn't report — so one build works on a Forerunner 970, a 165, a fēnix 7, etc.

### Where the installers come from (GitHub Actions)

Every push builds both installers in the cloud, so a **Mac** build is produced
without needing a Mac. On a version tag (`vX.Y.Z`) they're attached to a GitHub
**[Release](https://github.com/a01786744-coder/garmin-recovery-dashboard/releases)**
— that page is the link you send friends:

- **Windows:** `GarminRecoveryDashboard-Setup-<version>.exe`
- **macOS (Apple Silicon):** `GarminRecoveryDashboard-<version>-arm64.dmg`

To cut a release: `git tag vX.Y.Z && git push origin vX.Y.Z` (the workflow does
the rest). To build locally instead: `npm run dist:win` or `npm run dist:mac`
(the latter only works on a Mac).

### First-open steps for your friend (unsigned apps)

Both builds are **unsigned**, so each OS shows a one-time warning the first time:

- **Windows:** double-click the `.exe` → "Windows protected your PC" → **More
  info** → **Run anyway** → installs per-user (no admin) with a desktop shortcut.
- **macOS:** open the `.dmg`, drag the app to Applications, then **right-click
  (or Control-click) the app → Open → Open** (a plain double-click is blocked by
  Gatekeeper the first time; right-click → Open clears it permanently). If macOS
  still says it's "damaged," run once in Terminal:
  `xattr -cr "/Applications/Garmin Recovery Dashboard.app"`.

> The macOS build targets **Apple Silicon (M1/M2/M3+)**. An Intel-Mac build can be
> added as a second CI target if a friend needs it.
>
> Building locally requires the dev toolchain below installed once on the *build*
> machine (Python, Node, and `pyinstaller` in the venv). The *recipient* needs
> none of it.

## Prerequisites (to develop or build)

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

**Easiest:** double-click **`Start Dashboard.bat`** in this folder (or the
"Garmin Recovery Dashboard" desktop shortcut). It builds the frontend on first
launch, then opens the app — no terminal needed. (One-time setup with
`npm install` must be done first; see Setup above.)

**From a terminal:**

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
