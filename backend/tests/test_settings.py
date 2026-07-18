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


# --- v4.3: new option validation ---

def test_v43_general_options_validate(tmp_path):
    p = tmp_path / "settings.json"
    s = st.save_settings(p, {
        "accent_color": "#ff8800", "theme": "midnight", "density": "compact",
        "week_start": "sun", "weather_units": "f", "clock": "12",
    })
    assert s["accent_color"] == "#ff8800"
    assert s["theme"] == "midnight"
    assert s["density"] == "compact"
    assert (s["week_start"], s["weather_units"], s["clock"]) == ("sun", "f", "12")
    # invalid values fall back
    bad = st.save_settings(p, {"accent_color": "green", "theme": "neon",
                               "density": "cozy", "clock": "13"})
    assert bad["accent_color"] == "#22c55e"
    assert bad["theme"] == "dark"
    assert bad["density"] == "comfortable"
    assert bad["clock"] == "24"


def test_v43_hrv_weight_and_bands(tmp_path):
    p = tmp_path / "settings.json"
    s = st.save_settings(p, {"hrv_weight": 0.55, "recovery_green": 70, "recovery_amber": 40})
    assert s["hrv_weight"] == 0.55
    assert (s["recovery_green"], s["recovery_amber"]) == (70, 40)
    # clamp: weight out of range; amber forced below green
    c = st.save_settings(p, {"hrv_weight": 5, "recovery_green": 60, "recovery_amber": 80})
    assert c["hrv_weight"] == 1.0
    assert c["recovery_green"] == 60 and c["recovery_amber"] < 60


def test_v43_coach_and_sync_options(tmp_path):
    p = tmp_path / "settings.json"
    s = st.save_settings(p, {"coach_tone": "tough", "coach_auto_brief": True,
                             "coach_target_pref": "hr", "coach_warmup_default_s": 9999,
                             "coach_budget_reminder": 5, "sync_paused": True,
                             "sync_on_launch": False})
    assert s["coach_tone"] == "tough"
    assert s["coach_auto_brief"] is True
    assert s["coach_target_pref"] == "hr"
    assert s["coach_warmup_default_s"] == 1800     # clamped
    assert s["coach_budget_reminder"] == 5
    assert s["sync_paused"] is True and s["sync_on_launch"] is False
    assert st.save_settings(p, {"coach_tone": "mean"})["coach_tone"] == "balanced"


# --- v4.2: custom tabs + tab order ---

def test_custom_tabs_sanitized_and_capped(tmp_path):
    p = tmp_path / "settings.json"
    s = st.save_settings(p, {"custom_tabs": [
        {"id": "c1", "name": "Morning", "icon": "🌅",
         "layout": [{"i": "recovery", "x": 0, "y": 0, "w": 2, "h": 3},
                    {"i": "", "x": 0, "y": 1}]},          # blank widget id dropped
        {"id": "c1", "name": "dup"},                      # duplicate id dropped
        {"id": "", "name": "no id"},                      # missing id dropped
        {"id": "sleep", "name": "collides with builtin"}, # reserved id dropped
        "not a dict",
    ]})
    assert [t["id"] for t in s["custom_tabs"]] == ["c1"]
    tab = s["custom_tabs"][0]
    assert tab["name"] == "Morning" and tab["icon"] == "🌅"
    assert [w["i"] for w in tab["layout"]] == ["recovery"]   # blank pruned


def test_config_backup_and_restore_roundtrip(tmp_path):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    app = create_app(p, client_factory=lambda: MagicMock(), tokenstore=tmp_path / "g")
    c = app.test_client()
    # set some config + a journal entry, then back it up
    c.post("/api/settings", json={"accent_color": "#ff8800", "coach_tone": "tough",
                                  "anthropic_api_key": "sk-secret"})
    db.upsert_journal(p, "2026-07-15", {"late_caffeine": True}, "note")
    backup = c.get("/api/config-backup").get_json()
    assert backup["settings"]["accent_color"] == "#ff8800"
    assert "anthropic_api_key" not in backup["settings"]     # key never exported
    assert any(j["date"] == "2026-07-15" for j in backup["journal"])
    # wipe to defaults, then restore
    c.post("/api/settings", json={"accent_color": "#22c55e", "coach_tone": "balanced"})
    r = c.post("/api/config-restore", json=backup).get_json()
    assert r["ok"] and r["journal_restored"] >= 1
    now = c.get("/api/settings").get_json()
    assert now["accent_color"] == "#ff8800" and now["coach_tone"] == "tough"
    assert now["anthropic_api_key"] == "sk-secret"           # existing key preserved


def test_custom_tab_grid_coords_clamped(tmp_path):
    p = tmp_path / "settings.json"
    s = st.save_settings(p, {"custom_tabs": [
        {"id": "c1", "layout": [{"i": "x", "x": 99, "y": -5, "w": 99, "h": 0}]}]})
    w = s["custom_tabs"][0]["layout"][0]
    assert w["x"] == st.GRID_COLS - 1 and w["y"] == 0
    assert w["w"] == st.GRID_COLS and w["h"] == 1


def test_tab_order_and_hidden_allow_custom_ids_drop_unknown(tmp_path):
    p = tmp_path / "settings.json"
    s = st.save_settings(p, {
        "custom_tabs": [{"id": "c1", "name": "Mine"}],
        "tab_order": ["overview", "c1", "bogus", "overview", "coach"],  # dedup + prune
        "hidden_tabs": ["trends", "c1", "ghost"],
    })
    assert s["tab_order"] == ["overview", "c1", "coach"]
    assert s["hidden_tabs"] == ["trends", "c1"]


def test_tab_order_keeps_every_builtin_tab(tmp_path):
    # Regression: "today" was missing from TAB_KEYS, so validation silently
    # stripped it from tab_order and the Today tab jumped to the end of the bar.
    p = tmp_path / "settings.json"
    full = ["overview", "today", "sleep", "training", "activities", "trends", "coach"]
    s = st.save_settings(p, {"tab_order": full, "hidden_tabs": ["today"]})
    assert s["tab_order"] == full
    assert s["hidden_tabs"] == ["today"]


def test_custom_tabs_count_capped(tmp_path):
    p = tmp_path / "settings.json"
    many = [{"id": f"c{i}", "name": str(i)} for i in range(st.MAX_CUSTOM_TABS + 5)]
    s = st.save_settings(p, {"custom_tabs": many})
    assert len(s["custom_tabs"]) == st.MAX_CUSTOM_TABS


def test_bom_prefixed_file_still_parses(tmp_path):
    # A UTF-8 BOM (e.g. from PowerShell Out-File -Encoding utf8) must NOT make
    # the file unparseable — otherwise a save would wipe real values.
    p = tmp_path / "settings.json"
    body = '{"phone_access": true, "access_pin": "2262", "anthropic_api_key": "sk-x"}'
    p.write_bytes(b"\xef\xbb\xbf" + body.encode("utf-8"))
    s = st.load_settings(p)
    assert s["phone_access"] is True
    assert s["access_pin"] == "2262"
    assert s["anthropic_api_key"] == "sk-x"
    # And a subsequent save preserves them rather than resetting to defaults.
    merged = st.save_settings(p, {"units": "imperial"})
    assert merged["access_pin"] == "2262" and merged["anthropic_api_key"] == "sk-x"


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
