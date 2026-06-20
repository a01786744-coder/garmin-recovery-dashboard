# Garmin Recovery Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully-local Electron desktop app that pulls Garmin Connect data (Forerunner 970) via the `garminconnect` Python library and shows a Whoop-style recovery dashboard.

**Architecture:** A single Python backend process runs a 30-minute sync loop (Garmin → normalized SQLite) and serves a local Flask API. A React + Tailwind SPA reads cached data from that API. Electron wraps the SPA and manages the Python child process.

**Tech Stack:** Python 3.11 (`garminconnect` 0.3.2 — newest release supporting Python 3.11; 0.3.3+ requires 3.12; Flask, python-dotenv, pytest), SQLite (stdlib `sqlite3`), React + Tailwind (Vite), Electron, Node 24.

## Global Constraints

- Python: 3.11.x. Node: 24.x. Both already installed.
- Dependencies are limited to: `garminconnect`, `Flask`, `python-dotenv`, `pytest` (Python); `electron`, `react`, `react-dom`, `vite`, `@vitejs/plugin-react`, `tailwindcss`, a charting lib (`recharts`) (Node). **Stop and ask before adding ANY dependency not in this list.**
- Credentials ONLY via `GARMIN_EMAIL` / `GARMIN_PASSWORD` in a gitignored `.env`. Never hardcoded. Never printed to logs/console/errors.
- MUST run fully locally — no data to any third party except Garmin Connect.
- MUST NOT fabricate data: missing metric → SQL `NULL` → "no data" UI state. Never a placeholder number.
- MUST NOT crash on auth failure / 429 / connection error: log (no credentials), keep last good cache, show "last synced X ago" + manual retry.
- Recovery and Strain are CUSTOM metrics — label them in the UI as "not a Garmin or Whoop score".
- Only build what is in this plan. No user accounts, cloud sync, social, notifications.
- Stop and ask before any destructive command (deleting files, dropping the DB, force-push).
- Pull "yesterday" for daily metrics (today's data is partial).
- Work only within `C:\Users\rodri\Documents\garmin-dashboard`.

## File Structure

```
garmin-dashboard/
├── .env / .env.example / .gitignore / README.md
├── package.json                 # Electron + frontend scripts
├── electron/main.js             # spawn Python backend, load SPA, kill child on quit
├── backend/
│   ├── requirements.txt
│   ├── config.py                # load .env, paths, constants
│   ├── db.py                    # SQLite schema + upsert/read helpers
│   ├── recovery.py              # custom recovery + strain formulas
│   ├── garmin_client.py         # auth + metric pulls w/ null→"unavailable"
│   ├── sync.py                  # orchestrate pull → normalize → store → log
│   ├── api.py                   # Flask app + endpoints + 30-min scheduler
│   └── tests/
│       ├── test_recovery.py
│       ├── test_db.py
│       ├── test_garmin_client.py
│       └── test_sync.py
├── frontend/
│   ├── index.html / vite.config.js / tailwind.config.js / postcss.config.js
│   ├── package.json
│   └── src/{main.jsx, App.jsx, api.js, components/*}
└── data/                        # dashboard.db, .garth/ (gitignored)
```

---

## CHECKPOINT 1 — after Task 1, show project structure and STOP.

### Task 1: Project scaffolding

**Files:**
- Create: `.gitignore`, `.env.example`, `README.md` (stub), `backend/requirements.txt`, `backend/config.py`, `backend/__init__.py`, `backend/tests/__init__.py`, `data/.gitkeep`

**Interfaces:**
- Produces: `config.PROJECT_ROOT`, `config.DATA_DIR`, `config.DB_PATH`, `config.TOKENSTORE_DIR`, `config.GARMIN_EMAIL`, `config.GARMIN_PASSWORD`, `config.SYNC_INTERVAL_SECONDS = 1800`, `config.BASELINE_MIN_DAYS = 14`, `config.BASELINE_WINDOW_DAYS = 30`.

- [ ] **Step 1: Write `.gitignore`**

```gitignore
# Secrets & data
.env
data/dashboard.db
data/.garth/
# Python
__pycache__/
*.pyc
.pytest_cache/
venv/
.venv/
# Node
node_modules/
frontend/dist/
# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 2: Write `.env.example`**

```dotenv
# Copy to .env and fill in. .env is gitignored and never committed.
GARMIN_EMAIL=you@example.com
GARMIN_PASSWORD=your-password
```

- [ ] **Step 3: Write `backend/requirements.txt`**

```text
garminconnect==0.3.2
Flask==3.0.3
python-dotenv==1.0.1
pytest==8.2.0
```

- [ ] **Step 4: Write `backend/config.py`**

```python
"""Central config: paths, constants, and credentials loaded from .env.

Credential values are read from the environment and never logged.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "dashboard.db"
TOKENSTORE_DIR = DATA_DIR / ".garth"

GARMIN_EMAIL = os.environ.get("GARMIN_EMAIL")
GARMIN_PASSWORD = os.environ.get("GARMIN_PASSWORD")

SYNC_INTERVAL_SECONDS = 1800   # 30 minutes
BASELINE_WINDOW_DAYS = 30
BASELINE_MIN_DAYS = 14

DATA_DIR.mkdir(exist_ok=True)
```

- [ ] **Step 5: Create empty `backend/__init__.py`, `backend/tests/__init__.py`, and `data/.gitkeep`**

- [ ] **Step 6: Write `README.md` stub** (full README completed in Task 12)

```markdown
# Garmin Recovery Dashboard

A local Whoop-style recovery dashboard sourced from Garmin Connect. Setup
instructions are filled in once the app is complete (see Task 12).
```

- [ ] **Step 7: Set up Python venv and install deps**

Run:
```bash
cd "/c/Users/rodri/Documents/garmin-dashboard"
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt
```
Expected: installs without error; `.venv/Scripts/python -c "import garminconnect, flask, dotenv"` exits 0.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore: scaffold project structure and config"
```

- [ ] **Step 9: Show the tree and STOP for Checkpoint 1.**

Run: `git ls-files; echo "---"; find . -path ./.venv -prune -o -path ./.git -prune -o -type d -print`
Present the structure to the user and wait for go-ahead.

---

## CHECKPOINT 2 — after Task 3, run a real login + full data pull, show raw fields (incl. "unavailable"), STOP.

### Task 2: Garmin auth client

**Files:**
- Create: `backend/garmin_client.py`
- Test: `backend/tests/test_garmin_client.py`

**Interfaces:**
- Produces: `class GarminClient` with `__init__(email, password, tokenstore)`, `login() -> None` (raises `GarminAuthError` on bad creds), and a module-level `GarminAuthError`, `GarminRateLimitError`, `GarminConnectionError` (thin wrappers re-raised from the library so callers don't import library internals).

- [ ] **Step 1: Write the failing test (login resumes from tokenstore, never logs creds)**

```python
# backend/tests/test_garmin_client.py
from unittest.mock import MagicMock, patch
import backend.garmin_client as gc

def test_login_calls_library_with_tokenstore():
    with patch.object(gc, "Garmin") as MockGarmin:
        instance = MockGarmin.return_value
        client = gc.GarminClient("e@x.com", "secret", "/tmp/ts")
        client.login()
        MockGarmin.assert_called_once()
        instance.login.assert_called_once_with("/tmp/ts")

def test_login_wraps_auth_error():
    with patch.object(gc, "Garmin") as MockGarmin:
        from garminconnect import GarminConnectAuthenticationError
        MockGarmin.return_value.login.side_effect = GarminConnectAuthenticationError("bad")
        client = gc.GarminClient("e@x.com", "secret", "/tmp/ts")
        try:
            client.login()
            assert False, "should raise"
        except gc.GarminAuthError as e:
            assert "secret" not in str(e)  # never leak credentials
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_garmin_client.py -v`
Expected: FAIL (module/attr not defined).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/garmin_client.py
"""Authenticated wrapper around the garminconnect library.

Never logs or includes credential values in error messages.
"""
import logging
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

log = logging.getLogger("garmin")


class GarminAuthError(Exception):
    pass


class GarminRateLimitError(Exception):
    pass


class GarminConnectionError(Exception):
    pass


class GarminClient:
    def __init__(self, email, password, tokenstore):
        self._email = email
        self._password = password
        self._tokenstore = str(tokenstore)
        self._api = None

    def login(self):
        try:
            self._api = Garmin(self._email, self._password)
            self._api.login(self._tokenstore)
        except GarminConnectAuthenticationError:
            raise GarminAuthError("Garmin authentication failed (check .env credentials)")
        except GarminConnectTooManyRequestsError:
            raise GarminRateLimitError("Garmin rate limit hit (HTTP 429)")
        except GarminConnectConnectionError:
            raise GarminConnectionError("Could not connect to Garmin Connect")

    @property
    def api(self):
        if self._api is None:
            raise RuntimeError("login() must be called first")
        return self._api
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_garmin_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/garmin_client.py backend/tests/test_garmin_client.py
git commit -m "feat: add Garmin auth client with credential-safe error wrapping"
```

### Task 3: Metric pull functions with null→"unavailable" handling

**Files:**
- Modify: `backend/garmin_client.py`
- Test: `backend/tests/test_garmin_client.py`

**Interfaces:**
- Produces a method `fetch_day(date_str) -> tuple[dict, dict]` returning `(metrics, availability)`:
  - `metrics`: normalized dict with keys `hrv_last_night, hrv_status, rhr, sleep_score, deep_sleep_s, light_sleep_s, rem_sleep_s, awake_sleep_s, steps, calories, body_battery, training_readiness_score, stress_avg, vo2max` (value or `None`).
  - `availability`: same keys → `"available"` or `"unavailable"`.
- And `fetch_activities(start_str, end_str) -> list[dict]` with keys `activity_id, date, type, duration_s, avg_hr, max_hr, training_load, aerobic_te, anaerobic_te` (per-field `None` allowed).
- Helpers must never raise on missing data; they catch per-metric exceptions, log, and mark unavailable.

- [ ] **Step 1: Write the failing tests (null library returns become None + "unavailable", never raise)**

```python
def _client_with_api(api):
    c = gc.GarminClient("e", "p", "/tmp")
    c._api = api
    return c

def test_fetch_day_handles_none_and_empty():
    api = MagicMock()
    api.get_user_summary.return_value = {
        "totalSteps": 1119, "totalKilocalories": 2202.0,
        "restingHeartRate": 52, "averageStressLevel": 28,
        "bodyBatteryMostRecentValue": 60,
    }
    api.get_sleep_data.return_value = {
        "dailySleepDTO": {
            "deepSleepSeconds": 3600, "lightSleepSeconds": 7200,
            "remSleepSeconds": 5400, "awakeSleepSeconds": 600,
            "sleepScores": {"overall": {"value": 82}},
        }
    }
    api.get_hrv_data.return_value = None                       # no-data day → None
    api.get_training_readiness.return_value = []               # empty list
    api.get_max_metrics.return_value = None
    metrics, avail = _client_with_api(api).fetch_day("2026-06-19")
    assert metrics["steps"] == 1119
    assert metrics["sleep_score"] == 82
    assert metrics["rhr"] == 52
    assert metrics["hrv_last_night"] is None
    assert avail["hrv_last_night"] == "unavailable"
    assert avail["steps"] == "available"
    assert metrics["training_readiness_score"] is None
    assert avail["training_readiness_score"] == "unavailable"

def test_fetch_day_never_raises_on_exception():
    api = MagicMock()
    api.get_user_summary.side_effect = KeyError("boom")
    api.get_sleep_data.return_value = None
    api.get_hrv_data.return_value = None
    api.get_training_readiness.return_value = []
    api.get_max_metrics.return_value = None
    metrics, avail = _client_with_api(api).fetch_day("2026-06-19")
    assert metrics["steps"] is None
    assert avail["steps"] == "unavailable"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest backend/tests/test_garmin_client.py -v`
Expected: FAIL (`fetch_day` not defined).

- [ ] **Step 3: Implement `fetch_day` and `fetch_activities`** (append to `GarminClient`)

```python
    def _safe(self, fn, default=None):
        """Call a library getter; on any error return default (never raise)."""
        try:
            return fn()
        except Exception as e:  # library raises varied types on missing data
            log.warning("metric fetch failed: %s", type(e).__name__)
            return default

    def fetch_day(self, date_str):
        api = self.api
        summary = self._safe(lambda: api.get_user_summary(date_str), {}) or {}
        sleep = self._safe(lambda: api.get_sleep_data(date_str), {}) or {}
        hrv = self._safe(lambda: api.get_hrv_data(date_str), None)
        tr = self._safe(lambda: api.get_training_readiness(date_str), []) or []
        maxmet = self._safe(lambda: api.get_max_metrics(date_str), None)

        sdto = (sleep or {}).get("dailySleepDTO", {}) or {}
        hrv_sum = (hrv or {}).get("hrvSummary", {}) if hrv else {}
        tr0 = tr[0] if isinstance(tr, list) and tr else {}
        maxgen = {}
        if isinstance(maxmet, list) and maxmet:
            maxgen = (maxmet[0] or {}).get("generic", {}) or {}
        elif isinstance(maxmet, dict):
            maxgen = maxmet.get("generic", {}) or {}

        metrics = {
            "hrv_last_night": hrv_sum.get("lastNightAvg"),
            "hrv_status": hrv_sum.get("status"),
            "rhr": summary.get("restingHeartRate"),
            "sleep_score": (sdto.get("sleepScores", {}) or {}).get("overall", {}).get("value"),
            "deep_sleep_s": sdto.get("deepSleepSeconds"),
            "light_sleep_s": sdto.get("lightSleepSeconds"),
            "rem_sleep_s": sdto.get("remSleepSeconds"),
            "awake_sleep_s": sdto.get("awakeSleepSeconds"),
            "steps": summary.get("totalSteps"),
            "calories": summary.get("totalKilocalories"),
            "body_battery": summary.get("bodyBatteryMostRecentValue"),
            "training_readiness_score": tr0.get("score"),
            "stress_avg": summary.get("averageStressLevel"),
            "vo2max": maxgen.get("vo2MaxValue"),
        }
        availability = {k: ("available" if v is not None else "unavailable")
                        for k, v in metrics.items()}
        return metrics, availability

    def fetch_activities(self, start_str, end_str):
        api = self.api
        raw = self._safe(lambda: api.get_activities_by_date(start_str, end_str), []) or []
        out = []
        for a in raw:
            a = a or {}
            out.append({
                "activity_id": a.get("activityId"),
                "date": (a.get("startTimeLocal") or "")[:10] or None,
                "type": (a.get("activityType", {}) or {}).get("typeKey"),
                "duration_s": a.get("duration"),
                "avg_hr": a.get("averageHR"),
                "max_hr": a.get("maxHR"),
                "training_load": a.get("activityTrainingLoad"),
                "aerobic_te": a.get("aerobicTrainingEffect"),
                "anaerobic_te": a.get("anaerobicTrainingEffect"),
            })
        return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest backend/tests/test_garmin_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/garmin_client.py backend/tests/test_garmin_client.py
git commit -m "feat: add metric/activity fetch with null-safe unavailable handling"
```

- [ ] **Step 6: Write a throwaway checkpoint script and run a REAL pull**

Create `backend/_checkpoint_pull.py` (temporary; deleted after):

```python
"""One-off Checkpoint 2 verification: real login + full data pull.
Prints raw availability. Does NOT print credentials. Delete after use.
"""
import json, datetime as dt
import backend.config as cfg
from backend.garmin_client import GarminClient

yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
month_ago = (dt.date.today() - dt.timedelta(days=30)).isoformat()

c = GarminClient(cfg.GARMIN_EMAIL, cfg.GARMIN_PASSWORD, cfg.TOKENSTORE_DIR)
c.login()
metrics, avail = c.fetch_day(yesterday)
acts = c.fetch_activities(month_ago, yesterday)
print("DATE:", yesterday)
print("METRICS:", json.dumps(metrics, indent=2, default=str))
print("AVAILABILITY:", json.dumps(avail, indent=2))
print("ACTIVITIES (count):", len(acts))
if acts:
    print("SAMPLE ACTIVITY:", json.dumps(acts[0], indent=2, default=str))
```

Run: `.venv/Scripts/python -m backend._checkpoint_pull`
Expected: prints metrics + availability (some fields may be "unavailable") and activity count. **If MFA is required, the library will prompt** — handle interactively. **STOP and show the user the raw output for Checkpoint 2.** Do not delete `_checkpoint_pull.py` until the user confirms; then remove it.

---

## CHECKPOINT 3 — after Task 7, show a sample of stored data, STOP before frontend.

### Task 4: Recovery + strain formulas

**Files:**
- Create: `backend/recovery.py`
- Test: `backend/tests/test_recovery.py`

**Interfaces:**
- Produces: `recovery_score(hrv_today, rhr_today, hrv_hist, rhr_hist) -> int | None` (None when `< BASELINE_MIN_DAYS` history or today's HRV/RHR missing); `recovery_band(score) -> "green"|"yellow"|"red"`; `strain_score(activities_for_day) -> int | None`.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_recovery.py
import backend.recovery as r

def test_neutral_day_near_58():
    hist_hrv = [40] * 30
    hist_rhr = [50] * 30
    # today equals baseline mean → sigmoid(+0.3) ≈ 57-58
    assert 55 <= r.recovery_score(40, 50, hist_hrv, hist_rhr) <= 60

def test_high_hrv_low_rhr_is_green():
    hist_hrv = list(range(30, 60))       # mean ~44, std ~8.6
    hist_rhr = list(range(45, 75))
    score = r.recovery_score(70, 44, hist_hrv, hist_rhr)
    assert score >= 67
    assert r.recovery_band(score) == "green"

def test_low_hrv_high_rhr_is_red():
    hist_hrv = list(range(30, 60))
    hist_rhr = list(range(45, 75))
    score = r.recovery_score(25, 80, hist_hrv, hist_rhr)
    assert score <= 33
    assert r.recovery_band(score) == "red"

def test_insufficient_history_returns_none():
    assert r.recovery_score(40, 50, [40] * 10, [50] * 10) is None

def test_missing_today_returns_none():
    assert r.recovery_score(None, 50, [40] * 30, [50] * 30) is None

def test_strain_none_when_no_activities():
    assert r.strain_score([]) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest backend/tests/test_recovery.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `backend/recovery.py`**

```python
"""Custom recovery & strain scores. NOT Garmin or Whoop metrics.

Recovery formula (approximation of Whoop's documented behavior — HRV-dominant,
RHR secondary, compared to a personal 30-day baseline; the real Whoop formula
is proprietary and not public):

    hrv_std = max(std(hrv_hist), 0.05 * mean(hrv_hist))   # 5%-of-mean floor
    rhr_std = max(std(rhr_hist), 2.0)                      # ~2 bpm floor
    z_hrv     = clamp((hrv_today - mean(hrv_hist)) / hrv_std, -3, 3)
    z_rhr_inv = clamp(-(rhr_today - mean(rhr_hist)) / rhr_std, -3, 3)
    z         = 0.7 * z_hrv + 0.3 * z_rhr_inv             # HRV-dominant
    score     = round(100 / (1 + exp(-(1.0*z + 0.3))))    # +0.3 centers neutral ~58

Color bands match Whoop's published cutoffs: green >=67, yellow 34-66, red <=33.
Requires >= BASELINE_MIN_DAYS of history; otherwise returns None ("building
baseline"). Today's HRV or RHR missing also returns None (never fabricate).
"""
import math
from statistics import mean, pstdev
from backend.config import BASELINE_MIN_DAYS


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def recovery_score(hrv_today, rhr_today, hrv_hist, rhr_hist):
    hrv_hist = [h for h in (hrv_hist or []) if h is not None]
    rhr_hist = [r_ for r_ in (rhr_hist or []) if r_ is not None]
    if hrv_today is None or rhr_today is None:
        return None
    if len(hrv_hist) < BASELINE_MIN_DAYS or len(rhr_hist) < BASELINE_MIN_DAYS:
        return None

    hrv_mean, rhr_mean = mean(hrv_hist), mean(rhr_hist)
    hrv_std = max(pstdev(hrv_hist), 0.05 * hrv_mean) if hrv_mean else max(pstdev(hrv_hist), 1.0)
    rhr_std = max(pstdev(rhr_hist), 2.0)

    z_hrv = _clamp((hrv_today - hrv_mean) / hrv_std, -3, 3)
    z_rhr_inv = _clamp(-(rhr_today - rhr_mean) / rhr_std, -3, 3)
    z = 0.7 * z_hrv + 0.3 * z_rhr_inv
    score = 100 / (1 + math.exp(-(1.0 * z + 0.3)))
    return int(round(min(100, max(0, score))))


def recovery_band(score):
    if score is None:
        return None
    if score >= 67:
        return "green"
    if score >= 34:
        return "yellow"
    return "red"


def strain_score(activities_for_day):
    """Custom 0-100 strain from the day's activity training load.

    Sum each activity's training_load (fallback: duration_minutes * (avg_hr/100)
    when training_load is missing), then map to 0-100 via a saturating curve
    (load of ~300 ≈ 90). Returns None when there are no activities with usable data.
    """
    acts = activities_for_day or []
    total = 0.0
    used = False
    for a in acts:
        load = a.get("training_load")
        if load is None:
            dur = a.get("duration_s")
            hr = a.get("avg_hr")
            if dur and hr:
                load = (dur / 60.0) * (hr / 100.0)
        if load:
            total += load
            used = True
    if not used:
        return None
    score = 100 * (1 - math.exp(-total / 150.0))   # saturating
    return int(round(min(100, max(0, score))))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest backend/tests/test_recovery.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/recovery.py backend/tests/test_recovery.py
git commit -m "feat: add custom recovery and strain formulas with tests"
```

### Task 5: SQLite schema + read/write helpers

**Files:**
- Create: `backend/db.py`
- Test: `backend/tests/test_db.py`

**Interfaces:**
- Produces: `init_db(path)`; `upsert_daily(path, date, metrics, recovery, strain)`; `upsert_activities(path, activities)`; `get_daily(path, date) -> dict | None`; `get_trends(path, days) -> list[dict]` (ascending date); `get_history(path, field, days) -> list[float|None]`; `get_recent_activities(path, limit) -> list[dict]`; `write_sync_log(path, status, message, availability)`; `get_last_sync(path) -> dict | None`.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_db.py
import backend.db as db

def test_upsert_and_get_daily_roundtrip_with_nulls(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    metrics = {"hrv_last_night": 40, "hrv_status": "BALANCED", "rhr": 50,
               "sleep_score": 82, "deep_sleep_s": 3600, "light_sleep_s": 7200,
               "rem_sleep_s": 5400, "awake_sleep_s": 600, "steps": 1119,
               "calories": 2202.0, "body_battery": 60,
               "training_readiness_score": None, "stress_avg": 28, "vo2max": None}
    db.upsert_daily(p, "2026-06-19", metrics, recovery=58, strain=None)
    row = db.get_daily(p, "2026-06-19")
    assert row["rhr"] == 50
    assert row["recovery_score"] == 58
    assert row["vo2max"] is None            # NULL preserved, not fabricated
    assert row["strain_score"] is None

def test_upsert_daily_is_idempotent(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    m = {k: None for k in db.DAILY_FIELDS}
    m["rhr"] = 50
    db.upsert_daily(p, "2026-06-19", m, recovery=None, strain=None)
    m["rhr"] = 55
    db.upsert_daily(p, "2026-06-19", m, recovery=None, strain=None)
    assert db.get_daily(p, "2026-06-19")["rhr"] == 55

def test_get_history_returns_field_series(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    for i, d in enumerate(["2026-06-17", "2026-06-18", "2026-06-19"]):
        m = {k: None for k in db.DAILY_FIELDS}
        m["hrv_last_night"] = 40 + i
        db.upsert_daily(p, d, m, recovery=None, strain=None)
    assert db.get_history(p, "hrv_last_night", 30) == [40, 41, 42]

def test_sync_log_roundtrip(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    db.write_sync_log(p, "ok", "synced", {"hrv_last_night": "available"})
    last = db.get_last_sync(p)
    assert last["status"] == "ok"
    assert last["availability"]["hrv_last_night"] == "available"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest backend/tests/test_db.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `backend/db.py`**

```python
"""SQLite persistence. Missing metrics are stored as NULL (never fabricated)."""
import json
import sqlite3

DAILY_FIELDS = [
    "hrv_last_night", "hrv_status", "rhr", "sleep_score",
    "deep_sleep_s", "light_sleep_s", "rem_sleep_s", "awake_sleep_s",
    "steps", "calories", "body_battery", "training_readiness_score",
    "stress_avg", "vo2max",
]


def _conn(path):
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    return c


def init_db(path):
    with _conn(path) as c:
        cols = ", ".join(f"{f} REAL" if f not in ("hrv_status",) else f"{f} TEXT"
                         for f in DAILY_FIELDS)
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS daily_metrics (
                date TEXT PRIMARY KEY, {cols},
                recovery_score INTEGER, strain_score INTEGER
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                activity_id INTEGER PRIMARY KEY, date TEXT, type TEXT,
                duration_s REAL, avg_hr REAL, max_hr REAL,
                training_load REAL, aerobic_te REAL, anaerobic_te REAL
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT, message TEXT, availability TEXT
            )""")


