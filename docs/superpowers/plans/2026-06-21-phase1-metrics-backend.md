# Phase 1 — Backend Metrics & Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Fetch, normalize, store, and serve the high-value Forerunner 970 metrics (expanded daily summary, sleep detail, training status & load, readiness sub-factors, performance trends, intraday curves, personal records, and on-demand activity detail incl. GPS route) so the v2 tabbed UI has real data.

**Architecture:** Extend the existing backend (`garmin_client` → `sync` → `db` → Flask `api`). Today-first sync model and paced/429-tolerant backfill are unchanged. New intraday/performance/PR data is fetched for *today* each sync; activity detail (route, splits, HR zones) is fetched on-demand and cached.

**Tech Stack:** Python 3.11, `garminconnect` 0.3.2 (no new backend deps), SQLite, Flask, pytest.

## Global Constraints

- No new backend dependencies (stdlib + existing only).
- Verified field paths (probed live on this FR970 account — code against these exactly):
  - `get_user_summary(d)`: `highlyActiveSeconds`, `activeSeconds`, `sedentarySeconds`, `moderateIntensityMinutes`, `vigorousIntensityMinutes`, `intensityMinutesGoal`, `floorsAscended`, `floorsDescended`, `totalDistanceMeters`, `activeKilocalories`, `bmrKilocalories`, `totalKilocalories`.
  - `get_intensity_minutes_data(d)`: `weeklyModerate`, `weeklyVigorous`, `weeklyTotal`, `weekGoal`.
  - `get_respiration_data(d)`: `avgWakingRespirationValue`, `avgSleepRespirationValue`, `lowestRespirationValue`, `highestRespirationValue`, `respirationValuesArray` = `[[ms_ts, brpm], …]`.
  - `get_sleep_data(d).dailySleepDTO`: existing stages/score PLUS `sleepNeed` = `{baseline, actual, feedback}`, `restlessMomentsCount`, `awakeCount`, `avgOvernightHrv`, `bodyBatteryChange`, and `sleepScores.{deep,light,rem,awakeCount,restlessness}.{value,qualifierKey}`.
  - `get_training_status(d)` (device-keyed maps — see `_primary_device_value` helper):
    - `mostRecentTrainingStatus.latestTrainingStatusData.{deviceId}`: `trainingStatus` (int), `trainingStatusFeedbackPhrase`, `fitnessTrend`, `acuteTrainingLoadDTO.{acwrPercent, acwrStatus, dailyTrainingLoadAcute, dailyTrainingLoadChronic, dailyAcuteChronicWorkloadRatio}`.
    - `mostRecentTrainingLoadBalance.metricsTrainingLoadBalanceDTOMap.{deviceId}`: `monthlyLoadAerobicLow`, `monthlyLoadAerobicHigh`, `monthlyLoadAnaerobic`, `trainingBalanceFeedbackPhrase`, and the `…TargetMin/Max` fields.
    - `mostRecentVO2Max.generic.vo2MaxValue`, `…heatAltitudeAcclimation.{heatAcclimationPercentage, altitudeAcclimation, currentAltitude}`.
  - `get_training_readiness(d)[0]`: `score`, `level`, `feedbackShort`, `sleepScore`, `sleepScoreFactorPercent`, `recoveryTime`, `recoveryTimeFactorPercent`, `acwrFactorPercent`, `acuteLoad`, `stressHistoryFactorPercent`, `hrvFactorPercent`, `hrvWeeklyAverage`, `sleepHistoryFactorPercent`.
  - `get_race_predictions()`: `time5K`, `time10K`, `timeHalfMarathon`, `timeMarathon` (seconds).
  - `get_endurance_score(d)`: `overallScore`, `classification`, `gaugeLowerLimit`, `gaugeUpperLimit`, `classificationLowerLimit{Intermediate,Trained,WellTrained,Expert,Superior,Elite}`.
  - `get_max_metrics(d)`: may be `[]` on the current day; VO2max/fitness age also available via `get_training_status` (`mostRecentVO2Max.generic`). Prefer training_status for VO2max, fall back to max_metrics.
  - `get_personal_record()`: list of `{id, typeId, value, activityId, activityName, prStartTimeGmtFormatted, activityStartDateTimeLocalFormatted}`.
  - Intraday: `get_heart_rates(d).heartRateValues` = `[[ms_ts, bpm], …]`; `get_body_battery(d)` → list, `[0].bodyBatteryValuesArray` = `[[ms_ts, level], …]` + `charged`/`drained`; `get_hrv_data(d).hrvReadings` = `[{hrvValue, readingTimeGMT}, …]` + `hrvSummary.baseline`.
  - Activity detail: `get_activity_details(id, maxpoly=N).geoPolylineDTO` = `{startPoint, endPoint, minLat, maxLat, minLon, maxLon, polyline:[{lat, lon, altitude, time, speed}, …]}`; `get_activity_splits(id).lapDTOs` = `[{distance, duration, averageSpeed, averageHR, maxHR, elevationGain, averageRunCadence, …}]`; `get_activity_hr_in_timezones(id)` = `[{zoneNumber, secsInZone, zoneLowBoundary}, …]`; `get_activity_weather(id)` (situational).
