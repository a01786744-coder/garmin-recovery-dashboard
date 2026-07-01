from unittest.mock import MagicMock

import backend.db as db
import backend.settings as st
from backend.api import create_app


def test_phone_access_and_pin_defaults(tmp_path):
    s = st.load_settings(tmp_path / "settings.json")
    assert s["phone_access"] is False
    assert s["access_pin"] == ""


def test_phone_access_coerced_to_bool_and_pin_to_str(tmp_path):
    p = tmp_path / "settings.json"
    saved = st.save_settings(p, {"phone_access": 1, "access_pin": 1234})
    assert saved["phone_access"] is True
    assert saved["access_pin"] == "1234"
    assert st.load_settings(p) == saved


def _client(tmp_path, pin=""):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    st.save_settings(tmp_path / "settings.json", {"phone_access": True, "access_pin": pin})
    app = create_app(p, client_factory=lambda: MagicMock(), tokenstore=tmp_path / "garth")
    return app.test_client()


def test_loopback_bypasses_pin(tmp_path):
    c = _client(tmp_path, pin="1234")
    assert c.get("/api/sync-status").status_code == 200  # default REMOTE_ADDR is 127.0.0.1


def test_remote_requires_valid_pin(tmp_path):
    c = _client(tmp_path, pin="1234")
    remote = {"REMOTE_ADDR": "192.168.1.20"}
    assert c.get("/api/sync-status", environ_base=remote).status_code == 401
    ok = c.get("/api/sync-status", environ_base=remote, headers={"X-Access-Pin": "1234"})
    assert ok.status_code == 200


def test_remote_denied_when_no_pin_configured(tmp_path):
    c = _client(tmp_path, pin="")
    r = c.get("/api/sync-status", environ_base={"REMOTE_ADDR": "10.0.0.9"},
              headers={"X-Access-Pin": ""})
    assert r.status_code == 401
