"""Tests for browse-past-days endpoints: /api/days and /api/day/<date>."""
from unittest.mock import MagicMock

import backend.db as db
from backend.api import create_app


def _client(tmp_path):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    app = create_app(p, client_factory=lambda: MagicMock(), tokenstore=tmp_path / "garth")
    return app.test_client(), p


def _blank():
    return {k: None for k in db.DAILY_FIELDS}


def test_days_lists_dates_sorted_ascending(tmp_path):
    client, p = _client(tmp_path)
    for d in ("2026-06-20", "2026-06-22", "2026-06-21"):
        db.upsert_daily(p, d, _blank(), None, None)
    assert client.get("/api/days").get_json()["dates"] == [
        "2026-06-20", "2026-06-21", "2026-06-22"]


def test_day_returns_metrics_and_only_that_days_activities(tmp_path):
    client, p = _client(tmp_path)
    m = _blank(); m["rhr"] = 44; m["sleep_score"] = 80
    db.upsert_daily(p, "2026-06-21", m, 70, 20)
    db.upsert_activities(p, [
        {"activity_id": 1, "date": "2026-06-21", "type": "running", "duration_s": 1000,
         "avg_hr": 150, "max_hr": 170, "training_load": 50, "aerobic_te": 3, "anaerobic_te": 1},
        {"activity_id": 2, "date": "2026-06-20", "type": "cycling", "duration_s": 2000,
         "avg_hr": 130, "max_hr": 160, "training_load": 40, "aerobic_te": 2, "anaerobic_te": 0},
    ])
    body = client.get("/api/day/2026-06-21").get_json()
    assert body["metrics"]["rhr"] == 44 and body["metrics"]["sleep_score"] == 80
    assert [a["activity_id"] for a in body["activities"]] == [1]


def test_day_missing_returns_null_metrics_and_no_activities(tmp_path):
    client, _ = _client(tmp_path)
    body = client.get("/api/day/2099-01-01").get_json()
    assert body["metrics"] is None
    assert body["activities"] == []


def test_day_rejects_malformed_date(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/api/day/not-a-date").status_code == 400
