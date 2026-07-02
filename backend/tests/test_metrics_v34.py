"""v3.4.0 metric fixes: window-scaled recovery minimum, rescore pass,
baseline progress in /api/today."""
from unittest.mock import MagicMock

import backend.db as db
import backend.recovery as rec
import backend.settings as st
from backend.api import create_app
from backend.sync import rescore_history


def _blank():
    return {k: None for k in db.DAILY_FIELDS}


def _seed_days(p, n, hrv=60, rhr=45, start_day=1):
    """Insert n consecutive June days with HRV/RHR but NO recovery score."""
    for i in range(n):
        m = _blank()
        m["hrv_last_night"] = hrv + (i % 3)   # small variation
        m["rhr"] = rhr + (i % 2)
        db.upsert_daily(p, f"2026-06-{start_day + i:02d}", m, None, None)


# --- min-days scales with the baseline window ---

def test_min_days_scales_with_window():
    assert rec.min_days_for_window(7) == 4
    assert rec.min_days_for_window(10) == 5
    assert rec.min_days_for_window(14) == 7
    assert rec.min_days_for_window(30) == 14   # capped
    assert rec.min_days_for_window(60) == 14   # capped


def test_recovery_score_accepts_min_days_override():
    hist_hrv, hist_rhr = [60, 61, 62, 60, 61], [45, 46, 45, 46, 45]
    assert rec.recovery_score(60, 45, hist_hrv, hist_rhr) is None          # default 14
    s = rec.recovery_score(60, 45, hist_hrv, hist_rhr, min_days=4)
    assert isinstance(s, int) and 0 <= s <= 100


# --- rescore pass heals stored history ---

def test_rescore_history_fills_recovery_for_stored_days(tmp_path):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    _seed_days(p, 8)                       # 8 days, all recovery=None
    rescore_history(p, window=7)           # min_days = 4
    rows = db.get_trends(p, 10)
    by_date = {r["date"]: r for r in rows}
    # First 4 days lack 4 prior days of history -> stay None
    assert by_date["2026-06-02"]["recovery_score"] is None
    # Day 5 onward has >= 4 prior days -> scored
    assert by_date["2026-06-05"]["recovery_score"] is not None
    assert by_date["2026-06-08"]["recovery_score"] is not None


def test_rescore_history_is_idempotent(tmp_path):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    _seed_days(p, 8)
    rescore_history(p, window=7)
    first = {r["date"]: r["recovery_score"] for r in db.get_trends(p, 10)}
    rescore_history(p, window=7)
    second = {r["date"]: r["recovery_score"] for r in db.get_trends(p, 10)}
    assert first == second


# --- /api/today exposes baseline progress; settings change triggers rescore ---

def _client(tmp_path):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    app = create_app(p, client_factory=lambda: MagicMock(),
                     tokenstore=tmp_path / "garth")
    return app.test_client(), p


def test_today_reports_baseline_progress(tmp_path):
    client, p = _client(tmp_path)
    st.save_settings(tmp_path / "settings.json", {"baseline_window_days": 7})
    _seed_days(p, 3)                       # 3 days of history, latest is primary
    body = client.get("/api/today").get_json()
    # Primary day is 06-03; history strictly before it = 2 days; need 4.
    assert body["baseline"] == {"have": 2, "need": 4}


def test_settings_change_rescores_history(tmp_path):
    client, p = _client(tmp_path)
    st.save_settings(tmp_path / "settings.json", {"baseline_window_days": 30})
    _seed_days(p, 10)                      # 10 days, none scored (need 14 at 30d)
    assert all(r["recovery_score"] is None for r in db.get_trends(p, 12))
    client.post("/api/settings", json={"baseline_window_days": 8})   # need = 4
    rows = {r["date"]: r for r in db.get_trends(p, 12)}
    assert rows["2026-06-10"]["recovery_score"] is not None


# --- all-day strain ---

def test_strain_still_none_with_no_inputs_at_all():
    assert rec.strain_score([], None) is None
    assert rec.strain_score([], {"steps": None, "intensity_moderate": None,
                                 "intensity_vigorous": None}) is None


def test_strain_scores_a_no_workout_day_from_steps():
    s = rec.strain_score([], {"steps": 12000})
    assert isinstance(s, int) and 5 <= s <= 40


def test_strain_zero_step_day_scores_low_not_none():
    s = rec.strain_score([], {"steps": 0})
    assert s == 0


def test_strain_intensity_minutes_raise_the_score():
    base = rec.strain_score([], {"steps": 8000})
    more = rec.strain_score([], {"steps": 8000, "intensity_moderate": 30,
                                 "intensity_vigorous": 20})
    assert more > base


def test_strain_workouts_stack_on_top_of_daily_life():
    act = [{"date": "2026-06-22", "training_load": 91}]
    workout_only = rec.strain_score(act, None)
    combined = rec.strain_score(act, {"steps": 13000, "intensity_vigorous": 40})
    assert combined > workout_only


def test_strain_monotonic_in_steps():
    lo = rec.strain_score([], {"steps": 3000})
    hi = rec.strain_score([], {"steps": 18000})
    assert hi > lo


def test_rescore_history_fills_strain_where_steps_exist(tmp_path):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    m = _blank(); m["steps"] = 11000; m["intensity_moderate"] = 25
    db.upsert_daily(p, "2026-06-15", m, None, None)          # no strain stored
    m2 = _blank()                                             # a data-less day
    db.upsert_daily(p, "2026-06-16", m2, None, None)
    rescore_history(p, window=7)
    rows = {r["date"]: r for r in db.get_trends(p, 5)}
    assert rows["2026-06-15"]["strain_score"] is not None
    assert rows["2026-06-16"]["strain_score"] is None         # never fabricate
