from unittest.mock import MagicMock
import backend.db as db
from backend.api import create_app

def _client(tmp_path):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    app = create_app(p, client_factory=lambda: MagicMock(), tokenstore=tmp_path / "garth")
    return app.test_client(), p

def test_get_perf_history(tmp_path):
    p = tmp_path / "d.db"; db.init_db(p)
    db.upsert_perf(p, "2026-06-20", {"vo2max": 59})
    db.upsert_perf(p, "2026-06-22", {"vo2max": 60})
    hist = db.get_perf_history(p, 90)
    assert [r["date"] for r in hist] == ["2026-06-20", "2026-06-22"]   # ascending
    assert hist[-1]["vo2max"] == 60

def test_trends_includes_perf(tmp_path):
    client, p = _client(tmp_path)
    db.upsert_perf(p, "2026-06-22", {"vo2max": 60, "endurance_score": 6892})
    body = client.get("/api/trends?days=90").get_json()
    assert "perf" in body
    assert body["perf"][-1]["vo2max"] == 60
