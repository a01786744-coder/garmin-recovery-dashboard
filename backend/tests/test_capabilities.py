import backend.db as db
import backend.capabilities as caps


def _full_row(**over):
    """A full-fetch day (steps present so it counts toward observed_days)."""
    r = {k: None for k in db.DAILY_FIELDS}
    r["steps"] = 1000  # full-fetch marker
    r.update(over)
    return r


def test_entry_level_profile_hides_unsupported_categories():
    # 30 full days where HRV / Training Readiness / VO2max / ACWR are absent.
    rows = [_full_row(sleep_score=80, stress_avg=20, body_battery=50) for _ in range(30)]
    p = caps.compute_profile(rows, perf_rows=[], records=[], activities=[], ready_days=3)
    assert p["ready"] is True                          # plenty of full days observed
    assert p["supported"]["hrv"] is False
    assert p["supported"]["training_readiness"] is False
    assert p["supported"]["vo2max"] is False
    assert p["supported"]["training_load_acwr"] is False
    # but the watch clearly supports sleep / stress / body battery / steps
    assert p["supported"]["sleep"] is True
    assert p["supported"]["stress"] is True
    assert p["supported"]["body_battery"] is True
    assert p["supported"]["steps_floors"] is True


def test_full_watch_profile_supports_everything():
    rows = [_full_row(hrv_last_night=45, sleep_score=80, stress_avg=20, body_battery=50,
                      training_readiness_score=70, acwr_ratio=0.9, rhr=50,
                      resp_sleep=13, intensity_weekly_total=100, sleep_need_actual=480)
            for _ in range(30)]
    perf = [{"vo2max": 60, "race_5k": 1200, "endurance_score": 6800, "heat_acclimation": 20}]
    p = caps.compute_profile(rows, perf, records=[{"id": 1, "value": 5}],
                             activities=[{"activity_id": 1}], ready_days=3)
    assert p["ready"] is True
    for cat in caps.ALL_CATEGORIES:
        assert p["supported"][cat] is True, f"{cat} should be supported"


def test_one_day_gap_stays_supported():
    # Training Readiness present on 29 days, null on 1 -> still supported.
    rows = [_full_row(training_readiness_score=70) for _ in range(29)]
    rows.append(_full_row(training_readiness_score=None))
    p = caps.compute_profile(rows, [], [], [], ready_days=3)
    assert p["supported"]["training_readiness"] is True


def test_sticky_keeps_previously_supported_category():
    # Today's window shows no HRV, but a prior profile had it -> stays supported.
    rows = [_full_row(hrv_last_night=None) for _ in range(30)]
    prev = {"supported": {"hrv": True}}
    p = caps.compute_profile(rows, [], [], [], prev=prev, ready_days=3)
    assert p["supported"]["hrv"] is True


def test_not_ready_until_enough_full_days():
    rows = [_full_row(sleep_score=80) for _ in range(2)]   # only 2 full days
    p = caps.compute_profile(rows, [], [], [], ready_days=3)
    assert p["observed_days"] == 2
    assert p["ready"] is False
    # baseline-only rows (HRV/RHR but no full markers) do not count
    base_rows = [{**{k: None for k in db.DAILY_FIELDS}, "hrv_last_night": 40, "rhr": 50}
                 for _ in range(30)]
    p2 = caps.compute_profile(base_rows, [], [], [], ready_days=3)
    assert p2["observed_days"] == 0 and p2["ready"] is False


def test_perf_backed_categories():
    rows = [_full_row() for _ in range(5)]
    perf = [{"vo2max": 58, "fitness_age": 30}]
    p = caps.compute_profile(rows, perf, [], [], ready_days=3)
    assert p["supported"]["vo2max"] is True
    assert p["supported"]["race_predictions"] is False
    assert p["supported"]["endurance"] is False


def test_records_and_activities_categories():
    rows = [_full_row() for _ in range(5)]
    p = caps.compute_profile(rows, [], records=[{"id": 1, "value": 5}],
                             activities=[{"activity_id": 9}], ready_days=3)
    assert p["supported"]["personal_records"] is True
    assert p["supported"]["activities"] is True
    p2 = caps.compute_profile(rows, [], [], [], ready_days=3)
    assert p2["supported"]["personal_records"] is False
    assert p2["supported"]["activities"] is False


def test_profile_roundtrip(tmp_path):
    path = tmp_path / "capabilities.json"
    assert caps.load_profile(path) is None
    prof = caps.compute_profile([_full_row(hrv_last_night=40) for _ in range(3)], [], [], [])
    caps.save_profile(path, prof)
    loaded = caps.load_profile(path)
    assert loaded["supported"]["hrv"] is True
    assert "updated" in loaded


def test_default_profile_shows_all_not_ready():
    d = caps.default_profile()
    assert d["ready"] is False
    assert all(d["supported"][c] for c in caps.ALL_CATEGORIES)


def test_run_sync_writes_capability_profile(tmp_path):
    # End-to-end: a sync recomputes + persists the profile next to the DB.
    from unittest.mock import MagicMock
    import datetime as dt
    import backend.sync as sync

    p = tmp_path / "t.db"
    db.init_db(p)
    c = MagicMock()
    c.last_fetch_had_errors = False
    full = {k: None for k in db.DAILY_FIELDS}
    full.update(hrv_last_night=45, rhr=50, sleep_score=80, steps=1000,
                stress_avg=20, body_battery=50)
    c.fetch_day.return_value = (full, {})
    c.fetch_baseline.side_effect = lambda d: {"hrv_last_night": 40, "hrv_status": "BALANCED", "rhr": 50}
    c.fetch_activities.return_value = []
    c.fetch_performance.return_value = {"vo2max": 60}
    c.fetch_intraday.return_value = {}
    c.fetch_personal_records.return_value = []
    c.fetch_device_name.return_value = "fēnix 7"
    sync.run_sync(c, p, today=dt.date(2026, 6, 22), backfill_days=2, pacing=0)
    prof = caps.load_profile(tmp_path / "capabilities.json")
    assert prof is not None
    assert prof["supported"]["sleep"] is True
    assert prof["supported"]["vo2max"] is True       # from perf
    assert prof["device_name"] == "fēnix 7"          # detected device name persisted
