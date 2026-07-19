# v5.0 C1b: training-plan API endpoints.
import datetime as dt
from unittest.mock import MagicMock

import backend.db as db
import backend.settings as st
from backend.api import create_app

TODAY = dt.date.today().isoformat()
RACE_DATE = (dt.date.today() + dt.timedelta(days=60)).isoformat()

WK_DETAILED = {"index": 1, "start": TODAY, "focus": "base", "target_km": 30,
               "long_run_km": 10, "summary": "base week", "workouts": [{
                   "name": "Easy run", "suggested_date": TODAY,
                   "rationale": "base",
                   "steps": [{"kind": "interval", "duration_type": "time",
                              "duration_value": 1800, "target_type": "none"}]}]}
WK_OUTLINE = {"index": 2, "start": "2099-01-01", "focus": "build",
              "target_km": 36, "long_run_km": 14, "summary": "later",
              "workouts": None}


def _app(tmp_path, configured=True, garmin=None):
    p = tmp_path / "t.db"
    db.init_db(p)
    if configured:
        st.save_settings(p.parent / "settings.json",
                         {"coach_enabled": True, "anthropic_api_key": "k"})
    client = garmin or MagicMock()
    return create_app(p, client_factory=lambda: client), p, client


def test_plan_get_null_when_none(tmp_path):
    app, _, _ = _app(tmp_path)
    assert app.test_client().get("/api/coach/plan").get_json()["plan"] is None


def test_plan_generate_stores_and_returns(tmp_path, monkeypatch):
    from backend import coach
    monkeypatch.setattr(coach, "_call_claude",
                        lambda *a, **k: {"reply": "Strategy.",
                                         "weeks": [WK_DETAILED, WK_OUTLINE]})
    app, p, _ = _app(tmp_path)
    body = app.test_client().post("/api/coach/plan/generate", json={
        "race": {"name": "10k", "date": RACE_DATE, "distance_km": 10,
                 "goal_time_s": None}}).get_json()
    assert body["plan"]["race"]["name"] == "10k"
    assert len(body["plan"]["weeks"]) == 2
    assert db.get_training_plan(p)["race"]["distance_km"] == 10


def test_plan_generate_requires_coach(tmp_path):
    app, _, _ = _app(tmp_path, configured=False)
    body = app.test_client().post("/api/coach/plan/generate", json={
        "race": {"date": RACE_DATE, "distance_km": 10}}).get_json()
    assert body["error"] == "not_configured"


def test_plan_generate_rejects_bad_race(tmp_path):
    app, _, _ = _app(tmp_path)
    resp = app.test_client().post("/api/coach/plan/generate", json={
        "race": {"date": "2020-01-01", "distance_km": 10}})
    assert resp.status_code == 400


def test_plan_push_week_uploads_and_records(tmp_path):
    garmin = MagicMock()
    garmin.push_running_workout.return_value = {"workout_id": 77, "schedule": {"id": 1}}
    app, p, _ = _app(tmp_path, garmin=garmin)
    db.save_training_plan(p, {"name": "10k", "date": RACE_DATE,
                              "distance_km": 10, "goal_time_s": None},
                          [WK_DETAILED, WK_OUTLINE], None)
    body = app.test_client().post("/api/coach/plan/push-week",
                                  json={"week_index": 1}).get_json()
    assert body["ok"] is True
    assert body["pushed"] == 1
    garmin.login.assert_called_once()
    assert garmin.push_running_workout.call_count == 1
    # scheduled on the workout's suggested date
    assert garmin.push_running_workout.call_args[0][1] == TODAY
    assert len(db.list_coach_workouts(p)) == 1


def test_plan_push_week_rejects_outline_week(tmp_path):
    app, p, _ = _app(tmp_path)
    db.save_training_plan(p, {"name": "10k", "date": RACE_DATE,
                              "distance_km": 10, "goal_time_s": None},
                          [WK_DETAILED, WK_OUTLINE], None)
    resp = app.test_client().post("/api/coach/plan/push-week",
                                  json={"week_index": 2})
    assert resp.status_code == 400


def test_plan_delete(tmp_path):
    app, p, _ = _app(tmp_path)
    db.save_training_plan(p, {"name": "10k", "date": RACE_DATE,
                              "distance_km": 10, "goal_time_s": None},
                          [WK_DETAILED], None)
    assert app.test_client().delete("/api/coach/plan").get_json()["ok"] is True
    assert db.get_training_plan(p) is None


def test_plan_adapt_endpoint(tmp_path, monkeypatch):
    from backend import coach
    monkeypatch.setattr(coach, "_call_claude",
                        lambda *a, **k: {"reply": "Eased off.",
                                         "weeks": [WK_DETAILED]})
    app, p, _ = _app(tmp_path)
    db.save_training_plan(p, {"name": "10k", "date": RACE_DATE,
                              "distance_km": 10, "goal_time_s": None},
                          [WK_DETAILED], None)
    body = app.test_client().post("/api/coach/plan/adapt").get_json()
    assert body["plan"]["reply"] == "Eased off."
