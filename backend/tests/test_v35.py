"""v3.5.0: auth self-healing, score explanations, strain history backfill."""
from unittest.mock import MagicMock

import backend.db as db
import backend.recovery as rec
import backend.settings as st
from backend.api import create_app


def _client(tmp_path, with_tokens=True):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    if with_tokens:
        ts = tmp_path / "garth"; ts.mkdir(parents=True, exist_ok=True)
        (ts / "garmin_tokens.json").write_text("{}")
    app = create_app(p, client_factory=lambda: MagicMock(),
                     tokenstore=tmp_path / "garth")
    return app.test_client(), p


def test_last_sync_statuses_newest_first(tmp_path):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    db.write_sync_log(p, "ok", "synced", {})
    db.write_sync_log(p, "error", "GarminAuthError", {})
    assert db.last_sync_statuses(p, 2) == [("error", "GarminAuthError"), ("ok", "synced")]
    assert db.last_sync_statuses(p, 5) == [("error", "GarminAuthError"), ("ok", "synced")]


def test_needs_relogin_after_three_consecutive_auth_errors(tmp_path):
    client, p = _client(tmp_path)
    for _ in range(3):
        db.write_sync_log(p, "error", "GarminAuthError", {})
    body = client.get("/api/auth/status").get_json()
    assert body["authenticated"] is True
    assert body["needs_relogin"] is True


def test_no_relogin_when_a_recent_sync_succeeded(tmp_path):
    client, p = _client(tmp_path)
    db.write_sync_log(p, "error", "GarminAuthError", {})
    db.write_sync_log(p, "error", "GarminAuthError", {})
    db.write_sync_log(p, "ok", "synced", {})
    assert client.get("/api/auth/status").get_json()["needs_relogin"] is False


def test_start_at_login_setting_default_and_coercion(tmp_path):
    import backend.settings as st
    assert st.load_settings(tmp_path / "settings.json")["start_at_login"] is False
    saved = st.save_settings(tmp_path / "settings.json", {"start_at_login": 1})
    assert saved["start_at_login"] is True


def test_no_relogin_on_fresh_install(tmp_path):
    client, _ = _client(tmp_path, with_tokens=False)
    body = client.get("/api/auth/status").get_json()
    assert body["authenticated"] is False
    assert body["needs_relogin"] is False


# --- recovery explanation (why the score) ---

def test_recovery_explanation_full():
    hrv_hist, rhr_hist = [60, 61, 62, 60, 61], [45, 46, 45, 46, 45]
    ex = rec.recovery_explanation(70, 42, hrv_hist, rhr_hist, min_days=4)
    assert ex["hrv"]["today"] == 70
    assert 60 <= ex["hrv"]["baseline"] <= 62
    assert ex["hrv"]["z"] > 0        # HRV above baseline pushes recovery up
    assert ex["rhr"]["z"] > 0        # RHR below baseline pushes recovery up
    assert ex["weights"] == {"hrv": 0.7, "rhr": 0.3}


def test_recovery_explanation_none_when_score_would_be_none():
    assert rec.recovery_explanation(None, 45, [60] * 5, [45] * 5, min_days=4) is None
    assert rec.recovery_explanation(60, 45, [60] * 2, [45] * 2, min_days=4) is None


# --- strain breakdown (workout vs daily-life) + tuning ---

def test_strain_breakdown_rest_walk_run_land_sensibly():
    rest = rec.strain_breakdown([], {"steps": 2000})
    assert rest["score"] <= 8 and rest["workout"] == 0
    walk = rec.strain_breakdown([], {"steps": 12000, "intensity_moderate": 30})
    assert 25 <= walk["score"] <= 35
    run = rec.strain_breakdown([{"training_load": 90}],
                               {"steps": 12000, "intensity_vigorous": 40})
    assert 55 <= run["score"] <= 70
    assert run["workout"] == 90
    assert run["daily"] < 110        # overlap damping: daily counts at 50%


