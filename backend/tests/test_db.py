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