- No fabricated data: every field is null/None when Garmin returns nothing; situational metrics degrade to "No data".
- Never log/print credentials. Sync stays paced + 429-tolerant; never crashes.
- Cost control: intraday/performance/PRs fetched for TODAY only each sync (not backfilled). Backfill stays HRV+RHR only. Activity detail fetched on-demand via `/api/activity/<id>` and cached.

---

### Task 1: Schema expansion — new daily columns + new tables

**Files:**
- Modify: `backend/db.py`
- Test: `backend/tests/test_db.py`

**Interfaces:**
- Extend `DAILY_FIELDS` with new scalar columns (all REAL except `*_status`/`*_label`/`*_feedback` TEXT): `floors_ascended`, `intensity_moderate`, `intensity_vigorous`, `intensity_weekly_total`, `intensity_weekly_goal`, `highly_active_s`, `active_s`, `sedentary_s`, `active_calories`, `resting_calories`, `distance_m`, `resp_waking`, `resp_sleep`, `sleep_need_actual`, `sleep_need_baseline`, `sleep_deep_score`, `sleep_rem_score`, `sleep_light_score`, `sleep_restlessness_score`, `awake_count`, `training_status_label` (TEXT), `acwr_ratio`, `acute_load`, `chronic_load`, `load_aerobic_low`, `load_aerobic_high`, `load_anaerobic`, `tr_sleep_factor`, `tr_recovery_factor`, `tr_acwr_factor`, `tr_hrv_factor`, `tr_stress_factor`.
- New tables + helpers:
  - `daily_intraday(date, metric, json)` PK `(date, metric)`; `upsert_intraday(path, date, metric, data_list)`, `get_intraday(path, date, metric) -> list | None`.
  - `perf_metrics(date PK, vo2max, vo2max_cycling, fitness_age, race_5k, race_10k, race_hm, race_marathon, endurance_score, endurance_class, heat_acclimation, altitude_acclimation)`; `upsert_perf(path, date, perf)`, `get_latest_perf(path) -> dict | None` (most recent non-empty row).
  - `personal_records(id PK, type_id, value, activity_id, activity_name, start_time)`; `replace_personal_records(path, records)` (clear + insert), `get_personal_records(path) -> list`.
  - `activity_detail(activity_id PK, polyline_json, splits_json, hr_zones_json, weather_json, summary_json, fetched_at)`; `upsert_activity_detail(path, activity_id, **json_blobs)`, `get_activity_detail(path, activity_id) -> dict | None` (json fields parsed back to objects).

- [ ] **Step 1: Write failing tests**

```python
def test_expanded_daily_fields_roundtrip(tmp_path):
    p = tmp_path / "t.db"; db.init_db(p)
    m = {k: None for k in db.DAILY_FIELDS}
    m["acwr_ratio"] = 0.8; m["training_status_label"] = "PRODUCTIVE"; m["floors_ascended"] = 3.2
    db.upsert_daily(p, "2026-06-21", m, recovery=70, strain=40)
    row = db.get_daily(p, "2026-06-21")
    assert row["acwr_ratio"] == 0.8
    assert row["training_status_label"] == "PRODUCTIVE"
    assert row["load_anaerobic"] is None      # NULL preserved

def test_intraday_roundtrip(tmp_path):
    p = tmp_path / "t.db"; db.init_db(p)
    series = [[1782018000000, 48], [1782018120000, 50]]
    db.upsert_intraday(p, "2026-06-21", "hr", series)
    assert db.get_intraday(p, "2026-06-21", "hr") == series
    assert db.get_intraday(p, "2026-06-21", "missing") is None

def test_perf_metrics_latest(tmp_path):
    p = tmp_path / "t.db"; db.init_db(p)
    db.upsert_perf(p, "2026-06-20", {"vo2max": 60, "race_5k": 1205, "endurance_score": 6892})
    latest = db.get_latest_perf(p)
    assert latest["vo2max"] == 60 and latest["race_5k"] == 1205

def test_personal_records_replace(tmp_path):
    p = tmp_path / "t.db"; db.init_db(p)
    db.replace_personal_records(p, [{"id": 1, "type_id": 1, "value": 222.5,
        "activity_id": 9, "activity_name": "Run", "start_time": "2026-04-19T06:53:52.0"}])
    db.replace_personal_records(p, [{"id": 1, "type_id": 1, "value": 220.0,
        "activity_id": 9, "activity_name": "Run", "start_time": "2026-04-19T06:53:52.0"}])
    recs = db.get_personal_records(p)
    assert len(recs) == 1 and recs[0]["value"] == 220.0

def test_activity_detail_roundtrip(tmp_path):
    p = tmp_path / "t.db"; db.init_db(p)
    db.upsert_activity_detail(p, 23318459088,
        polyline_json=[{"lat": 30.1, "lon": -95.5}], splits_json=[{"distance": 1000}],
        hr_zones_json=[{"zoneNumber": 1, "secsInZone": 193}], weather_json=None,
        summary_json={"distance": 8000})
    d = db.get_activity_detail(p, 23318459088)
    assert d["polyline"][0]["lat"] == 30.1
    assert d["hr_zones"][0]["zoneNumber"] == 1
    assert d["weather"] is None
```

