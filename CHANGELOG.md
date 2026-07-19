# Changelog

All notable changes to the Garmin Recovery Dashboard. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/). Dates are YYYY-MM-DD.

## [4.3.2] — 2026-07-18

### Changed
- **Pace-by-split chart now labels time as min:sec instead of raw seconds** — the
  Y-axis and tooltip show `6:48` rather than `408`, matching how pace reads
  everywhere else in the app.

## [4.3.1] — 2026-07-17

### Fixed
- **Accent color now recolors the whole app**, not just the Settings panel — the
  active tab, primary buttons, focus rings, and toggles follow your chosen color.
  Semantic green/amber/red (good/caution/bad) stay meaningful.

## [4.3.0] — 2026-07-17

**Settings redesign** — a proper tabbed Settings dialog with a left-rail of
sections and a raft of new options.

### Added
- **Tabbed Settings**: General · Dashboard & Tabs · Recovery & Metrics ·
  Sync & Data · AI Coach · Phone & Sharing · About (left rail on desktop, chip
  strip on mobile).
- **General**: accent-color picker (recolors buttons, active tab, and the
  recovery ring), three extra themes (Midnight, Slate, Contrast) on top of
  Dark/Light, density (comfortable/compact), default launch tab, week-start
  Mon/Sun, weather units °C/°F, and 12/24-hour clock.
- **Recovery & Metrics**: HRV-vs-Resting-HR **weighting slider** (default 70/30 —
  changing it re-scores your history), custom recovery **color-band cutoffs**
  (green/amber), sleep goal, and max-HR for zone accuracy.
- **Sync & Data**: sync-on-launch toggle, pause-syncing, and **backup & restore**
  (your settings, custom tabs, and journal in one file — never your API key).
- **AI Coach**: in-app model picker (Sonnet 5 / Opus 4.8 / Haiku 4.5), coaching
  **tone** (balanced / concise / detailed / tough-love / encouraging),
  auto-generate the morning brief, workout defaults (warmup length, pace-vs-HR
  target preference), and a monthly-spend reminder.

### Technical
- `recovery.py` takes a tunable `hrv_weight` and custom band cutoffs, threaded
  from settings through sync/rescore and the API. Appearance (theme + accent +
  bands) applies from a single `applyAppearance()`; accent is a CSS variable
  (`--accent`) plus a Tailwind `accent` color. 216 backend tests.

## [4.2.1] — 2026-07-17

### Fixed
- **The Today tab no longer jumps to the end of the tab bar** after customizing
  tabs. The backend's list of built-in tab keys predated the Today tab, so
  saved tab orders silently dropped it (and Today could never be hidden).

## [4.2.0] — 2026-07-16

**Dashboard customization** — rearrange your tabs and build your own.

### Added
- **Jiggle edit mode**: tap **✎ Edit** (or long-press the tab bar) and the tabs
  wobble Apple-home-screen style — drag to reorder, ✕ to hide, and ＋ to create
  a new custom tab (name + icon). Tap **Done** when finished.
- **Custom tabs**: create several of your own named tabs. Each is a resizable
  **snap-to grid** — drag widgets to move, drag a corner to resize, ✕ to remove.
  Reflows to a single column on a phone.
- **Widget inventory**: a Minecraft-creative-inventory-style palette of every
  dashboard card (Recovery, Sleep debt, HRV trend, Weekly volume, Coach brief,
  and ~20 more) with category filters and search. Click a slot to drop it into
  your tab; widgets already placed are dimmed. Every widget shows your real data
  (or an honest "No data").
- Built-in tabs are unchanged; your layout, tab order, and hidden tabs all
  persist locally in settings.

### Technical
- New `DashboardContext` feeds widgets everything they need; `widgets/registry`
  is the single catalog. Grid via `react-grid-layout`, tab reorder via
  `@dnd-kit`. `tab_order` + `custom_tabs` added to settings (validated, capped,
  coordinate-clamped). 206 backend tests.

## [4.1.2] — 2026-07-16

### Fixed
- **Coach failed with a ModuleNotFoundError on the packaged app.** A CI build
  silently dropped the bundled Claude SDK and its native dependencies
  (pydantic/pydantic_core/jiter), so the coach couldn't run even with a valid
  key. The freeze step now collects those packages explicitly and **verifies
  the bundle contains them, failing the build if any are missing** — a
  coach-less binary can no longer be released.