def upsert_daily(path, date, metrics, recovery, strain):
    cols = ["date"] + DAILY_FIELDS + ["recovery_score", "strain_score"]
    vals = [date] + [metrics.get(f) for f in DAILY_FIELDS] + [recovery, strain]
    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{c2}=excluded.{c2}" for c2 in cols if c2 != "date")
    with _conn(path) as c:
        c.execute(
            f"INSERT INTO daily_metrics ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(date) DO UPDATE SET {updates}", vals)


def upsert_activities(path, activities):
    with _conn(path) as c:
        for a in activities:
            if a.get("activity_id") is None:
                continue
            c.execute("""
                INSERT INTO activities (activity_id, date, type, duration_s,
                    avg_hr, max_hr, training_load, aerobic_te, anaerobic_te)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(activity_id) DO UPDATE SET
                    date=excluded.date, type=excluded.type,
                    duration_s=excluded.duration_s, avg_hr=excluded.avg_hr,
                    max_hr=excluded.max_hr, training_load=excluded.training_load,
                    aerobic_te=excluded.aerobic_te, anaerobic_te=excluded.anaerobic_te
            """, [a.get(k) for k in ("activity_id", "date", "type", "duration_s",
                  "avg_hr", "max_hr", "training_load", "aerobic_te", "anaerobic_te")])