- [ ] **Step 2: Run to confirm failure**

Run: `.venv/Scripts/python -m pytest backend/tests/test_db.py -v`
Expected: FAIL (new fields/functions missing).

- [ ] **Step 3: Implement**

In `backend/db.py`: (a) append the new field names to `DAILY_FIELDS` with the right types in `init_db`'s column generation — keep the existing TEXT-vs-REAL logic but extend the TEXT set to `("hrv_status", "training_status_label")`; (b) add the three `CREATE TABLE` statements in `init_db`; (c) add the helper functions. Intraday/json columns store via `json.dumps` and read via `json.loads`; `get_activity_detail` maps stored `*_json` columns back to keys `polyline`, `splits`, `hr_zones`, `weather`, `summary`.

```python
# init_db: extend the TEXT-typed set used when building daily_metrics columns
TEXT_FIELDS = ("hrv_status", "training_status_label")
# ... cols = ", ".join(f"{f} TEXT" if f in TEXT_FIELDS else f"{f} REAL" for f in DAILY_FIELDS)

# new tables (add inside init_db)
c.execute("""CREATE TABLE IF NOT EXISTS daily_intraday (
    date TEXT, metric TEXT, json TEXT, PRIMARY KEY (date, metric))""")
c.execute("""CREATE TABLE IF NOT EXISTS perf_metrics (
    date TEXT PRIMARY KEY, vo2max REAL, vo2max_cycling REAL, fitness_age REAL,
    race_5k REAL, race_10k REAL, race_hm REAL, race_marathon REAL,
    endurance_score REAL, endurance_class REAL, heat_acclimation REAL,
    altitude_acclimation REAL)""")
c.execute("""CREATE TABLE IF NOT EXISTS personal_records (
    id INTEGER PRIMARY KEY, type_id INTEGER, value REAL, activity_id INTEGER,
    activity_name TEXT, start_time TEXT)""")
c.execute("""CREATE TABLE IF NOT EXISTS activity_detail (
    activity_id INTEGER PRIMARY KEY, polyline_json TEXT, splits_json TEXT,
    hr_zones_json TEXT, weather_json TEXT, summary_json TEXT, fetched_at TEXT)""")
```

```python
def upsert_intraday(path, date, metric, data_list):
    with _conn(path) as c:
        c.execute("INSERT INTO daily_intraday (date, metric, json) VALUES (?,?,?) "
                  "ON CONFLICT(date, metric) DO UPDATE SET json=excluded.json",
                  (date, metric, json.dumps(data_list)))

def get_intraday(path, date, metric):
    with _conn(path) as c:
        row = c.execute("SELECT json FROM daily_intraday WHERE date=? AND metric=?",
                        (date, metric)).fetchone()
        return json.loads(row["json"]) if row else None

_PERF_COLS = ["vo2max", "vo2max_cycling", "fitness_age", "race_5k", "race_10k",
              "race_hm", "race_marathon", "endurance_score", "endurance_class",
              "heat_acclimation", "altitude_acclimation"]

def upsert_perf(path, date, perf):
    cols = ["date"] + _PERF_COLS
    vals = [date] + [perf.get(k) for k in _PERF_COLS]
    ph = ", ".join("?" for _ in cols)
    upd = ", ".join(f"{c2}=excluded.{c2}" for c2 in cols if c2 != "date")
    with _conn(path) as c:
        c.execute(f"INSERT INTO perf_metrics ({', '.join(cols)}) VALUES ({ph}) "
                  f"ON CONFLICT(date) DO UPDATE SET {upd}", vals)

def get_latest_perf(path):
    with _conn(path) as c:
        row = c.execute("SELECT * FROM perf_metrics ORDER BY date DESC LIMIT 1").fetchone()
        return dict(row) if row else None

def replace_personal_records(path, records):
    with _conn(path) as c:
        c.execute("DELETE FROM personal_records")
        for r in records:
            c.execute("INSERT INTO personal_records (id, type_id, value, activity_id, "
                      "activity_name, start_time) VALUES (?,?,?,?,?,?)",
                      [r.get(k) for k in ("id","type_id","value","activity_id","activity_name","start_time")])

def get_personal_records(path):
    with _conn(path) as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM personal_records ORDER BY type_id").fetchall()]

def upsert_activity_detail(path, activity_id, polyline_json=None, splits_json=None,
                           hr_zones_json=None, weather_json=None, summary_json=None):
    import datetime as _dt
    blobs = [json.dumps(x) if x is not None else None
             for x in (polyline_json, splits_json, hr_zones_json, weather_json, summary_json)]
    with _conn(path) as c:
        c.execute("""INSERT INTO activity_detail (activity_id, polyline_json, splits_json,
            hr_zones_json, weather_json, summary_json, fetched_at) VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(activity_id) DO UPDATE SET polyline_json=excluded.polyline_json,
            splits_json=excluded.splits_json, hr_zones_json=excluded.hr_zones_json,
            weather_json=excluded.weather_json, summary_json=excluded.summary_json,
            fetched_at=excluded.fetched_at""",
            [activity_id] + blobs + [_dt.datetime.now().isoformat()])

def get_activity_detail(path, activity_id):
    with _conn(path) as c:
        row = c.execute("SELECT * FROM activity_detail WHERE activity_id=?",
                        (activity_id,)).fetchone()
        if not row:
            return None
        def _load(v): return json.loads(v) if v else None
        return {"polyline": _load(row["polyline_json"]), "splits": _load(row["splits_json"]),
                "hr_zones": _load(row["hr_zones_json"]), "weather": _load(row["weather_json"]),
                "summary": _load(row["summary_json"]), "fetched_at": row["fetched_at"]}
```

