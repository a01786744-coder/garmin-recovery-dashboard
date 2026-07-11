"""Sleep debt: cumulative actual-vs-need over the last 7/14 days. Only days
where Garmin reported BOTH values count — a day without data is never assumed
slept or missed (no fabrication)."""
from backend.insights import sleep_debt


def _day(date, actual, baseline):
    return {"date": date, "sleep_need_actual": actual, "sleep_need_baseline": baseline}


def test_sleep_debt_sums_deficits_over_windows():
    # 14 days: each day slept 420 of 480 needed -> 60 min short per day.
    daily = [_day(f"2026-07-{i:02d}", 420, 480) for i in range(1, 15)]
    d = sleep_debt(daily)
    assert d["debt7_min"] == 7 * 60
    assert d["debt14_min"] == 14 * 60
    assert d["days7"] == 7 and d["days14"] == 14
    assert len(d["series"]) == 14
    assert d["series"][-1]["deficit_min"] == 60


def test_sleep_debt_surplus_goes_negative():
    daily = [_day(f"2026-07-{i:02d}", 540, 480) for i in range(1, 8)]  # +1h/night
    d = sleep_debt(daily)
    assert d["debt7_min"] == -7 * 60


def test_sleep_debt_skips_days_without_data():
    daily = [_day("2026-07-01", 420, 480),
             _day("2026-07-02", None, 480),      # actual missing -> not counted
             _day("2026-07-03", 420, None),      # need missing -> not counted
             _day("2026-07-04", 400, 480)]
    d = sleep_debt(daily)
    assert d["debt7_min"] == 60 + 80
    assert d["days7"] == 2
    assert d["series"][1]["deficit_min"] is None


def test_sleep_debt_none_when_no_usable_days():
    assert sleep_debt([_day("2026-07-01", None, None)]) is None
    assert sleep_debt([]) is None
    assert sleep_debt(None) is None


def test_sleep_debt_uses_only_last_14_rows():
    old = [_day(f"2026-06-{i:02d}", 0, 480) for i in range(1, 20)]   # huge debt
    recent = [_day(f"2026-07-{i:02d}", 480, 480) for i in range(1, 15)]  # even
    d = sleep_debt(old + recent)
    assert d["debt14_min"] == 0


# --- backfill must MERGE, not wipe richer fields the daily sync stored ---

def test_backfill_upsert_preserves_existing_fields():
    import backend.db as db
    import tempfile
    from pathlib import Path
    p = Path(tempfile.mkdtemp()) / "t.db"
    db.init_db(p)
    # A full fetch_day row with rich fields.
    m = {k: None for k in db.DAILY_FIELDS}
    m.update(hrv_last_night=60, rhr=45, sleep_need_actual=420,
             sleep_need_baseline=480, training_readiness_score=70)
    db.upsert_daily(p, "2026-07-01", m, 55, 20)
    # A later re-backfill upserts a sparser dict (merge mode): new non-None
    # values win, existing values survive Nones.
    sparse = {k: None for k in db.DAILY_FIELDS}
    sparse.update(hrv_last_night=61, body_battery=80)
    db.upsert_daily(p, "2026-07-01", sparse, 56, None, merge=True)
    row = db.get_daily(p, "2026-07-01")
    assert row["hrv_last_night"] == 61            # updated
    assert row["body_battery"] == 80              # added
    assert row["sleep_need_actual"] == 420        # preserved (was wiped before)
    assert row["training_readiness_score"] == 70  # preserved
    assert row["recovery_score"] == 56
    assert row["strain_score"] == 20              # None in merge -> preserved


def test_fetch_baseline_includes_sleep_need():
    from unittest.mock import MagicMock
    import backend.garmin_client as gc
    api = MagicMock()
    api.get_user_summary.return_value = {"restingHeartRate": 50}
    api.get_hrv_data.return_value = None
    api.get_sleep_data.return_value = {"dailySleepDTO": {
        "sleepNeed": {"actual": 430, "baseline": 480}}}
    c = gc.GarminClient("e", "p", "ts"); c._api = api
    base = c.fetch_baseline("2026-06-19")
    assert base["sleep_need_actual"] == 430
    assert base["sleep_need_baseline"] == 480
