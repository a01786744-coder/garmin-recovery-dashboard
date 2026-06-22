# backend/tests/test_api.py
from unittest.mock import MagicMock
import backend.db as db
from backend.api import create_app

def _client(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    m = {k: None for k in db.DAILY_FIELDS}; m["rhr"] = 50
    db.upsert_daily(p, "2026-06-19", m, recovery=58, strain=20)
    app = create_app(p, client_factory=lambda: MagicMock())
    return app.test_client(), p

def test_today_endpoint_returns_latest(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/api/today")
    assert resp.status_code == 200
    assert resp.get_json()["metrics"]["recovery_score"] == 58

def test_trends_endpoint(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.get("/api/trends?days=14")
    assert resp.status_code == 200
    assert isinstance(resp.get_json()["days"], list)

def test_sync_status_endpoint(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/api/sync-status").status_code == 200

def test_responses_carry_cors_header(tmp_path):
    # Electron's file:// renderer can only read the API if it sends ACAO.
    client, _ = _client(tmp_path)
    resp = client.get("/api/today")
    assert resp.headers.get("Access-Control-Allow-Origin") == "*"


def test_today_includes_perf_and_records(tmp_path):
    client, p = _client(tmp_path)
    db.upsert_perf(p, "2026-06-20", {"vo2max": 60})
    db.replace_personal_records(p, [{"id": 1, "type_id": 1, "value": 5.0,
        "activity_id": 9, "activity_name": "R", "start_time": "t"}])
    body = client.get("/api/today").get_json()
    assert body["perf"]["vo2max"] == 60
    assert len(body["records"]) == 1


def test_intraday_endpoint(tmp_path):
    client, p = _client(tmp_path)
    db.upsert_intraday(p, "2026-06-20", "hr", [[1, 48]])
    body = client.get("/api/intraday?date=2026-06-20&metric=hr").get_json()
    assert body["series"] == [[1, 48]]
    miss = client.get("/api/intraday?date=2026-06-20&metric=stress").get_json()
    assert miss["series"] is None


def test_performance_endpoint(tmp_path):
    client, p = _client(tmp_path)
    db.upsert_perf(p, "2026-06-20", {"vo2max": 60, "race_5k": 1205})
    body = client.get("/api/performance").get_json()
    assert body["perf"]["race_5k"] == 1205
    assert isinstance(body["records"], list)


def test_activity_endpoint_returns_cached(tmp_path):
    client, p = _client(tmp_path)
    db.upsert_activity_detail(p, 999, polyline_json=[{"lat": 1.0, "lon": 2.0}])
    body = client.get("/api/activity/999").get_json()
    assert body["polyline"][0]["lat"] == 1.0