- [ ] **Step 4: Run tests — PASS**

Run: `.venv/Scripts/python -m pytest backend/tests/test_db.py -v` → all pass.
Also run `.venv/Scripts/python -m pytest backend -q` (existing tests must still pass; new DAILY_FIELDS are additive and default to None).

- [ ] **Step 5: Commit**

```bash
git add backend/db.py backend/tests/test_db.py
git commit -m "feat: expand SQLite schema for v2 metrics, intraday, perf, PRs, activity detail"
```

---

### Task 2: garmin_client parsing for the new metrics

**Files:**
- Modify: `backend/garmin_client.py`
- Test: `backend/tests/test_garmin_client.py`

**Interfaces:**
- Module helper `_primary_device_value(device_map)`: given a `{deviceId: {...}}` dict, return the value whose `primaryTrainingDevice` is True, else the first value, else `{}`.
- Extend `fetch_day(date)` to also populate the new daily scalar fields (intensity minutes, floors, active/sedentary seconds, calorie split, distance, respiration, sleep detail/component scores, training status/load/ACWR, readiness sub-factors). Keep existing keys. Continue using `_safe` so missing data → None and `last_fetch_had_errors` still works.
- New methods: `fetch_performance(date) -> dict` (vo2max, fitness_age, race_*, endurance_score/class, acclimation); `fetch_personal_records() -> list[dict]`; `fetch_intraday(date) -> dict[str, list]` (keys `hr`, `stress`, `body_battery`, `hrv`); `fetch_activity_detail(activity_id) -> dict` (keys `polyline`, `splits`, `hr_zones`, `weather`, `summary`).

- [ ] **Step 1: Write failing tests (parse from the real probed shapes)**

