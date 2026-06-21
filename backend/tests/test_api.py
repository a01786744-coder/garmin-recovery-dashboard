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