## [4.1.1] — 2026-07-16

### Fixed
- **Settings file is now read BOM-tolerantly.** A settings.json that picked up
  a UTF-8 byte-order mark (e.g. from an external editor or PowerShell) could
  fail to parse and silently fall back to defaults — which, on the next save,
  overwrote real values (API key, PIN, phone access). Loading now strips a
  leading BOM, so a hand-edited or re-encoded file can never wipe settings.

## [4.1.0] — 2026-07-16

### Changed
- **Coach now runs on Claude Sonnet 5** by default (~2.5× cheaper than Opus,
  near-equal coaching quality). Existing installs are switched automatically;
  the model remains configurable via `coach_model` in settings.
- **Much better coach responses on screen.** Replies now render with
  structure — short paragraphs, bullet lists, bold key numbers — instead of a
  wall of plain text, and every brief/chat answer opens with **highlight
  chips**: the key metrics behind the advice (e.g. `ACWR 1.4` amber,
  `Recovery 88` green, `Acute load 500` red).

### Fixed
- Escape artifacts (`\n`, `—`) occasionally leaking into coach replies —
  responses are now sanitized before display and storage.

## [4.0.0] — 2026-07-15

**AI Coach** — a personal running coach powered by Claude (Anthropic API),
with real structured workouts pushed to your Garmin watch.

### Added
- **Coach tab**: a daily morning brief written from your actual data (recovery,
  HRV, sleep debt, running tolerance, journal), plus a chat where you can ask
  anything — "should I run today?", "design me an interval session", "why was
  my recovery low this week?".
- **Workouts on your watch**: when the coach proposes a run it appears as a
  structured workout card — warmup/intervals/recovery/cooldown with explicit
  pace ranges (min/km) and heart-rate bands. After you review and confirm,
  it's uploaded to Garmin Connect and scheduled on your calendar; the watch
  guides you through it with pace/HR alerts like any coach-built workout.
  Pushed workouts are listed in the app and can be removed (unscheduled +
  deleted from Garmin) with one click.
- **Settings → AI Coach**: opt-in toggle + Anthropic API key (stored only in
  the local settings file, like the access PIN; never logged). Model:
  Claude Opus 4.8.

### Privacy
- Off by default. When enabled, the only data sent to Anthropic is the coach
  context: recent daily metrics, activities, journal tags, and performance
  numbers — never Garmin credentials, tokens, or your email. Everything else
  in the app remains fully local.
- Workout upload is the app's first and only write to your Garmin account,
  and it happens exclusively behind the explicit "Send to watch → Confirm"
  flow.

### Technical
- `backend/coach.py` (context builder, cached daily brief, chat with strict
  JSON-schema responses), `backend/workouts.py` (design → Garmin structured
  workout: sec/km → m/s speed zones, custom bpm ranges, repeat groups),
  `push_running_workout`/`remove_workout` on the Garmin client, three new DB
  tables (briefs, chat, pushed workouts). The daily brief is cached per date —
  one Claude call a day. 196 backend tests.

## [3.9.0] — 2026-07-15

Full Forerunner 970 data integration: everything the watch records is now
stored and shown. Field names were confirmed against real account data.

### Added
- **Running dynamics & power** on every run detail — cadence, stride length,
  ground contact time, vertical oscillation, vertical ratio, average/normalized/
  max running power, and elevation gain.
- **Weather conditions** row on activity details (condition, temp, feels-like,
  humidity, wind) — this was already cached but never shown.
- **Recovery time** (hours until fully recovered) on the Today tab.
- **Blood oxygen (SpO2)** — average, sleep average, and daily low — on the Today
  and Sleep tabs.
- **Skin temperature** deviation from baseline on the Today and Sleep tabs.
- **Naps** surfaced on the Sleep tab when recorded.
- **Fitness age** restored with a working data source (`get_fitnessage_data`);
  the old source was empty on this watch, which is why it showed blank.
- **Hill score**, **body weight**, **altitude acclimation**, and **lactate
  threshold** (threshold HR + running FTP) tiles on Trends.
- **Running tolerance** card on Trends — this week's impact load vs your
  tolerance ceiling.
- **HRV status** badge (Balanced / Unbalanced / …) on the HRV trend card.
- **All-day heart-rate curve** in the Resting HR detail panel.

### Technical
- New daily columns (recovery time, naps, skin temp, SpO2, hydration) and perf
  columns (running tolerance, hill score, lactate threshold, body weight);
  activity detail gains a running-dynamics blob. All migrated in place.