```python
def test_primary_device_value_picks_primary():
    m = {"1": {"primaryTrainingDevice": False, "x": 1},
         "2": {"primaryTrainingDevice": True, "x": 2}}
    assert gc._primary_device_value(m)["x"] == 2
    assert gc._primary_device_value({})  == {}

def test_fetch_day_parses_training_and_readiness():
    api = MagicMock()
    api.get_user_summary.return_value = {
        "restingHeartRate": 39, "totalSteps": 1574, "totalKilocalories": 1337.0,
        "activeKilocalories": 5.0, "bmrKilocalories": 1332.0, "averageStressLevel": 20,
        "bodyBatteryMostRecentValue": 50, "highlyActiveSeconds": 229, "activeSeconds": 324,
        "sedentarySeconds": 30287, "moderateIntensityMinutes": 0, "vigorousIntensityMinutes": 2,
        "intensityMinutesGoal": 150, "floorsAscended": 3.16, "totalDistanceMeters": 1228}
    api.get_sleep_data.return_value = {"dailySleepDTO": {
        "deepSleepSeconds": 5580, "lightSleepSeconds": 14160, "remSleepSeconds": 6960,
        "awakeSleepSeconds": 900, "awakeCount": 1, "avgOvernightHrv": 79,
        "sleepNeed": {"actual": 28800, "baseline": 27000},
        "sleepScores": {"overall": {"value": 91}, "deep": {"value": 80},
                        "rem": {"value": 70}, "light": {"value": 60},
                        "restlessness": {"value": 90}}}}
    api.get_hrv_data.return_value = {"hrvSummary": {"lastNightAvg": 79, "status": "BALANCED"}}
    api.get_intensity_minutes_data.return_value = {"weeklyTotal": 116, "weekGoal": 150}
    api.get_respiration_data.return_value = {"avgWakingRespirationValue": 12, "avgSleepRespirationValue": 13}
    api.get_training_readiness.return_value = [{"score": 75, "sleepScoreFactorPercent": 74,
        "recoveryTimeFactorPercent": 80, "acwrFactorPercent": 99, "hrvFactorPercent": 0,
        "stressHistoryFactorPercent": 98, "acuteLoad": 177}]
    api.get_training_status.return_value = {
        "mostRecentTrainingStatus": {"latestTrainingStatusData": {"3626478156": {
            "trainingStatusFeedbackPhrase": "PRODUCTIVE_1", "primaryTrainingDevice": True,
            "acuteTrainingLoadDTO": {"dailyAcuteChronicWorkloadRatio": 0.8,
                "dailyTrainingLoadAcute": 177, "dailyTrainingLoadChronic": 219}}}},
        "mostRecentTrainingLoadBalance": {"metricsTrainingLoadBalanceDTOMap": {"3626478156": {
            "monthlyLoadAerobicLow": 0.0, "monthlyLoadAerobicHigh": 150.7,
            "monthlyLoadAnaerobic": 0.0, "primaryTrainingDevice": True}}}}
    api.get_max_metrics.return_value = []
    metrics, avail = _client_with_api(api).fetch_day("2026-06-21")
    assert metrics["acwr_ratio"] == 0.8
    assert metrics["acute_load"] == 177
    assert metrics["training_status_label"] == "PRODUCTIVE_1"
    assert metrics["load_aerobic_high"] == 150.7
    assert metrics["tr_sleep_factor"] == 74
    assert metrics["sleep_deep_score"] == 80
    assert metrics["sleep_need_actual"] == 28800
    assert metrics["resp_sleep"] == 13
    assert metrics["intensity_weekly_total"] == 116
    assert metrics["sedentary_s"] == 30287
    assert metrics["sleep_score"] == 91   # existing field still works

def test_fetch_performance_parses_predictions_and_endurance():
    api = MagicMock()
    api.get_training_status.return_value = {"mostRecentVO2Max": {"generic": {"vo2MaxValue": 60.0}}}
    api.get_max_metrics.return_value = []
    api.get_race_predictions.return_value = {"time5K": 1205, "time10K": 2536,
        "timeHalfMarathon": 5509, "timeMarathon": 12772}
    api.get_endurance_score.return_value = {"overallScore": 6892, "classification": 4}
    perf = _client_with_api(api).fetch_performance("2026-06-21")
    assert perf["vo2max"] == 60.0
    assert perf["race_5k"] == 1205 and perf["race_marathon"] == 12772
    assert perf["endurance_score"] == 6892 and perf["endurance_class"] == 4

def test_fetch_intraday_parses_arrays():
    api = MagicMock()
    api.get_heart_rates.return_value = {"heartRateValues": [[1, 48], [2, 50]]}
    api.get_stress_data.return_value = {"stressValuesArray": [[1, 20], [2, 25]]}
    api.get_body_battery.return_value = [{"bodyBatteryValuesArray": [[1, 38], [2, 40]]}]
    api.get_hrv_data.return_value = {"hrvReadings": [{"hrvValue": 63, "readingTimeGMT": "t"}]}
    intr = _client_with_api(api).fetch_intraday("2026-06-21")
    assert intr["hr"] == [[1, 48], [2, 50]]
    assert intr["body_battery"] == [[1, 38], [2, 40]]
    assert intr["hrv"][0]["hrvValue"] == 63

def test_fetch_activity_detail_parses_polyline_and_zones():
    api = MagicMock()
    api.get_activity_details.return_value = {"geoPolylineDTO": {
        "polyline": [{"lat": 30.1, "lon": -95.5}], "minLat": 30.0, "maxLat": 30.2}}
    api.get_activity_splits.return_value = {"lapDTOs": [{"distance": 1000, "averageHR": 150}]}
    api.get_activity_hr_in_timezones.return_value = [{"zoneNumber": 1, "secsInZone": 193}]
    api.get_activity_weather.return_value = {"temp": 20}
    d = _client_with_api(api).fetch_activity_detail(999)
    assert d["polyline"][0]["lat"] == 30.1
    assert d["splits"][0]["averageHR"] == 150
    assert d["hr_zones"][0]["zoneNumber"] == 1
    assert d["summary"]["minLat"] == 30.0   # bounds carried in summary
```

- [ ] **Step 2: Run to confirm failure**

Run: `.venv/Scripts/python -m pytest backend/tests/test_garmin_client.py -v` → FAIL.

- [ ] **Step 3: Implement**

Add the module helper and methods; extend `fetch_day`'s metrics dict with the new keys (all via `.get()` chains so missing → None). Use `_safe` for every new API call so errors set `last_fetch_had_errors`.

```python
def _primary_device_value(device_map):
    if not isinstance(device_map, dict) or not device_map:
        return {}
    for v in device_map.values():
        if isinstance(v, dict) and v.get("primaryTrainingDevice"):
            return v
    return next(iter(device_map.values()), {}) or {}
```

