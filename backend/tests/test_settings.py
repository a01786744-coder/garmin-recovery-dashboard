from unittest.mock import MagicMock

import backend.db as db
import backend.settings as st
from backend.api import create_app


# --- settings module ---

def test_defaults_when_no_file(tmp_path):
    s = st.load_settings(tmp_path / "settings.json")
    assert s == st.DEFAULTS
    assert s is not st.DEFAULTS   # returns a copy, not the shared default


def test_validation_clamps_and_coerces(tmp_path):
    p = tmp_path / "settings.json"
    saved = st.save_settings(p, {
        "units": "furlongs",          # invalid -> metric
        "sync_interval_minutes": 9999,  # clamp -> 240
        "baseline_window_days": 1,      # clamp -> 7
        "hidden_tabs": ["sleep", "bogus"],  # filter -> ["sleep"]
        "unknown_key": "ignored",
    })
    assert saved["units"] == "metric"
    assert saved["sync_interval_minutes"] == 240
    assert saved["baseline_window_days"] == 7
    assert saved["hidden_tabs"] == ["sleep"]
    assert "unknown_key" not in saved
    assert st.load_settings(p) == saved   # persisted + reloads identically


def test_save_merges_partial(tmp_path):
    p = tmp_path / "settings.json"
    st.save_settings(p, {"units": "imperial"})
    merged = st.save_settings(p, {"sync_interval_minutes": 60})
    assert merged["units"] == "imperial"        # preserved
    assert merged["sync_interval_minutes"] == 60


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{ not json")
    assert st.load_settings(p) == st.DEFAULTS


# --- API endpoints ---

def _client(tmp_path):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    app = create_app(p, client_factory=lambda: MagicMock(),
                     tokenstore=tmp_path / "garth")
    return app.test_client(), p


def test_settings_endpoints_roundtrip(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/api/settings").get_json()["units"] == "metric"
    r = client.post("/api/settings", json={"units": "imperial", "hidden_tabs": ["trends"]})
    body = r.get_json()
    assert body["units"] == "imperial" and body["hidden_tabs"] == ["trends"]
    assert client.get("/api/settings").get_json()["units"] == "imperial"


def test_switch_account_clears_data_and_tokens(tmp_path):
    client, p = _client(tmp_path)
    # seed a token + some data
    ts = tmp_path / "garth"; ts.mkdir(parents=True, exist_ok=True)
    (ts / "garmin_tokens.json").write_text("{}")
    m = {k: None for k in db.DAILY_FIELDS}; m["rhr"] = 50
    db.upsert_daily(p, "2026-06-22", m, recovery=60, strain=20)
    (tmp_path / "capabilities.json").write_text("{}")
    assert client.get("/api/auth/status").get_json()["authenticated"] is True

    assert client.post("/api/auth/switch-account").get_json() == {"status": "ok"}

    assert client.get("/api/auth/status").get_json()["authenticated"] is False  # tokens gone
    assert db.get_daily(p, "2026-06-22") is None                                 # rows cleared
    assert not (tmp_path / "capabilities.json").exists()                         # profile removed


def test_clear_all_data_empties_every_table(tmp_path):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    m = {k: None for k in db.DAILY_FIELDS}
    db.upsert_daily(p, "2026-06-22", m, None, None)
    db.upsert_activities(p, [{"activity_id": 1, "date": "2026-06-22", "type": "running",
                              "duration_s": 1, "avg_hr": 1, "max_hr": 1,
                              "training_load": 1, "aerobic_te": 1, "anaerobic_te": 1}])
    db.write_sync_log(p, "ok", "synced", {})
    db.clear_all_data(p)
    assert db.get_daily(p, "2026-06-22") is None
    assert db.get_recent_activities(p, 10) == []
    assert db.get_last_sync(p) is None