- Recovery time, naps, and skin temp are parsed from payloads already fetched
  (zero extra API calls); naps + skin temp also backfill history
  (`BASELINE_FETCH_VERSION=6`). SpO2, hydration, running tolerance, hill score,
  lactate threshold, fitness age, and body weight add one call each, today only.
- `perf_metrics` upserts now COALESCE so a failed sub-fetch never wipes a stored
  value. 181 backend tests.

## [3.8.0] — 2026-07-12

### Added
- **Per-sport activity views.** The activity detail now adapts to the sport:
  outdoor GPS activities keep the map + splits; **treadmill/indoor cardio**
  drops the dead map and leads with splits and HR; **gym sessions** show the
  recorded **exercises with sets, reps and weight** (fetched on demand and
  cached); anything else (team sports, no GPS) gets an effort-focused view
  (max HR, aerobic/anaerobic training effect, zones).
- **Sport filter chips** on the Activities list (All · Run · Ride · Gym ·
  Other, color-coded) and the list now covers your full recent history via a
  new `/api/activities` endpoint — not just the last 10.
- **Weekly volume chart**: stacked hours per week by sport for the last 8
  weeks.

### Notes
- 172 backend tests.

## [3.7.0] — 2026-07-11

### Added
- **Sleep debt tracker** (Sleep tab): cumulative need-minus-slept over the
  last 7 and 14 days with per-night deficit/surplus bars. Counts only nights
  Garmin reported — a missing night is never assumed slept or missed.
- **Long-term trends** (Trends tab): Body Battery, waking respiration, VO₂max
  and fitness age as lines over 30d/90d/6m/1y — metrics that previously only
  showed today's number.
- The backfill now also captures **body battery, stress, and sleep need** for
  past days (parsed from data it already downloads — no extra Garmin calls);
  a one-time re-backfill fills the new history.

### Fixed
- **Re-backfills no longer erase data.** A version-bump re-backfill used to
  overwrite each day's full row with its sparser fetch, wiping richer fields
  the daily sync had stored (sleep need, readiness, respiration…). Backfill
  upserts are now merge-mode: missing values never overwrite existing ones.

### Notes
- 168 backend tests.

## [3.6.0] — 2026-07-08

### Added
- **Compare chart** (Trends): Whoop-style overlay — Recovery as bars colored
  by zone (green/yellow/red) with **Sleep** or **Strain** as a line on the
  same 0-100 scale, switchable, with 30d/60d/90d/6m/1y ranges.

## [3.5.1] — 2026-07-05

### Added
- **Chart range selector**: every metric detail panel can switch its evolution
  chart and stats between **30d / 60d / 90d / 6m / 1y**.
- **Date style setting**: chart dates show real month names ("Jul 4") by
  default, switchable to numeric ("07-04") in Settings → Dates. Applies to all
  chart axes/tooltips, the day browser, the stale banner, and the week review.
- **Tray heads-up**: the first time you close the window, a one-time
  notification explains the app keeps running in the tray (and how to quit) —
  closing no longer looks like a refusal to close.

## [3.5.0] — 2026-07-04

### Added
- **Background/tray mode.** Closing the window keeps the app (and your phone
  dashboard) running in the tray / menu bar — Open/Quit from the tray icon. A
  **Start at login (minimized)** setting launches it hidden at boot. Launching
  the app while it's already running focuses the existing window.
- **"Why this score."** The Recovery panel shows today's HRV and resting HR
  against your baseline (with direction chips and the 70/30 weighting); the
  Strain panel splits the day into workout vs daily-life load.
- **Strain history.** The backfill now captures steps/intensity for past days
  (from data it already downloaded — no extra Garmin calls); a one-time
  re-backfill fills the strain trend and heatmap.
- **Journal everywhere.** The journal appears on the Overview for whichever
  day you're viewing — past days editable via the day browser. Tags with a
  discovered effect show a ▲/▼ badge, and correlations now also test each tag
  against next-night sleep.
- **Your week in review** on the Today tab every Monday: last week vs the week
  before, best/toughest day, and how many patterns the journal has found.
- **Reliability:** stale-data banner when nothing has synced for >2 days; a
  "session expired — sign in again" prompt after repeated auth failures
  (instead of failing silently); the day browser now updates as new days
  arrive (was dead on fresh installs until relaunch).