def test_strain_breakdown_none_without_data():
    assert rec.strain_breakdown([], None) is None


def test_strain_score_matches_breakdown():
    m = {"steps": 9000}
    assert rec.strain_score([], m) == rec.strain_breakdown([], m)["score"]


# --- /api/today exposes both explanations ---

def test_today_includes_explanations(tmp_path):
    client, p = _client(tmp_path)
    st.save_settings(tmp_path / "settings.json", {"baseline_window_days": 7})
    for i in range(1, 6):
        m = {k: None for k in db.DAILY_FIELDS}
        m["hrv_last_night"] = 60 + i % 3; m["rhr"] = 45
        db.upsert_daily(p, f"2026-06-{i:02d}", m, None, None)
    m = {k: None for k in db.DAILY_FIELDS}
    m.update(hrv_last_night=66, rhr=44, steps=8000, sleep_score=80)
    db.upsert_daily(p, "2026-06-06", m, None, None)
    body = client.get("/api/today").get_json()
    assert body["recovery_explain"]["hrv"]["today"] == 66
    assert body["strain_explain"]["score"] > 0
    assert body["strain_explain"]["workout"] == 0


# --- strain history: backfill now parses activity fields (same API call) ---

def test_fetch_baseline_includes_activity_fields():
    import backend.garmin_client as gc
    api = MagicMock()
    api.get_user_summary.return_value = {
        "restingHeartRate": 50, "totalSteps": 9000,
        "moderateIntensityMinutes": 12, "vigorousIntensityMinutes": 3,
        "activeKilocalories": 400, "totalDistanceMeters": 6500}
    api.get_hrv_data.return_value = {"hrvSummary": {"lastNightAvg": 40}}
    api.get_sleep_data.return_value = {}
    c = gc.GarminClient("e", "p", "ts"); c._api = api
    base = c.fetch_baseline("2026-06-19")
    assert base["steps"] == 9000
    assert base["intensity_moderate"] == 12 and base["intensity_vigorous"] == 3
    assert base["active_calories"] == 400 and base["distance_m"] == 6500


def test_baseline_fetch_version_bumped_for_strain_history():
    from backend.config import BASELINE_FETCH_VERSION
    assert BASELINE_FETCH_VERSION >= 3   # triggers the one-time re-backfill


# --- journal correlations vs next-night sleep + structured fields ---

def test_journal_correlation_includes_sleep_metric_and_structured_fields():
    from backend.insights import journal_correlations
    # Sleep alternates low/high; recovery constant (no recovery effect).
    daily = [{"date": f"2026-07-{i:02d}", "recovery_score": 60,
              "sleep_score": 40 if i % 2 == 0 else 90} for i in range(1, 17)]
    entries = [{"date": f"2026-07-{i:02d}",
                "tags": {"screens_in_bed": (i % 2 == 1)}} for i in range(1, 16)]
    out = journal_correlations(daily, entries)
    hits = [c for c in out if c.get("metric") == "sleep" and c.get("tag") == "screens_in_bed"]
    assert hits, f"no sleep correlation found in {out}"
    assert "sleep" in hits[0]["text"].lower() and "lower" in hits[0]["text"]
    assert hits[0]["delta"] < 0
    # No recovery effect should be reported (recovery is flat).
    assert not [c for c in out if c.get("metric") == "recovery"]


# --- weekly extremes for the Monday recap ---

def test_week_extremes_best_and_worst():
    from backend.insights import week_extremes
    daily = [{"date": f"2026-07-{i:02d}", "recovery_score": s}
             for i, s in zip(range(1, 8), [50, 80, None, 20, 60, 70, 40])]
    ex = week_extremes(daily)
    assert ex["best"] == {"date": "2026-07-02", "recovery": 80}
    assert ex["worst"] == {"date": "2026-07-04", "recovery": 20}


def test_week_extremes_none_when_no_scores():
    from backend.insights import week_extremes
    assert week_extremes([{"date": "2026-07-01", "recovery_score": None}]) is None
    assert week_extremes([]) is None
