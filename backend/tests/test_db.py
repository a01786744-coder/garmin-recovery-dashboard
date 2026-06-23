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

def test_get_history_before_excludes_target_day(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    for i, d in enumerate(["2026-06-17", "2026-06-18", "2026-06-19"]):
        m = {k: None for k in db.DAILY_FIELDS}
        m["rhr"] = 50 + i
        db.upsert_daily(p, d, m, recovery=None, strain=None)
    # baseline for 2026-06-19 should be the two earlier days only
    assert db.get_history_before(p, "rhr", "2026-06-19", 30) == [50, 51]

def test_get_existing_dates(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    for d in ["2026-06-17", "2026-06-19"]:
        db.upsert_daily(p, d, {k: None for k in db.DAILY_FIELDS}, None, None)
    got = db.get_existing_dates(p, 30)
    assert got == {"2026-06-17", "2026-06-19"}
    assert "2026-06-18" not in got       # a gap to be backfilled

def test_sync_log_roundtrip(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    db.write_sync_log(p, "ok", "synced", {"hrv_last_night": "available"})
    last = db.get_last_sync(p)
    assert last["status"] == "ok"
    assert last["availability"]["hrv_last_night"] == "available"


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


def test_init_db_migrates_old_schema(tmp_path):
    # Simulate a DB created before the v2 columns existed.
    import sqlite3
    p = tmp_path / "old.db"
    con = sqlite3.connect(str(p))
    con.execute("CREATE TABLE daily_metrics (date TEXT PRIMARY KEY, rhr REAL, "
                "recovery_score INTEGER, strain_score INTEGER)")
    con.commit(); con.close()
    db.init_db(p)   # must ADD the new columns, not error
    m = {k: None for k in db.DAILY_FIELDS}
    m["acwr_ratio"] = 0.9; m["floors_ascended"] = 4.0
    db.upsert_daily(p, "2026-06-21", m, recovery=70, strain=30)
    row = db.get_daily(p, "2026-06-21")
    assert row["acwr_ratio"] == 0.9 and row["floors_ascended"] == 4.0


def test_get_primary_day_skips_empty_today(tmp_path):
    # Yesterday has data; today (more recent) is an empty row (the morning gap
    # before the watch syncs). Primary day should be the populated yesterday.
    p = tmp_path / "pd.db"
    db.init_db(p)
    full = {k: None for k in db.DAILY_FIELDS}
    full.update(sleep_score=90, rhr=42, hrv_last_night=70, steps=8000, body_battery=50)
    db.upsert_daily(p, "2026-06-22", full, recovery=None, strain=None)
    db.upsert_daily(p, "2026-06-23", {k: None for k in db.DAILY_FIELDS}, None, None)
    assert db.get_primary_day(p)["date"] == "2026-06-22"


def test_get_primary_day_prefers_today_when_it_has_data(tmp_path):
    p = tmp_path / "pd.db"
    db.init_db(p)
    y = {k: None for k in db.DAILY_FIELDS}; y["sleep_score"] = 80
    t = {k: None for k in db.DAILY_FIELDS}; t["sleep_score"] = 85   # today has last-night data
    db.upsert_daily(p, "2026-06-22", y, None, None)
    db.upsert_daily(p, "2026-06-23", t, None, None)
    assert db.get_primary_day(p)["date"] == "2026-06-23"


def test_get_primary_day_ignores_partial_today_without_sleep(tmp_path):
    # Today has only RHR/steps trickled in (no sleep/HRV yet) — must still show
    # yesterday's completed night, not the empty-gauge today.
    p = tmp_path / "pd.db"
    db.init_db(p)
    y = {k: None for k in db.DAILY_FIELDS}; y["sleep_score"] = 90; y["hrv_last_night"] = 70
    t = {k: None for k in db.DAILY_FIELDS}; t["rhr"] = 45; t["steps"] = 800
    db.upsert_daily(p, "2026-06-22", y, None, None)
    db.upsert_daily(p, "2026-06-23", t, None, None)
    assert db.get_primary_day(p)["date"] == "2026-06-22"


def test_get_primary_day_falls_back_to_latest_when_all_empty(tmp_path):
    p = tmp_path / "pd.db"
    db.init_db(p)
    db.upsert_daily(p, "2026-06-22", {k: None for k in db.DAILY_FIELDS}, None, None)
    db.upsert_daily(p, "2026-06-23", {k: None for k in db.DAILY_FIELDS}, None, None)
    assert db.get_primary_day(p)["date"] == "2026-06-23"   # latest row when none populated


def test_get_primary_day_none_when_empty_db(tmp_path):
    p = tmp_path / "pd.db"
    db.init_db(p)
    assert db.get_primary_day(p) is None