In `fetch_day`, after the existing calls, add (using `_safe`):
```python
        intensity = self._safe(lambda: api.get_intensity_minutes_data(date_str), {}) or {}
        resp = self._safe(lambda: api.get_respiration_data(date_str), {}) or {}
        tstat = self._safe(lambda: api.get_training_status(date_str), {}) or {}
        tr0 = (self._safe(lambda: api.get_training_readiness(date_str), []) or [{}])
        tr0 = tr0[0] if tr0 else {}

        ts_data = _primary_device_value(
            ((tstat.get("mostRecentTrainingStatus") or {}).get("latestTrainingStatusData")) or {})
        acute = ts_data.get("acuteTrainingLoadDTO", {}) or {}
        load_bal = _primary_device_value(
            ((tstat.get("mostRecentTrainingLoadBalance") or {}).get("metricsTrainingLoadBalanceDTOMap")) or {})
        scores = (sdto.get("sleepScores") or {})
        sleep_need = (sdto.get("sleepNeed") or {})
```
…and extend the `metrics` dict with:
```python
            "floors_ascended": summary.get("floorsAscended"),
            "intensity_moderate": summary.get("moderateIntensityMinutes"),
            "intensity_vigorous": summary.get("vigorousIntensityMinutes"),
            "intensity_weekly_total": intensity.get("weeklyTotal"),
            "intensity_weekly_goal": intensity.get("weekGoal"),
            "highly_active_s": summary.get("highlyActiveSeconds"),
            "active_s": summary.get("activeSeconds"),
            "sedentary_s": summary.get("sedentarySeconds"),
            "active_calories": summary.get("activeKilocalories"),
            "resting_calories": summary.get("bmrKilocalories"),
            "distance_m": summary.get("totalDistanceMeters"),
            "resp_waking": resp.get("avgWakingRespirationValue"),
            "resp_sleep": resp.get("avgSleepRespirationValue"),
            "sleep_need_actual": sleep_need.get("actual"),
            "sleep_need_baseline": sleep_need.get("baseline"),
            "sleep_deep_score": (scores.get("deep") or {}).get("value"),
            "sleep_rem_score": (scores.get("rem") or {}).get("value"),
            "sleep_light_score": (scores.get("light") or {}).get("value"),
            "sleep_restlessness_score": (scores.get("restlessness") or {}).get("value"),
            "awake_count": sdto.get("awakeCount"),
            "training_status_label": ts_data.get("trainingStatusFeedbackPhrase"),
            "acwr_ratio": acute.get("dailyAcuteChronicWorkloadRatio"),
            "acute_load": acute.get("dailyTrainingLoadAcute"),
            "chronic_load": acute.get("dailyTrainingLoadChronic"),
            "load_aerobic_low": load_bal.get("monthlyLoadAerobicLow"),
            "load_aerobic_high": load_bal.get("monthlyLoadAerobicHigh"),
            "load_anaerobic": load_bal.get("monthlyLoadAnaerobic"),
            "tr_sleep_factor": tr0.get("sleepScoreFactorPercent"),
            "tr_recovery_factor": tr0.get("recoveryTimeFactorPercent"),
            "tr_acwr_factor": tr0.get("acwrFactorPercent"),
            "tr_hrv_factor": tr0.get("hrvFactorPercent"),
            "tr_stress_factor": tr0.get("stressHistoryFactorPercent"),
```
Keep `training_readiness_score` sourced from `tr0.get("score")` (replaces the old separate call — reuse `tr0`).

New methods:
```python
    def fetch_performance(self, date_str):
        self._fetch_errors = 0
        api = self.api
        tstat = self._safe(lambda: api.get_training_status(date_str), {}) or {}
        generic = ((tstat.get("mostRecentVO2Max") or {}).get("generic")) or {}
        accl = ((tstat.get("mostRecentVO2Max") or {}).get("heatAltitudeAcclimation")) or {}
        maxmet = self._safe(lambda: api.get_max_metrics(date_str), None)
        mg = {}
        if isinstance(maxmet, list) and maxmet:
            mg = (maxmet[0] or {}).get("generic", {}) or {}
        race = self._safe(lambda: api.get_race_predictions(), {}) or {}
        endur = self._safe(lambda: api.get_endurance_score(date_str), {}) or {}
        return {
            "vo2max": generic.get("vo2MaxValue") or mg.get("vo2MaxValue"),
            "vo2max_cycling": ((tstat.get("mostRecentVO2Max") or {}).get("cycling") or {}).get("vo2MaxValue"),
            "fitness_age": generic.get("fitnessAge") or mg.get("fitnessAge"),
            "race_5k": race.get("time5K"), "race_10k": race.get("time10K"),
            "race_hm": race.get("timeHalfMarathon"), "race_marathon": race.get("timeMarathon"),
            "endurance_score": endur.get("overallScore"), "endurance_class": endur.get("classification"),
            "heat_acclimation": accl.get("heatAcclimationPercentage"),
            "altitude_acclimation": accl.get("altitudeAcclimation"),
        }

    def fetch_personal_records(self):
        self._fetch_errors = 0
        api = self.api
        raw = self._safe(lambda: api.get_personal_record(), []) or []
        out = []
        for r in raw:
            r = r or {}
            out.append({"id": r.get("id"), "type_id": r.get("typeId"), "value": r.get("value"),
                        "activity_id": r.get("activityId"), "activity_name": r.get("activityName"),
                        "start_time": r.get("prStartTimeGmtFormatted") or r.get("activityStartDateTimeLocalFormatted")})
        return out

    def fetch_intraday(self, date_str):
        self._fetch_errors = 0
        api = self.api
        hr = self._safe(lambda: api.get_heart_rates(date_str), {}) or {}
        stress = self._safe(lambda: api.get_stress_data(date_str), {}) or {}
        bb = self._safe(lambda: api.get_body_battery(date_str), []) or []
        hrv = self._safe(lambda: api.get_hrv_data(date_str), {}) or {}
        bb0 = bb[0] if isinstance(bb, list) and bb else {}
        return {
            "hr": hr.get("heartRateValues"),
            "stress": stress.get("stressValuesArray"),
            "body_battery": bb0.get("bodyBatteryValuesArray"),
            "hrv": hrv.get("hrvReadings"),
        }

    def fetch_activity_detail(self, activity_id, maxpoly=2000):
        self._fetch_errors = 0
        api = self.api
        det = self._safe(lambda: api.get_activity_details(activity_id, maxpoly=maxpoly), {}) or {}
        geo = det.get("geoPolylineDTO", {}) or {}
        splits = self._safe(lambda: api.get_activity_splits(activity_id), {}) or {}
        zones = self._safe(lambda: api.get_activity_hr_in_timezones(activity_id), []) or []
        weather = self._safe(lambda: api.get_activity_weather(activity_id), None)
        summary = {k: geo.get(k) for k in ("minLat", "maxLat", "minLon", "maxLon", "startPoint", "endPoint")}
        return {
            "polyline": geo.get("polyline"),
            "splits": splits.get("lapDTOs"),
            "hr_zones": zones if isinstance(zones, list) else None,
            "weather": weather,
            "summary": summary,
        }
```

