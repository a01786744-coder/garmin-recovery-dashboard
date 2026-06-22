# backend/tests/test_sync.py
import datetime as dt
from unittest.mock import MagicMock
import backend.db as db
import backend.sync as sync
from backend.garmin_client import GarminAuthError

TODAY = dt.date(2026, 6, 20)

def _metrics(hrv, rhr):
    m = {k: None for k in db.DAILY_FIELDS}
    m.update(hrv_last_night=hrv, rhr=rhr, hrv_status="BALANCED", sleep_score=80)
    return m

def _client(today_hrv=45, today_rhr=48):
    c = MagicMock()
    c.last_fetch_had_errors = False
    c.fetch_day.return_value = (_metrics(today_hrv, today_rhr),
                                {k: "available" for k in db.DAILY_FIELDS})
    c.fetch_baseline.side_effect = lambda d: {
        "hrv_last_night": 40, "hrv_status": "BALANCED", "rhr": 50}
    c.fetch_activities.return_value = [{
        "activity_id": 1, "date": TODAY.isoformat(), "type": "running",
        "duration_s": 1800, "avg_hr": 150, "max_hr": 170,
        "training_load": 120, "aerobic_te": 3.0, "anaerobic_te": 0.5}]
    # v2 today-only extras — benign defaults so existing tests are unaffected
    c.fetch_performance.return_value = {}
    c.fetch_intraday.return_value = {"hr": None, "stress": None,
                                     "body_battery": None, "hrv": None}
    c.fetch_personal_records.return_value = []
    return c

def test_run_sync_backfills_then_scores_today(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    c = _client()
    result = sync.run_sync(c, p, today=TODAY, backfill_days=30, pacing=0)
    assert result["status"] == "ok"
    today_row = db.get_daily(p, TODAY.isoformat())
    assert today_row["recovery_score"] is not None     # baseline backfilled → score exists
    assert today_row["strain_score"] is not None        # today's activity → strain
    # backfilled ~30 prior days of HRV/RHR exist for the trend
    assert len(db.get_existing_dates(p, 60)) >= 30
    assert db.get_last_sync(p)["status"] == "ok"

def test_run_sync_skips_existing_backfill_days(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    # pre-seed one past day; it must not be re-fetched
    db.upsert_daily(p, "2026-06-10", _metrics(41, 49), None, None)
    c = _client()
    sync.run_sync(c, p, today=TODAY, backfill_days=30, pacing=0)
    fetched_dates = [call.args[0] for call in c.fetch_baseline.call_args_list]
    assert "2026-06-10" not in fetched_dates             # skipped (already present)

def test_run_sync_partial_when_backfill_rate_limited(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    c = _client()
    c.last_fetch_had_errors = True                       # every backfill fetch "errors"
    result = sync.run_sync(c, p, today=TODAY, backfill_days=30, pacing=0)
    assert result["status"] == "partial"                 # stopped early, resume next run
    assert db.get_last_sync(p)["status"] == "partial"

def test_run_sync_logs_auth_failure_without_raising(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    c = MagicMock()
    c.last_fetch_had_errors = False
    c.fetch_baseline.side_effect = GarminAuthError("bad")
    result = sync.run_sync(c, p, today=TODAY, backfill_days=2, pacing=0)
    assert result["status"] == "error"
    assert db.get_last_sync(p)["status"] == "error"


def test_run_sync_stores_perf_intraday_prs(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    c = _client()
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
    p = tmp_path / "t.db"
    db.init_db(p)
    c = _client()
    c.fetch_activity_detail.return_value = {"polyline": [{"lat": 30.1, "lon": -95.5}],
        "splits": [{"distance": 1000}], "hr_zones": [{"zoneNumber": 1}],
        "weather": None, "summary": {"minLat": 30.0}}
    d = sync.sync_activity_detail(c, p, 999)
    assert d["polyline"][0]["lat"] == 30.1
    assert db.get_activity_detail(p, 999)["splits"][0]["distance"] == 1000
