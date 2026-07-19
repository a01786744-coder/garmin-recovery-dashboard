# v5.0 C1: training plan — storage, generation, adaptation.
import datetime as dt

import pytest

import backend.db as db
from backend import plan

SETTINGS = {"coach_enabled": True, "anthropic_api_key": "k",
            "coach_model": "claude-sonnet-5"}

TODAY = "2026-07-18"


def _race(days_out=86):
    date = (dt.date.fromisoformat(TODAY) + dt.timedelta(days=days_out)).isoformat()
    return {"name": "Half marathon", "date": date, "distance_km": 21.1,
            "goal_time_s": None}


def _week(i, start, workouts=None):
    return {"index": i, "start": start, "focus": "base", "target_km": 32,
            "long_run_km": 12, "summary": f"week {i}", "workouts": workouts}


WK1 = _week(1, "2026-07-20", workouts=[{
    "name": "Easy run", "suggested_date": "2026-07-21",
    "rationale": "aerobic base", "steps": []}])
WK2 = _week(2, "2026-07-27")


def _db(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    return p


# --- storage ---

def test_plan_roundtrip(tmp_path):
    p = _db(tmp_path)
    assert db.get_training_plan(p) is None
    db.save_training_plan(p, _race(), [WK1, WK2], "strategy notes")
    got = db.get_training_plan(p)
    assert got["race"]["distance_km"] == 21.1
    assert [w["index"] for w in got["weeks"]] == [1, 2]
    assert got["weeks"][0]["workouts"][0]["name"] == "Easy run"
    assert got["notes"] == "strategy notes"
    db.delete_training_plan(p)
    assert db.get_training_plan(p) is None


# --- generation ---

def test_generate_plan_stores_and_returns(tmp_path, monkeypatch):
    p = _db(tmp_path)
    from backend import coach
    monkeypatch.setattr(coach, "_call_claude",
                        lambda *a, **k: {"reply": "Plan ready.",
                                         "weeks": [WK1, WK2]})
    out = plan.generate_plan(p, SETTINGS, _race(), today_str=TODAY)
    assert out["race"]["name"] == "Half marathon"
    assert len(out["weeks"]) == 2
    stored = db.get_training_plan(p)
    assert stored["weeks"][1]["summary"] == "week 2"


@pytest.mark.parametrize("bad", [
    {},                                                # missing everything
    {**_race(), "date": "2020-01-01"},                 # race in the past
    {**_race(), "date": "someday"},                    # unparseable
    {**_race(), "distance_km": 0},                     # no distance
])
def test_generate_plan_rejects_bad_race(tmp_path, bad):
    p = _db(tmp_path)
    with pytest.raises(ValueError):
        plan.generate_plan(p, SETTINGS, bad, today_str=TODAY)


# --- adaptation ---

def test_adapt_plan_updates_weeks_keeps_race(tmp_path, monkeypatch):
    p = _db(tmp_path)
    race = _race()
    db.save_training_plan(p, race, [WK1, WK2], None)
    revised = [WK1, {**WK2, "summary": "week 2 (eased off — low recovery)"}]
    from backend import coach
    monkeypatch.setattr(coach, "_call_claude",
                        lambda *a, **k: {"reply": "Eased week 2.",
                                         "weeks": revised})
    out = plan.adapt_plan(p, SETTINGS, today_str="2026-07-25")
    assert out["reply"] == "Eased week 2."
    stored = db.get_training_plan(p)
    assert stored["race"] == race
    assert "eased off" in stored["weeks"][1]["summary"]


def test_adapt_without_plan_raises(tmp_path):
    p = _db(tmp_path)
    with pytest.raises(ValueError):
        plan.adapt_plan(p, SETTINGS, today_str=TODAY)