- [ ] **Step 4: Run tests — PASS**, then `.venv/Scripts/python -m pytest backend -q`.

- [ ] **Step 5: Commit**

```bash
git add backend/garmin_client.py backend/tests/test_garmin_client.py
git commit -m "feat: parse expanded daily metrics, performance, intraday, PRs, activity detail"
```

---

### Task 3: Sync expansion

**Files:**
- Modify: `backend/sync.py`
- Test: `backend/tests/test_sync.py`

**Interfaces:**
- `run_sync` additionally, for TODAY only: stores `fetch_performance(today)` via `db.upsert_perf`; stores `fetch_intraday(today)` arrays via `db.upsert_intraday` (one row per non-null metric); refreshes `fetch_personal_records()` via `db.replace_personal_records`. Backfill path unchanged (HRV/RHR only). All wrapped so failures degrade to the existing "partial"/"error" handling and never crash. The expanded `fetch_day` already fills the new daily scalars — no extra work for those.
- New function `sync_activity_detail(client, db_path, activity_id) -> dict | None`: fetch + cache one activity's detail (used by the API on-demand); returns the stored detail.

- [ ] **Step 1: Write failing tests**

```python
def test_run_sync_stores_perf_intraday_prs(tmp_path):
    p = tmp_path / "t.db"; db.init_db(p)
    c = _client()   # existing helper; extend it below
    c.fetch_performance.return_value = {"vo2max": 60, "race_5k": 1205, "endurance_score": 6892}
    c.fetch_intraday.return_value = {"hr": [[1, 48]], "stress": None,
                                     "body_battery": [[1, 38]], "hrv": None}
    c.fetch_personal_records.return_value = [{"id": 1, "type_id": 1, "value": 222.5,
        "activity_id": 9, "activity_name": "Run", "start_time": "t"}]
    sync.run_sync(c, p, today=TODAY, backfill_days=2, pacing=0)
    assert db.get_latest_perf(p)["vo2max"] == 60
    assert db.get_intraday(p, TODAY.isoformat(), "hr") == [[1, 48]]
    assert db.get_intraday(p, TODAY.isoformat(), "stress") is None   # null metric not stored
    assert len(db.get_personal_records(p)) == 1

def test_sync_activity_detail_caches(tmp_path):
    p = tmp_path / "t.db"; db.init_db(p)
    c = _client()
    c.fetch_activity_detail.return_value = {"polyline": [{"lat": 30.1, "lon": -95.5}],
        "splits": [{"distance": 1000}], "hr_zones": [{"zoneNumber": 1}],
        "weather": None, "summary": {"minLat": 30.0}}
    d = sync.sync_activity_detail(c, p, 999)
    assert d["polyline"][0]["lat"] == 30.1
    assert db.get_activity_detail(p, 999)["splits"][0]["distance"] == 1000
```

Extend the `_client()` helper in test_sync.py so the MagicMock also returns the new methods (`fetch_performance`, `fetch_intraday`, `fetch_personal_records`, `fetch_activity_detail`) with sensible defaults, and keep `last_fetch_had_errors = False`.

- [ ] **Step 2: Run to confirm failure** → FAIL.

- [ ] **Step 3: Implement** — after today's `fetch_day`/activities block in `run_sync`, add:

```python
    # today-only extras (cost-controlled: not backfilled)
    try:
        perf = client.fetch_performance(today_str)
        db.upsert_perf(db_path, today_str, perf)
        intr = client.fetch_intraday(today_str)
        for metric, series in intr.items():
            if series:
                db.upsert_intraday(db_path, today_str, metric, series)
        prs = client.fetch_personal_records()
        if prs:
            db.replace_personal_records(db_path, prs)
    except _FETCH_ERRORS as e:
        log.warning("extras fetch failed: %s", type(e).__name__)  # non-fatal; core day already stored
```

