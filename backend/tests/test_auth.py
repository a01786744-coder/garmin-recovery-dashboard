from unittest.mock import MagicMock

import backend.db as db
from backend.api import create_app, _has_tokens, _clear_tokens
from backend.garmin_client import GarminMFARequired, GarminAuthError

PASSWORD = "sup3r-secret-pw"


def _app(tmp_path, fake_login):
    """Build an app whose auth_client_factory returns a fake client. The fake's
    login()/complete_mfa() behavior is driven by `fake_login`, which receives
    (client, tokenstore)."""
    p = tmp_path / "t.db"
    db.init_db(p)
    ts = tmp_path / "garth"

    def factory(email, password, tokenstore):
        c = MagicMock()
        c._email, c._password, c._tokenstore = email, password, str(tokenstore)
        fake_login(c, tokenstore)
        return c

    app = create_app(p, client_factory=lambda: MagicMock(),
                     tokenstore=ts, auth_client_factory=factory)
    return app.test_client(), ts


def _write_token(ts):
    ts.mkdir(parents=True, exist_ok=True)
    (ts / "oauth2_token.json").write_text("{}")


def test_status_false_when_no_tokens(tmp_path):
    client, ts = _app(tmp_path, lambda c, t: None)
    assert client.get("/api/auth/status").get_json() == {"authenticated": False}


def test_login_success_then_status_true(tmp_path):
    # success: the real GarminClient.login() would persist tokens; the fake
    # simulates that by writing a token file.
    def fake(c, ts):
        c.login.side_effect = lambda: _write_token(ts)
    client, ts = _app(tmp_path, fake)
    r = client.post("/api/auth/login", json={"email": "a@b.com", "password": PASSWORD})
    assert r.get_json() == {"status": "ok"}
    assert client.get("/api/auth/status").get_json()["authenticated"] is True


def test_login_missing_credentials(tmp_path):
    client, ts = _app(tmp_path, lambda c, t: None)
    r = client.post("/api/auth/login", json={"email": "", "password": ""})
    assert r.status_code == 400
    assert r.get_json()["message"] == "missing_credentials"


def test_login_auth_error_message_has_no_password(tmp_path):
    def fake(c, ts):
        c.login.side_effect = GarminAuthError("bad")
    client, ts = _app(tmp_path, fake)
    r = client.post("/api/auth/login", json={"email": "a@b.com", "password": PASSWORD})
    body = r.get_json()
    assert body["status"] == "error" and body["message"] == "authentication_failed"
    assert PASSWORD not in r.get_data(as_text=True)   # password never echoed
    assert client.get("/api/auth/status").get_json()["authenticated"] is False


def test_login_mfa_required_then_complete(tmp_path):
    def fake(c, ts):
        c.login.side_effect = GarminMFARequired({"state": 1})
        c.complete_mfa.side_effect = lambda state, code: _write_token(ts)
    client, ts = _app(tmp_path, fake)
    r1 = client.post("/api/auth/login", json={"email": "a@b.com", "password": PASSWORD})
    assert r1.get_json() == {"status": "mfa_required"}
    r2 = client.post("/api/auth/mfa", json={"code": "123456"})
    assert r2.get_json() == {"status": "ok"}
    assert client.get("/api/auth/status").get_json()["authenticated"] is True


def test_mfa_without_pending_login(tmp_path):
    client, ts = _app(tmp_path, lambda c, t: None)
    r = client.post("/api/auth/mfa", json={"code": "123456"})
    assert r.status_code == 400


def test_logout_clears_tokens(tmp_path):
    def fake(c, ts):
        c.login.side_effect = lambda: _write_token(ts)
    client, ts = _app(tmp_path, fake)
    client.post("/api/auth/login", json={"email": "a@b.com", "password": PASSWORD})
    assert client.get("/api/auth/status").get_json()["authenticated"] is True
    assert client.post("/api/auth/logout").get_json() == {"status": "ok"}
    assert client.get("/api/auth/status").get_json()["authenticated"] is False


def test_has_and_clear_tokens_helpers(tmp_path):
    ts = tmp_path / "garth"
    assert _has_tokens(ts) is False
    _write_token(ts)
    assert _has_tokens(ts) is True
    _clear_tokens(ts)
    assert _has_tokens(ts) is False
