# v3.2.0 — "Today" tab, light/dark theme, branding & cross-platform distribution

Date: 2026-06-29
Status: Approved (design)

## Goal

Expand the Garmin Recovery Dashboard with a time-aware **Today** tab, make Training
Readiness/Status discoverable, add a light theme, give the app a real icon, let
users browse past days, and — most importantly — ship a **Mac build** alongside
Windows so it can be sent to friends on either OS. All existing constraints hold:
local-first, no fabricated data (missing → "No data"/"Building baseline"), never
crash on Garmin auth/rate-limit failures, credentials never logged, tokens stored
as restricted-permission files.

## Agreed decisions

- New tab is named **"Today"** (time-aware single view), placed second (after Overview).
- Mac distribution via **GitHub Actions cloud build, unsigned** (no Apple notarization).
  Mac friends do a one-time right-click → Open to clear Gatekeeper.
- All seven items ship in v3.2.0, in this **work order**:
  1. GitHub repo + CI build (Windows `.exe` + Mac `.dmg`) — *distribution first*
  2. Light/dark theme
  3. Logo / icon & branding
  4. (interleaved) Today tab, Readiness on Overview, update notifier, browse past days

## Work items

### 1. GitHub + cross-platform installer (FIRST)
- Create a GitHub repo (private recommended) and push the existing `garmin-dashboard`
  history. Gives backup + version history + a place for Releases.
- `.github/workflows/build.yml`: matrix `windows-latest` + `macos-latest`.
  Per OS: setup Python 3.11 → venv → `pip install -r requirements.txt` → `npm ci`
  → build frontend → freeze backend (PyInstaller, native per-OS) → `electron-builder
  --win`/`--mac`. On a `v*` tag, attach `GarminRecoveryDashboard-Setup-X.exe` and
  `...-X.dmg` to a GitHub Release.
- Replace the Windows-only `build:backend` npm script with `scripts/freeze.js`
  (node) that selects `.venv/Scripts` vs `.venv/bin`, so `npm run dist` works on
  both OSes. `electron/main.js` already resolves `garmin-backend.exe` vs
  `garmin-backend`, so the Mac spawn is covered.
- package.json `build`: add a `mac` target (`dmg`), `hardenedRuntime` off (unsigned),
  shared `extraResources` mapping `pybuild/dist/garmin-backend` → `backend`.
- Verification: Windows artifact built/validated locally; Mac `.dmg` validated in CI
  (cannot build macOS on the Windows dev machine).

### 2. Light/dark theme (heaviest item)
- Add CSS-variable semantic tokens for `[data-theme="dark"]` / `[data-theme="light"]`
  in `index.css`: `--bg, --surface, --surface-2, --text, --muted, --border`.
- Wire them into `tailwind.config.js` as named colors backed by the vars
  (`bg-surface`, `text-base`, `text-muted`, `border-subtle`, …) using the
  `rgb(var(--x) / <alpha-value>)` pattern.
- Sweep UI primitives + app shell (Card, StatTile, SectionTitle, NoData, nav,
  header, body background, ~15 files) from literal `neutral-*` classes to tokens.
  Accent colors (green/purple/orange/blue) are theme-independent and unchanged.
- Toggle in the header; persisted as `theme` ("dark"|"light", default "dark") in
  settings.json (extend `backend/settings.py` validation). Apply by setting
  `data-theme` on `<html>` at boot from the loaded setting.

### 3. Logo / icon & branding
- Design a recovery pulse/ring icon; render a 1024×1024 `build/icon.png` (Pillow
  script or equivalent). electron-builder generates Windows `.ico` + Mac `.icns`.
- Replaces the generic Electron icon on both platforms and in the installer.

### 4. Today tab (time-aware)
- `frontend/src/tabs/Today.jsx`. Picks view from the clock: `<12:00` → Morning
  Report, else Afternoon Recap; segmented toggle to switch manually.
- **Morning Report:** Recovery score, Sleep score + total + stages strip, HRV last
  night + status, Body Battery at wake, Training Readiness + top factor, RHR, plain
  summary line.
- **Afternoon Recap:** Body Battery now + drained-since-morning, steps vs goal,
  stress (avg + current), intensity minutes today/weekly, today's workouts + load
  added, active calories, plain summary line.
- No new Garmin calls (reuses `/api/today` + `/api/intraday`). Body Battery at wake
  derived from the intraday body-battery series; "now" from `bodyBatteryMostRecentValue`.
- Summary sentences = new **pure functions in `insights.py`** (`morning_summary`,
  `afternoon_summary`), unit-tested, empty on thin data (no fabrication). Surfaced
  via the `/api/insights` payload.
- Cards capability-gated via `visible(caps, cat)`.
- **Dropped:** weather and workout-plan (not reliably in garminconnect 0.3.2; would
  require fabrication or fragile endpoints).

### 5. Readiness on the Overview + discoverability
- Add a Training Readiness tile to the Overview (score + label); click opens the
  detail panel / routes to the Strain & Training tab.

### 6. Update notifier
- On launch, check the GitHub Releases API for a newer tag than the bundled version;
  show a dismissible "vX.Y.Z available — Download" banner linking to the release.
- One new external call — disclosed in README next to the map-tiles note; gated by a
  `check_updates` setting (default on). App version injected at build via Vite define.

### 7. Browse past days
- Header `‹ prev · date · next ›` + "Today" button.
- New `GET /api/day/<date>` (same shape as `/api/today` for that date) and
  `GET /api/days` (dates with data). Day-views (Overview, Today, Sleep, Strain &
  Training) re-render from the selected day's metrics; intraday curves follow via
  `m.date`. Range views (Trends, Activities) unchanged.

## Out of scope (YAGNI)
Apple notarization ($99/yr), full auto-install updater (can't work on unsigned Mac),
external weather API (breaks local-first), new Garmin data scopes.

## Testing
- New backend logic (`morning_summary`, `afternoon_summary`, `/api/day`,
  `/api/days`, settings `theme`/`check_updates`) gets unit tests; existing 97 pass.
- Frontend verified against the real app DB and a local Windows `npm run dist`;
  Mac build validated in CI.

## Risks
- Light theme is a broad component sweep; mitigated by routing everything through a
  small set of semantic tokens so the toggle itself is trivial.
- Mac `.dmg` can't be built on the Windows dev box — first validation is in CI.
- Private-repo macOS CI minutes are limited (~a dozen builds/month on the free tier);
  fine for tagged releases.