def get_daily(path, date):
    with _conn(path) as c:
        row = c.execute("SELECT * FROM daily_metrics WHERE date=?", (date,)).fetchone()
        return dict(row) if row else None


def get_trends(path, days):
    with _conn(path) as c:
        rows = c.execute(
            "SELECT * FROM daily_metrics ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_history(path, field, days):
    if field not in DAILY_FIELDS:
        raise ValueError(f"unknown field {field}")
    with _conn(path) as c:
        rows = c.execute(
            f"SELECT {field} FROM daily_metrics ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
        return [r[field] for r in reversed(rows)]


def get_recent_activities(path, limit):
    with _conn(path) as c:
        rows = c.execute(
            "SELECT * FROM activities ORDER BY date DESC, activity_id DESC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]


def write_sync_log(path, status, message, availability):
    with _conn(path) as c:
        c.execute(
            "INSERT INTO sync_log (status, message, availability) VALUES (?,?,?)",
            (status, message, json.dumps(availability or {})))


def get_last_sync(path):
    with _conn(path) as c:
        row = c.execute(
            "SELECT * FROM sync_log ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            return None
        d = dict(row)
        d["availability"] = json.loads(d.get("availability") or "{}")
        return d
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest backend/tests/test_db.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/db.py backend/tests/test_db.py
git commit -m "feat: add SQLite schema with null-preserving upsert/read helpers"
```

### Task 6: Sync orchestration

**Files:**
- Create: `backend/sync.py`
- Test: `backend/tests/test_sync.py`

**Interfaces:**
- Produces: `run_sync(client, db_path) -> dict` (returns `{"status", "message", "availability"}`); computes recovery from stored history + today, computes strain from the day's activities, writes daily + activities + sync_log. Catches `GarminAuthError`/`GarminRateLimitError`/`GarminConnectionError` and logs a failed sync without raising.

- [ ] **Step 1: Write failing test (sync stores data and computes scores; failure logs without raising)**

```python
# backend/tests/test_sync.py
from unittest.mock import MagicMock
import backend.db as db
import backend.sync as sync
from backend.garmin_client import GarminAuthError

def _metrics(hrv, rhr):
    m = {k: None for k in db.DAILY_FIELDS}
    m.update(hrv_last_night=hrv, rhr=rhr, sleep_score=80)
    return m

def test_run_sync_stores_and_scores(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    # seed 20 days of history so recovery can compute
    for i in range(20):
        db.upsert_daily(p, f"2026-05-{i+1:02d}", _metrics(40, 50), None, None)
    client = MagicMock()
    client.fetch_day.return_value = (_metrics(45, 48),
                                     {k: "available" for k in db.DAILY_FIELDS})
    client.fetch_activities.return_value = [{
        "activity_id": 1, "date": "2026-06-19", "type": "running",
        "duration_s": 1800, "avg_hr": 150, "max_hr": 170,
        "training_load": 120, "aerobic_te": 3.0, "anaerobic_te": 0.5}]
    result = sync.run_sync(client, p, today=None)
    assert result["status"] == "ok"
    rows = db.get_trends(p, 60)
    latest = rows[-1]
    assert latest["recovery_score"] is not None
    assert latest["strain_score"] is not None
    assert db.get_last_sync(p)["status"] == "ok"

def test_run_sync_logs_auth_failure_without_raising(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    client = MagicMock()
    client.fetch_day.side_effect = GarminAuthError("bad")
    result = sync.run_sync(client, p, today=None)
    assert result["status"] == "error"
    assert db.get_last_sync(p)["status"] == "error"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_sync.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `backend/sync.py`**

```python
"""Orchestrate a sync: pull yesterday + 30d activities, score, store, log."""
import datetime as dt
import logging

import backend.db as db
from backend import recovery as rec
from backend.config import BASELINE_WINDOW_DAYS
from backend.garmin_client import (
    GarminAuthError, GarminRateLimitError, GarminConnectionError,
)

log = logging.getLogger("sync")


def run_sync(client, db_path, today=None):
    today = today or dt.date.today()
    target = (today - dt.timedelta(days=1)).isoformat()        # yesterday
    start = (today - dt.timedelta(days=30)).isoformat()
    try:
        metrics, availability = client.fetch_day(target)
        activities = client.fetch_activities(start, target)
    except (GarminAuthError, GarminRateLimitError, GarminConnectionError) as e:
        msg = type(e).__name__
        log.warning("sync failed: %s", msg)
        db.write_sync_log(db_path, "error", msg, {})
        return {"status": "error", "message": msg, "availability": {}}

    # baseline history EXCLUDING today's target (avoid self-inclusion)
    hrv_hist = db.get_history(db_path, "hrv_last_night", BASELINE_WINDOW_DAYS)
    rhr_hist = db.get_history(db_path, "rhr", BASELINE_WINDOW_DAYS)
    recovery = rec.recovery_score(metrics.get("hrv_last_night"),
                                  metrics.get("rhr"), hrv_hist, rhr_hist)
    strain = rec.strain_score([a for a in activities if a.get("date") == target])

    db.upsert_daily(db_path, target, metrics, recovery, strain)
    db.upsert_activities(db_path, activities)
    db.write_sync_log(db_path, "ok", "synced", availability)
    return {"status": "ok", "message": "synced", "availability": availability}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_sync.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/sync.py backend/tests/test_sync.py
git commit -m "feat: add sync orchestration with scoring and failure logging"
```

### Task 7: Real sync run + show stored sample (Checkpoint 3)

**Files:**
- Create (temporary): `backend/_checkpoint_sync.py`

- [ ] **Step 1: Write the temporary checkpoint script**

```python
"""Checkpoint 3: real login → run_sync → dump stored sample. Delete after."""
import json
import backend.config as cfg
import backend.db as db
from backend.garmin_client import GarminClient
from backend.sync import run_sync

db.init_db(cfg.DB_PATH)
c = GarminClient(cfg.GARMIN_EMAIL, cfg.GARMIN_PASSWORD, cfg.TOKENSTORE_DIR)
c.login()
print("SYNC RESULT:", json.dumps(run_sync(c, cfg.DB_PATH), indent=2, default=str))
print("LAST SYNC:", json.dumps(db.get_last_sync(cfg.DB_PATH), indent=2, default=str))
print("TRENDS (last 5):", json.dumps(db.get_trends(cfg.DB_PATH, 5), indent=2, default=str))
print("RECENT ACTIVITIES:", json.dumps(db.get_recent_activities(cfg.DB_PATH, 5), indent=2, default=str))
```

- [ ] **Step 2: Run it**

Run: `.venv/Scripts/python -m backend._checkpoint_sync`
Expected: a single real day stored (recovery likely `null` — "building baseline" on a fresh DB, which is expected), activities stored. **STOP and show the user the stored sample for Checkpoint 3.** After confirmation, delete `_checkpoint_pull.py` and `_checkpoint_sync.py`.

```bash
git add -A && git commit -m "chore: remove checkpoint scripts after verification"
```

---

## (Post Checkpoint 3 — frontend, no further mandatory stops)

### Task 8: Flask API + scheduler

**Files:**
- Create: `backend/api.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Produces a Flask app with `GET /api/today`, `GET /api/trends?days=N`, `GET /api/sync-status`, `POST /api/sync`. A background `threading.Timer` loop runs `run_sync` every `SYNC_INTERVAL_SECONDS`. `create_app(db_path, client_factory)` is the testable factory (client_factory injected so tests avoid network).

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_api.py
from unittest.mock import MagicMock
import backend.db as db
from backend.api import create_app

def _client(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    m = {k: None for k in db.DAILY_FIELDS}; m["rhr"] = 50
    db.upsert_daily(p, "2026-06-19", m, recovery=58, strain=20)
    app = create_app(p, client_factory=lambda: MagicMock())
    return app.test_client(), p

def test_today_endpoint_returns_latest(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/api/today")
    assert resp.status_code == 200
    assert resp.get_json()["metrics"]["recovery_score"] == 58

def test_trends_endpoint(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/api/trends?days=14")
    assert resp.status_code == 200
    assert isinstance(resp.get_json()["days"], list)

def test_sync_status_endpoint(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/api/sync-status").status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_api.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `backend/api.py`**

```python
"""Local Flask API serving cached SQLite data + manual/scheduled sync."""
import threading
import logging

from flask import Flask, jsonify, request

import backend.config as cfg
import backend.db as db
from backend.sync import run_sync

log = logging.getLogger("api")


def create_app(db_path=cfg.DB_PATH, client_factory=None):
    app = Flask(__name__, static_folder=None)
    db.init_db(db_path)

    def _trends(days):
        rows = db.get_trends(db_path, days)
        return {
            "days": rows,
            "hrv": [{"date": r["date"], "value": r["hrv_last_night"]} for r in rows],
            "rhr": [{"date": r["date"], "value": r["rhr"]} for r in rows],
        }

    @app.get("/api/today")
    def today():
        rows = db.get_trends(db_path, 1)
        metrics = rows[-1] if rows else None
        return jsonify({
            "metrics": metrics,
            "activities": db.get_recent_activities(db_path, 10),
            "sync": db.get_last_sync(db_path),
        })

    @app.get("/api/trends")
    def trends():
        days = int(request.args.get("days", 30))
        return jsonify(_trends(days))

    @app.get("/api/sync-status")
    def sync_status():
        return jsonify(db.get_last_sync(db_path) or {"status": "never"})

    @app.post("/api/sync")
    def manual_sync():
        if client_factory is None:
            return jsonify({"status": "error", "message": "no client"}), 503
        client = client_factory()
        try:
            client.login()
        except Exception as e:
            db.write_sync_log(db_path, "error", type(e).__name__, {})
            return jsonify({"status": "error", "message": type(e).__name__}), 200
        return jsonify(run_sync(client, db_path))

    return app


def _scheduled_loop(db_path, client_factory):
    try:
        client = client_factory()
        client.login()
        run_sync(client, db_path)
    except Exception as e:
        log.warning("scheduled sync failed: %s", type(e).__name__)
        db.write_sync_log(db_path, "error", type(e).__name__, {})
    finally:
        t = threading.Timer(cfg.SYNC_INTERVAL_SECONDS, _scheduled_loop,
                            args=(db_path, client_factory))
        t.daemon = True
        t.start()


def main():
    logging.basicConfig(level=logging.INFO)
    from backend.garmin_client import GarminClient

    def factory():
        return GarminClient(cfg.GARMIN_EMAIL, cfg.GARMIN_PASSWORD, cfg.TOKENSTORE_DIR)

    app = create_app(cfg.DB_PATH, client_factory=factory)
    _scheduled_loop(cfg.DB_PATH, factory)   # immediate + every 30 min
    app.run(host="127.0.0.1", port=5057)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_api.py -v`
Expected: PASS.

- [ ] **Step 5: Run full backend suite + commit**

Run: `.venv/Scripts/python -m pytest backend -v`
Expected: all PASS.
```bash
git add backend/api.py backend/tests/test_api.py
git commit -m "feat: add Flask API with endpoints and 30-min sync scheduler"
```

### Task 9: Frontend scaffold (Vite + React + Tailwind)

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.js`, `frontend/index.html`, `frontend/tailwind.config.js`, `frontend/postcss.config.js`, `frontend/src/main.jsx`, `frontend/src/index.css`, `frontend/src/api.js`

**Interfaces:**
- Produces an `api.js` exposing `getToday()`, `getTrends(days)`, `getSyncStatus()`, `postSync()` that fetch from `http://127.0.0.1:5057`.

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "garmin-dashboard-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": { "react": "^18.3.1", "react-dom": "^18.3.1", "recharts": "^2.12.7" },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1", "vite": "^5.3.4",
    "tailwindcss": "^3.4.7", "postcss": "^8.4.40", "autoprefixer": "^10.4.19"
  }
}
```

- [ ] **Step 2: Create config files**

`frontend/vite.config.js`:
```js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: { port: 5173 },
  build: { outDir: "dist" },
});
```

`frontend/tailwind.config.js`:
```js
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: { extend: {} },
  plugins: [],
};
```

`frontend/postcss.config.js`:
```js
export default { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

`frontend/index.html`:
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Recovery Dashboard</title>
  </head>
  <body class="bg-neutral-950">
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

`frontend/src/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
body { margin: 0; font-family: ui-sans-serif, system-ui, sans-serif; }
```

- [ ] **Step 3: Create `frontend/src/api.js`**

```js
const BASE = "http://127.0.0.1:5057";
async function j(path, opts) {
  const r = await fetch(BASE + path, opts);
  if (!r.ok) throw new Error("api " + r.status);
  return r.json();
}
export const getToday = () => j("/api/today");
export const getTrends = (days) => j(`/api/trends?days=${days}`);
export const getSyncStatus = () => j("/api/sync-status");
export const postSync = () => j("/api/sync", { method: "POST" });
```

- [ ] **Step 4: Create `frontend/src/main.jsx` (placeholder render; App in Task 10)**

```jsx
import React from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.jsx";
createRoot(document.getElementById("root")).render(<App />);
```

- [ ] **Step 5: Install + verify build tooling**

Run:
```bash
cd "/c/Users/rodri/Documents/garmin-dashboard/frontend" && npm install
```
Expected: installs cleanly. (Build verified in Task 10 once `App.jsx` exists.)

- [ ] **Step 6: Commit**

```bash
cd "/c/Users/rodri/Documents/garmin-dashboard"
git add frontend/package.json frontend/vite.config.js frontend/index.html frontend/tailwind.config.js frontend/postcss.config.js frontend/src/main.jsx frontend/src/index.css frontend/src/api.js
git commit -m "feat: scaffold Vite + React + Tailwind frontend with API client"
```

### Task 10: Dashboard UI components

**Files:**
- Create: `frontend/src/App.jsx`, `frontend/src/components/Gauge.jsx`, `frontend/src/components/TrendChart.jsx`, `frontend/src/components/SleepStages.jsx`, `frontend/src/components/ActivityList.jsx`, `frontend/src/components/SyncHeader.jsx`

**Interfaces:**
- Consumes `api.js` functions and the `/api/today` + `/api/trends` JSON shapes from Task 8.
- Each component renders a "no data" state when its value is `null` (never a placeholder number).

- [ ] **Step 1: `Gauge.jsx` (circular score; handles null → "No data" / "Building baseline")**

```jsx
import React from "react";
const COLORS = { green: "#22c55e", yellow: "#eab308", red: "#ef4444" };
export default function Gauge({ label, value, band, sublabel, nullText = "No data" }) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, value));
  const color = band ? COLORS[band] : "#3b82f6";
  const R = 52, C = 2 * Math.PI * R;
  return (
    <div className="flex flex-col items-center">
      <svg width="140" height="140" viewBox="0 0 140 140">
        <circle cx="70" cy="70" r={R} fill="none" stroke="#27272a" strokeWidth="12" />
        {value != null && (
          <circle cx="70" cy="70" r={R} fill="none" stroke={color} strokeWidth="12"
            strokeDasharray={C} strokeDashoffset={C * (1 - pct / 100)}
            strokeLinecap="round" transform="rotate(-90 70 70)" />
        )}
        <text x="70" y="70" textAnchor="middle" dy="0.35em"
          fill="#fafafa" fontSize={value == null ? "13" : "30"} fontWeight="600">
          {value == null ? nullText : value}
        </text>
      </svg>
      <div className="mt-2 text-neutral-200 font-medium">{label}</div>
      {sublabel && <div className="text-xs text-neutral-500">{sublabel}</div>}
    </div>
  );
}
```

- [ ] **Step 2: `TrendChart.jsx` (14-day line; null gaps preserved)**

```jsx
import React from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
export default function TrendChart({ title, data, color }) {
  const hasData = data && data.some((d) => d.value != null);
  return (
    <div className="bg-neutral-900 rounded-xl p-4">
      <div className="text-neutral-300 text-sm mb-2">{title}</div>
      {!hasData ? (
        <div className="h-40 flex items-center justify-center text-neutral-600 text-sm">No data</div>
      ) : (
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={data}>
            <XAxis dataKey="date" hide />
            <YAxis domain={["auto", "auto"]} stroke="#52525b" fontSize={11} width={28} />
            <Tooltip contentStyle={{ background: "#18181b", border: "none", color: "#fff" }} />
            <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2}
              dot={false} connectNulls={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
```

- [ ] **Step 3: `SleepStages.jsx`**

```jsx
import React from "react";
const STAGES = [
  ["deep_sleep_s", "Deep", "#1d4ed8"], ["light_sleep_s", "Light", "#3b82f6"],
  ["rem_sleep_s", "REM", "#8b5cf6"], ["awake_sleep_s", "Awake", "#52525b"],
];
export default function SleepStages({ metrics }) {
  const vals = STAGES.map(([k]) => metrics?.[k]);
  const total = vals.reduce((s, v) => s + (v || 0), 0);
  return (
    <div className="bg-neutral-900 rounded-xl p-4">
      <div className="text-neutral-300 text-sm mb-2">Last night sleep stages</div>
      {!total ? (
        <div className="h-10 flex items-center text-neutral-600 text-sm">No data</div>
      ) : (
        <>
          <div className="flex h-6 rounded overflow-hidden">
            {STAGES.map(([k, , c]) => (
              <div key={k} style={{ width: `${((metrics[k] || 0) / total) * 100}%`, background: c }} />
            ))}
          </div>
          <div className="flex gap-4 mt-2 text-xs text-neutral-400">
            {STAGES.map(([k, label, c]) => (
              <span key={k}><span style={{ color: c }}>■</span> {label} {Math.round((metrics[k] || 0) / 60)}m</span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: `ActivityList.jsx`**

```jsx
import React from "react";
const fmt = (s) => (s == null ? "—" : `${Math.floor(s / 60)}m`);
export default function ActivityList({ activities }) {
  return (
    <div className="bg-neutral-900 rounded-xl p-4">
      <div className="text-neutral-300 text-sm mb-2">Recent activities</div>
      {!activities || activities.length === 0 ? (
        <div className="text-neutral-600 text-sm">No data</div>
      ) : (
        <ul className="divide-y divide-neutral-800">
          {activities.map((a) => (
            <li key={a.activity_id} className="py-2 flex justify-between text-sm">
              <span className="text-neutral-200 capitalize">{(a.type || "activity").replace(/_/g, " ")}</span>
              <span className="text-neutral-400">{fmt(a.duration_s)} · {a.avg_hr ? `${Math.round(a.avg_hr)} bpm` : "— bpm"}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 5: `SyncHeader.jsx` (last synced + retry)**

```jsx
import React from "react";
function ago(ts) {
  if (!ts) return "never";
  const d = (Date.now() - new Date(ts + "Z").getTime()) / 60000;
  if (d < 1) return "just now";
  if (d < 60) return `${Math.round(d)} min ago`;
  return `${Math.round(d / 60)} h ago`;
}
export default function SyncHeader({ sync, onRetry, syncing }) {
  const err = sync && sync.status === "error";
  return (
    <div className="flex items-center justify-between mb-6">
      <h1 className="text-xl font-semibold text-neutral-100">Recovery Dashboard</h1>
      <div className="flex items-center gap-3 text-sm">
        <span className={err ? "text-red-400" : "text-neutral-400"}>
          {err ? "Sync failed · " : ""}Last synced {ago(sync && sync.timestamp)}
        </span>
        <button onClick={onRetry} disabled={syncing}
          className="px-3 py-1 rounded bg-neutral-800 text-neutral-200 hover:bg-neutral-700 disabled:opacity-50">
          {syncing ? "Syncing…" : "Retry"}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: `App.jsx` (compose; poll today + trends)**

```jsx
import React, { useEffect, useState, useCallback } from "react";
import { getToday, getTrends, postSync } from "./api.js";
import Gauge from "./components/Gauge.jsx";
import TrendChart from "./components/TrendChart.jsx";
import SleepStages from "./components/SleepStages.jsx";
import ActivityList from "./components/ActivityList.jsx";
import SyncHeader from "./components/SyncHeader.jsx";

function band(score) {
  if (score == null) return null;
  if (score >= 67) return "green";
  if (score >= 34) return "yellow";
  return "red";
}

export default function App() {
  const [today, setToday] = useState(null);
  const [trends, setTrends] = useState(null);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [t, tr] = await Promise.all([getToday(), getTrends(14)]);
      setToday(t); setTrends(tr);
    } catch (e) { /* keep last good UI; never crash */ }
  }, []);

  useEffect(() => { load(); const id = setInterval(load, 60000); return () => clearInterval(id); }, [load]);

  const retry = async () => {
    setSyncing(true);
    try { await postSync(); } catch (e) { /* surfaced via sync status */ }
    await load(); setSyncing(false);
  };

  const m = today?.metrics;
  const rec = m?.recovery_score;
  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 p-6 max-w-5xl mx-auto">
      <SyncHeader sync={today?.sync} onRetry={retry} syncing={syncing} />
      <div className="grid grid-cols-3 gap-4 mb-2">
        <Gauge label="Recovery" value={rec} band={band(rec)}
          sublabel="Estimated · not a Garmin/Whoop score"
          nullText="Building baseline" />
        <Gauge label="Sleep" value={m?.sleep_score} band={null} />
        <Gauge label="Strain" value={m?.strain_score} band={null}
          sublabel="Estimated · custom metric" />
      </div>
      <p className="text-center text-xs text-neutral-600 mb-6">
        Recovery &amp; Strain are custom estimates derived from your Garmin data — not official Garmin or Whoop metrics.
      </p>
      <div className="grid grid-cols-2 gap-4 mb-4">
        <TrendChart title="HRV (14-day)" data={trends?.hrv} color="#22c55e" />
        <TrendChart title="Resting HR (14-day)" data={trends?.rhr} color="#f97316" />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <SleepStages metrics={m} />
        <ActivityList activities={today?.activities} />
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Verify production build**

Run: `cd "/c/Users/rodri/Documents/garmin-dashboard/frontend" && npm run build`
Expected: builds to `frontend/dist` without error.

- [ ] **Step 8: Commit**

```bash
cd "/c/Users/rodri/Documents/garmin-dashboard"
git add frontend/src
git commit -m "feat: build dark Whoop-style dashboard UI with no-data states"
```

### Task 11: Electron shell

**Files:**
- Create: `package.json` (root), `electron/main.js`

**Interfaces:**
- Consumes: built frontend at `frontend/dist/index.html`; backend entry `backend.api` run via the venv Python.
- Produces: `npm start` that builds the frontend, spawns the Python backend, opens a window, and kills the backend on quit.

- [ ] **Step 1: Create root `package.json`**

```json
{
  "name": "garmin-dashboard",
  "version": "1.0.0",
  "description": "Local Whoop-style recovery dashboard sourced from Garmin Connect.",
  "main": "electron/main.js",
  "scripts": {
    "build:frontend": "npm --prefix frontend run build",
    "start": "npm run build:frontend && electron .",
    "test:backend": "python -m pytest backend -v"
  },
  "devDependencies": { "electron": "^31.3.0" }
}
```

- [ ] **Step 2: Create `electron/main.js`**

```js
const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

const ROOT = path.join(__dirname, "..");
const isWin = process.platform === "win32";
const PY = path.join(ROOT, ".venv", isWin ? "Scripts/python.exe" : "bin/python");

let backend = null;

function startBackend() {
  const py = fs.existsSync(PY) ? PY : (isWin ? "python" : "python3");
  backend = spawn(py, ["-m", "backend.api"], { cwd: ROOT, stdio: "inherit" });
  backend.on("exit", (code) => console.log("backend exited", code));
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1100, height: 800, backgroundColor: "#0a0a0a",
    webPreferences: { contextIsolation: true },
  });
  win.loadFile(path.join(ROOT, "frontend", "dist", "index.html"));
}

app.whenReady().then(() => {
  startBackend();
  // give Flask a moment to bind before the window fetches
  setTimeout(createWindow, 1500);
});

function killBackend() {
  if (backend && !backend.killed) backend.kill();
}
app.on("window-all-closed", () => { killBackend(); app.quit(); });
app.on("before-quit", killBackend);
process.on("exit", killBackend);
```

- [ ] **Step 3: Install Electron**

Run: `cd "/c/Users/rodri/Documents/garmin-dashboard" && npm install`
Expected: Electron installs.

- [ ] **Step 4: Smoke test (manual)**

Run: `cd "/c/Users/rodri/Documents/garmin-dashboard" && npm start`
Expected: frontend builds, Electron window opens showing the dashboard with real cached data (HRV/RHR/Sleep populated; Recovery shows "Building baseline" until ≥14 days exist). Retry button triggers a sync. Close window → backend process terminates (verify no lingering python in Task 12 note).

- [ ] **Step 5: Commit**

```bash
git add package.json electron/main.js package-lock.json
git commit -m "feat: add Electron shell that manages the Python backend"
```

### Task 12: README + final verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the full `README.md`**

```markdown
# Garmin Recovery Dashboard

A fully-local, Whoop-style recovery dashboard that pulls your Garmin Connect
data (built for a Forerunner 970) and shows Recovery, Sleep, and Strain scores
plus HRV and resting-HR trends. All data stays on your machine — the only
network calls are to Garmin Connect.

> **Recovery and Strain are custom estimates**, not official Garmin or Whoop
> metrics. See `backend/recovery.py` for the documented formula.

## Prerequisites
- Python 3.11+, Node 24+
- A Garmin Connect account with data synced from your watch

## Setup
1. Copy `.env.example` to `.env` and fill in your Garmin credentials:
   ```
   GARMIN_EMAIL=you@example.com
   GARMIN_PASSWORD=your-password
   ```
   `.env` is gitignored and never committed. Credentials are used only to log
   into Garmin Connect and are never logged or printed.
2. Create the Python environment and install backend deps:
   ```
   python -m venv .venv
   .venv\Scripts\python -m pip install -r backend/requirements.txt
   ```
3. Install Node deps (root + frontend):
   ```
   npm install
   npm --prefix frontend install
   ```

## Run
```
npm start
```
This builds the frontend, launches the Python backend (Flask API + sync
scheduler) on `127.0.0.1:5057`, and opens the Electron window. The backend is
terminated when you close the app.

If your account uses MFA, the first login prompts for a code in the terminal;
after that a token is cached in `data/.garth/` and reused.

## How sync works
- On launch and then every **30 minutes**, the backend pulls **yesterday's**
  daily metrics (today's data is incomplete) plus the last 30 days of
  activities, computes the scores, and stores everything in
  `data/dashboard.db` (SQLite).
- The header shows "Last synced X ago"; **Retry** forces an immediate sync.
- If Garmin auth fails or rate-limits (HTTP 429), the app keeps showing the
  last cached data and surfaces the error — it never crashes.
- **Recovery needs ≥14 days of history** to show a score; before that it shows
  "Building baseline". Metrics Garmin doesn't return show "No data" rather than
  a fabricated number.

## Tests
```
npm run test:backend
```
```

- [ ] **Step 2: Run the full backend test suite**

Run: `cd "/c/Users/rodri/Documents/garmin-dashboard" && .venv/Scripts/python -m pytest backend -v`
Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add full setup and usage README"
```

---

## Self-Review (completed during planning)

- **Spec coverage:** auth (T2), all metric pulls + unavailable logging (T3), recovery formula (T4), SQLite schema (T5), sync + 30-min schedule (T6/T8), API endpoints (T8), dark 3-gauge UI + trends + sleep stages + activities (T10), Electron child-process management (T11), README (T12), all four checkpoints (T1, T3, T7, gated). ✓
- **No-fabrication / no-data states:** null preserved through db (T5) and rendered as "No data" in every component (T10). ✓
- **Credential safety:** never logged in client (T2) or sync/api error paths (T6/T8). ✓
- **Type consistency:** `fetch_day`→`(metrics, availability)` consumed by `run_sync`; `DAILY_FIELDS` shared by db/tests; `recovery_score`/`recovery_band`/`strain_score` signatures consistent across T4/T6; API JSON shapes (`metrics`, `activities`, `sync`, `hrv`, `rhr`) consistent across T8/T10. ✓
- **Dependency lock:** only the approved libraries appear. ✓
```
