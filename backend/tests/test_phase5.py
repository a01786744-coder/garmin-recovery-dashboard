import logging
from unittest.mock import MagicMock

import backend.db as db
from backend.api import create_app, RedactingFilter


def _client(tmp_path):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    app = create_app(p, client_factory=lambda: MagicMock(), tokenstore=tmp_path / "garth")
    return app.test_client(), p


def test_today_includes_progress(tmp_path):
    client, p = _client(tmp_path)
    m = {k: None for k in db.DAILY_FIELDS}
    db.upsert_daily(p, "2026-06-22", m, None, None)
    db.write_sync_log(p, "ok", "synced", {})
    prog = client.get("/api/today").get_json()["progress"]
    assert prog["days_synced"] == 1
    assert prog["target_days"] == 30          # default baseline window
    assert prog["complete"] is True           # last sync status == "ok"


def test_progress_incomplete_on_partial(tmp_path):
    client, p = _client(tmp_path)
    db.write_sync_log(p, "partial", "rate limited", {})
    assert client.get("/api/today").get_json()["progress"]["complete"] is False


def test_export_json(tmp_path):
    client, p = _client(tmp_path)
    m = {k: None for k in db.DAILY_FIELDS}; m["rhr"] = 50
    db.upsert_daily(p, "2026-06-22", m, recovery=60, strain=None)
    r = client.get("/api/export/json")
    assert r.status_code == 200
    assert "attachment" in r.headers["Content-Disposition"]
    body = r.get_json()
    assert body["daily_metrics"][0]["rhr"] == 50
    assert "activities" in body and "perf_metrics" in body and "personal_records" in body


def test_export_csv(tmp_path):
    client, p = _client(tmp_path)
    m = {k: None for k in db.DAILY_FIELDS}; m["steps"] = 1234
    db.upsert_daily(p, "2026-06-22", m, recovery=70, strain=40)
    r = client.get("/api/export/csv")
    assert r.status_code == 200
    assert r.mimetype == "text/csv"
    text = r.get_data(as_text=True)
    lines = text.strip().splitlines()
    assert lines[0].startswith("date,")          # header
    assert "2026-06-22" in lines[1] and "1234" in lines[1]


def _record(msg):
    return logging.LogRecord("t", logging.INFO, __file__, 1, msg, None, None)


def test_redacting_filter_scrubs_credentials():
    f = RedactingFilter()
    rec = _record("login for user me@example.com password=hunter2 ok")
    f.filter(rec)
    out = rec.getMessage()
    assert "me@example.com" not in out
    assert "hunter2" not in out
    assert "[REDACTED]" in out


def test_redacting_filter_scrubs_long_token():
    f = RedactingFilter()
    token = "A" * 60
    rec = _record(f"dumped token {token}")
    f.filter(rec)
    assert token not in rec.getMessage()
