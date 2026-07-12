"""v3.8.0: activities list endpoint + strength exercise sets in the cached
activity detail."""
from unittest.mock import MagicMock

import backend.db as db
from backend.api import create_app
from backend.sync import sync_activity_detail


def _client(tmp_path, factory=None):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    app = create_app(p, client_factory=factory or (lambda: MagicMock()),
                     tokenstore=tmp_path / "garth")
    return app.test_client(), p


def _act(i, date, type_):
    return {"activity_id": i, "date": date, "type": type_, "duration_s": 1800,
            "avg_hr": 140, "max_hr": 165, "training_load": 40,
            "aerobic_te": 2.5, "anaerobic_te": 0.5}


# --- GET /api/activities?limit=N ---

def test_activities_endpoint_returns_recent_with_limit(tmp_path):
    client, p = _client(tmp_path)
    db.upsert_activities(p, [_act(i, f"2026-07-{i:02d}", "running") for i in range(1, 9)])
    body = client.get("/api/activities?limit=3").get_json()
    assert len(body["activities"]) == 3
    assert body["activities"][0]["date"] == "2026-07-08"   # newest first


def test_activities_endpoint_caps_limit(tmp_path):
    client, p = _client(tmp_path)
    db.upsert_activities(p, [_act(1, "2026-07-01", "running")])
    assert client.get("/api/activities?limit=99999").status_code == 200
    assert client.get("/api/activities").status_code == 200   # default limit


# --- strength exercise sets cached with the activity detail ---

def test_fetch_activity_detail_includes_exercise_sets():
    import backend.garmin_client as gc
    api = MagicMock()
    api.get_activity_details.return_value = {}
    api.get_activity_splits.return_value = {}
    api.get_activity_hr_in_timezones.return_value = []
    api.get_activity_weather.return_value = None
    api.get_activity_exercise_sets.return_value = {"exerciseSets": [
        {"exercises": [{"category": "BENCH_PRESS"}], "repetitionCount": 8,
         "weight": 60000.0, "duration": 45.0, "setType": "ACTIVE"},
        {"exercises": [], "setType": "REST", "duration": 90.0},
    ]}
    c = gc.GarminClient("e", "p", "ts"); c._api = api
    d = c.fetch_activity_detail(42)
    assert d["exercise_sets"][0]["repetitionCount"] == 8
    assert d["exercise_sets"][0]["weight"] == 60000.0


def test_exercise_sets_roundtrip_through_cache(tmp_path):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    client = MagicMock()
    client.fetch_activity_detail.return_value = {
        "polyline": None, "splits": None, "hr_zones": None, "weather": None,
        "summary": None,
        "exercise_sets": [{"exercises": [{"category": "SQUAT"}],
                           "repetitionCount": 5, "weight": 100000.0,
                           "setType": "ACTIVE"}],
    }
    d = sync_activity_detail(client, p, 42)
    assert d["exercise_sets"][0]["repetitionCount"] == 5
    # And straight from the cache without a client:
    cached = db.get_activity_detail(p, 42)
    assert cached["exercise_sets"][0]["exercises"][0]["category"] == "SQUAT"