### Changed
- **Strain tuning:** daily-life load (steps + intensity) counts at half on
  workout days, since workouts already include their own steps — run days now
  land ~55-70 instead of 80+.

### Fixed
- "Today" was computed in UTC, so every evening the app thought tomorrow had
  started (false "not synced yet" banner; journal entries written under
  tomorrow's date). Now local time.

### Notes
- 160 backend tests.

## [3.4.2] — 2026-07-03

### Fixed
- **Manual sync wiped recovery scores** when the baseline window was set below
  30 days: the Retry/manual sync used the default 30-day window (needing 14
  baseline days) and its rescore pass overwrote scores computed under the
  user's shorter window. Manual sync now uses the configured window, same as
  the scheduled sync.

## [3.4.1] — 2026-07-02

### Fixed
- **Sleep "Component scores" were always empty:** the fetch read keys Garmin
  doesn't use (`deep`/`rem`/`light`). It now reads the real
  `deepPercentage`/`remPercentage`/`lightPercentage` (value + quality
  qualifier); the card is reworked into **Stage quality** — percent of the
  night per stage with Garmin's Excellent/Good/Fair/Poor rating, plus a
  restlessness rating (which has no numeric value, so none is invented).
- **"Record 16" and friends:** personal-record types 9 (total ascent),
  14 (most steps in a month), 15/16 (best/current step-goal streak) are now
  labeled; unknown types are hidden instead of showing a raw "record N".

## [3.4.0] — 2026-07-02

### Fixed
- **Recovery finally loads.** The score demanded a hardcoded 14 days of HRV/RHR
  history even when the baseline window was set below 14 — making a score
  mathematically impossible at short windows. The minimum now scales with the
  window (7-day window → 4 days, capped at 14). A **rescore pass** recomputes
  recovery for all stored days after every sync and on settings changes, so
  history heals immediately. The gauge shows real progress
  ("Baseline 3/4 days") while building.

### Changed
- **All-day Strain.** Strain now combines workout load with daily-life load
  (intensity minutes at Garmin's mod+2×vig weighting, plus steps) — so a
  no-workout day scores from wear data instead of staying blank. Still never
  fabricated: a day with no data stays empty.

### Added
- **Journal** (Today tab): tag each day — alcohol, late caffeine, late meal,
  high stress, sick, travel, screens in bed, nap — plus a note. Entries
  **prefill from your previous answers** (change only what changed) and save on
  tap. Once ≥4 tagged and ≥4 untagged days accumulate, Insights reports each
  tag's effect on next-day recovery ("On alcohol days, next-day recovery
  averages 12 points lower.").
- **Month heatmap** (Trends tab): a calendar grid colored by Recovery, Sleep,
  or Strain with month navigation — spot patterns at a glance.
- `/api/sync-status` reports the app's `data_dir` (support diagnostic).

### Notes
- 143 backend tests.

## [3.3.0] — 2026-07-01

### Added
- **Phone access (LAN + Tailscale).** The desktop app can now double as a private
  web server your phone opens by URL — on home Wi‑Fi, or from anywhere with
  **Tailscale**. Turn it on in **Settings → Enable phone access** and set a **PIN**;
  your data stays on your PC.
  - Flask serves the built SPA alongside the API from one origin; Electron loads it
    by URL; the frontend uses same‑origin calls.
  - A required **access PIN** gates every non‑loopback API request (your own PC
    needs none); a PIN screen appears on the phone.
  - **PWA**: web manifest + Apple web‑app tags + icons + a secure‑context service
    worker — on iPhone, Safari → **Add to Home Screen** for a full‑screen app.
  - Responsive polish for phone widths.

### Notes
- 121 backend tests. Access stays private: only your own devices reach it, PIN‑gated;
  Tailscale keeps it off the public internet. Your PC must be on to serve the phone.

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

[3.4.2]: #342--2026-07-03
[3.4.1]: #341--2026-07-02
[3.4.0]: #340--2026-07-02
[3.3.0]: #330--2026-07-01
[3.2.0]: #320--2026-06-30
[3.1.3]: #313--2026-06-23
[3.1.2]: #312--2026-06-23
[3.1.1]: #311--2026-06-23
[3.1.0]: #310--2026-06-23
[3.0.0]: #300--2026-06-23
[2.0.0]: #200--2026-06-21
[1.0.0]: #100--2026-06-20
