"""v3.5.0: auth self-healing (needs_relogin after repeated auth failures)."""
from unittest.mock import MagicMock

import backend.db as db
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


def test_no_relogin_on_fresh_install(tmp_path):
    client, _ = _client(tmp_path, with_tokens=False)
    body = client.get("/api/auth/status").get_json()
    assert body["authenticated"] is False
    assert body["needs_relogin"] is False