And add:
```python
def sync_activity_detail(client, db_path, activity_id):
    try:
        d = client.fetch_activity_detail(activity_id)
    except _FETCH_ERRORS as e:
        log.warning("activity detail fetch failed: %s", type(e).__name__)
        return db.get_activity_detail(db_path, activity_id)
    db.upsert_activity_detail(db_path, activity_id, polyline_json=d.get("polyline"),
        splits_json=d.get("splits"), hr_zones_json=d.get("hr_zones"),
        weather_json=d.get("weather"), summary_json=d.get("summary"))
    return db.get_activity_detail(db_path, activity_id)
```

- [ ] **Step 4: Run tests — PASS**, then full `pytest backend -q`.

- [ ] **Step 5: Commit**

```bash
git add backend/sync.py backend/tests/test_sync.py
git commit -m "feat: sync expanded perf/intraday/PR data and on-demand activity detail"
```

---

### Task 4: API endpoints for the new data

**Files:**
- Modify: `backend/api.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- `GET /api/today` (expanded): already returns the latest daily row (now with all new columns) + activities + sync; add `"perf": db.get_latest_perf(db_path)` and `"records": db.get_personal_records(db_path)`.
- `GET /api/intraday?date=YYYY-MM-DD&metric=hr|stress|body_battery|hrv` → `{ "metric":…, "date":…, "series": <list|null> }`.
- `GET /api/performance` → `{ "perf": …, "records": [...] }`.
- `GET /api/activity/<int:activity_id>` → cached detail if present, else triggers `sync_activity_detail` via the injected client (returns `{}`/503-safe if no client), then returns the stored detail.

- [ ] **Step 1: Write failing tests**

```python
def test_today_includes_perf_and_records(tmp_path):
    client, p = _client(tmp_path)   # existing helper
    db.upsert_perf(p, "2026-06-20", {"vo2max": 60})
    db.replace_personal_records(p, [{"id": 1, "type_id": 1, "value": 5.0,
        "activity_id": 9, "activity_name": "R", "start_time": "t"}])
    body = client.get("/api/today").get_json()
    assert body["perf"]["vo2max"] == 60
    assert len(body["records"]) == 1

def test_intraday_endpoint(tmp_path):
    client, p = _client(tmp_path)
    db.upsert_intraday(p, "2026-06-20", "hr", [[1, 48]])
    body = client.get("/api/intraday?date=2026-06-20&metric=hr").get_json()
    assert body["series"] == [[1, 48]]
    miss = client.get("/api/intraday?date=2026-06-20&metric=stress").get_json()
    assert miss["series"] is None

def test_activity_endpoint_returns_cached(tmp_path):
    client, p = _client(tmp_path)
    db.upsert_activity_detail(p, 999, polyline_json=[{"lat": 1.0, "lon": 2.0}])
    body = client.get("/api/activity/999").get_json()
    assert body["polyline"][0]["lat"] == 1.0
```

- [ ] **Step 2: Run to confirm failure** → FAIL.

- [ ] **Step 3: Implement** the new routes in `create_app`; `/api/today` gains `perf` + `records`. `/api/activity/<id>`: if `db.get_activity_detail` is None and a `client_factory` exists, call `sync_activity_detail` (login first, guarded) then return the cached detail; otherwise return the cached value or `{}`.

- [ ] **Step 4: Run tests — PASS**, then full `pytest backend -q`.

- [ ] **Step 5: Commit**

```bash
git add backend/api.py backend/tests/test_api.py
git commit -m "feat: API endpoints for perf, records, intraday, and activity detail"
```

---

### Task 5: Live verification (no mandatory stop)

**Files:** none committed (temporary script, deleted after).

- [ ] **Step 1:** Write `backend/_verify_phase1.py` that logs in, runs `run_sync`, then prints: today's expanded daily row, `get_latest_perf`, count of intraday metrics stored for today, `get_personal_records` count, and `sync_activity_detail` for the most recent activity (polyline point count, splits count, hr-zone count).
- [ ] **Step 2:** Run it in the background (paced; may be "partial" on rate limit). Show the controller the real stored output, confirm the new metrics populate (or are honest "No data"), then delete the script and commit its removal.

---

## Self-Review (run after writing)

- Spec coverage: expanded daily metrics (T1/T2), intraday curves (T1/T2/T3), training status/load + readiness sub-factors (T2), performance/race/endurance/VO2/fitness-age (T2/T3), PRs (T2/T3), activity detail incl. GPS polyline (T2/T3), all endpoints (T4), live check (T5). ✓
- Field paths copied verbatim from live probes (device-keyed maps handled via `_primary_device_value`). ✓
- No fabrication: every new field via `.get()` → None; null intraday metrics not stored; situational metrics degrade. ✓
- Cost control: extras + intraday today-only; activity detail on-demand; backfill unchanged. ✓
- No new dependencies. ✓
