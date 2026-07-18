"""v4.0: AI coach — context builder, brief caching, chat, workout conversion,
and the Garmin push path. Claude and Garmin are mocked throughout."""
import json
from unittest.mock import MagicMock, patch

import backend.db as db
import backend.coach as coach
import backend.workouts as wk
from backend.api import create_app


def _seed(p):
    db.init_db(p)
    metrics = {f: None for f in db.DAILY_FIELDS}
    metrics.update({"hrv_last_night": 60, "rhr": 44, "sleep_score": 82,
                    "recovery_time_min": 900, "steps": 9000})
    db.upsert_daily(p, "2026-07-14", metrics, 55, 40)
    db.upsert_daily(p, "2026-07-15", metrics, 62, 30)
    db.upsert_activities(p, [{"activity_id": 1, "date": "2026-07-15",
                              "type": "running", "duration_s": 3000,
                              "avg_hr": 150, "max_hr": 170, "training_load": 90,
                              "aerobic_te": 3.1, "anaerobic_te": 0.4}])
    db.upsert_perf(p, "2026-07-15", {"vo2max": 54, "lt_hr": 180, "lt_power": 320,
                                     "race_10k": 2550})
    db.upsert_journal(p, "2026-07-15", {"late_caffeine": True}, "slept badly")


# --- context builder ---

def test_context_contains_real_data_and_no_credentials(tmp_path):
    p = tmp_path / "d.db"
    _seed(p)
    ctx = coach.build_context(p)
    assert ctx["days"][-1]["recovery_score"] == 62
    assert ctx["performance"]["lt_hr"] == 180
    assert ctx["recent_activities"][0]["type"] == "running"
    assert ctx["journal"][0]["tags"] == ["late_caffeine"]
    blob = json.dumps(ctx).lower()
    for banned in ("token", "password", "api_key", "email", "pin"):
        assert banned not in blob


def test_context_omits_null_fields(tmp_path):
    p = tmp_path / "d.db"
    _seed(p)
    ctx = coach.build_context(p)
    assert "spo2_avg" not in ctx["days"][-1]   # was never set -> omitted


# --- brief caching ---

def _settings():
    return {"coach_enabled": True, "anthropic_api_key": "k",
            "coach_model": "claude-opus-4-8"}


def test_daily_brief_caches_per_date(tmp_path):
    p = tmp_path / "d.db"
    _seed(p)
    with patch.object(coach, "_call_claude",
                      return_value={"reply": "Take it easy today.", "workout": None}) as m:
        b1 = coach.daily_brief(p, _settings(), "2026-07-15")
        b2 = coach.daily_brief(p, _settings(), "2026-07-15")
    assert m.call_count == 1                     # second hit came from cache
    assert b1["text"] == "Take it easy today."
    assert b2["cached"] is True


def test_daily_brief_force_regenerates(tmp_path):
    p = tmp_path / "d.db"
    _seed(p)
    with patch.object(coach, "_call_claude",
                      return_value={"reply": "x", "workout": None}) as m:
        coach.daily_brief(p, _settings(), "2026-07-15")
        coach.daily_brief(p, _settings(), "2026-07-15", force=True)
    assert m.call_count == 2


# --- chat ---

def test_chat_persists_history_and_returns_workout(tmp_path):
    p = tmp_path / "d.db"
    _seed(p)
    workout = {"name": "Tempo 4x5", "suggested_date": "2026-07-16",
               "rationale": "tolerance headroom", "steps": []}
    with patch.object(coach, "_call_claude",
                      return_value={"reply": "Here's a tempo.", "workout": workout}):
        out = coach.chat(p, _settings(), "give me a workout", "2026-07-15")
    assert out["workout"]["name"] == "Tempo 4x5"
    hist = db.get_coach_chat(p, 10)
    assert [h["role"] for h in hist] == ["user", "assistant"]
    assert hist[1]["workout"]["name"] == "Tempo 4x5"


def test_chat_sends_context_and_history(tmp_path):
    p = tmp_path / "d.db"
    _seed(p)
    db.add_coach_chat(p, "user", "earlier question", None)
    db.add_coach_chat(p, "assistant", "earlier answer", None)
    captured = {}
    def fake(settings, messages):
        captured["messages"] = messages
        return {"reply": "ok", "workout": None}
    with patch.object(coach, "_call_claude", side_effect=fake):
        coach.chat(p, _settings(), "and now?", "2026-07-15")
    msgs = captured["messages"]
    assert "Athlete data (JSON)" in msgs[0]["content"]
    assert any("earlier question" in m["content"] for m in msgs)
    assert msgs[-1]["content"] == "and now?"


# --- v4.1: escape-artifact sanitizer + highlights ---

def test_clean_text_fixes_escape_artifacts():
    raw = "load is up \\u2014 two hard days\\nRest tomorrow \\u2013 easy jog"
    assert coach.clean_text(raw) == "load is up — two hard days\nRest tomorrow – easy jog"


def test_clean_text_leaves_normal_text_alone():
    s = "Recovery **88** — nice rebound.\n\n- easy run\n- sleep early"
    assert coach.clean_text(s) == s


def test_call_claude_sanitizes_and_defaults_highlights(tmp_path):
    import json as _json
    fake_resp = MagicMock()
    fake_resp.stop_reason = "end_turn"
    block = MagicMock(); block.type = "text"
    block.text = _json.dumps({"reply": "ACWR high \\u2014 back off", "workout": None})
    fake_resp.content = [block]
    with patch("anthropic.Anthropic") as A:
        A.return_value.messages.create.return_value = fake_resp
        out = coach._call_claude(_settings(), [{"role": "user", "content": "x"}])
    assert out["reply"] == "ACWR high — back off"
    assert out["highlights"] == []


def test_brief_and_chat_persist_highlights(tmp_path):
    p = tmp_path / "d.db"
    _seed(p)
    hl = [{"label": "ACWR", "value": "1.4", "tone": "warn"},
          {"label": "Recovery", "value": "88", "tone": "good"}]
    with patch.object(coach, "_call_claude",
                      return_value={"reply": "r", "workout": None, "highlights": hl}):
        brief = coach.daily_brief(p, _settings(), "2026-07-15")
        coach.chat(p, _settings(), "why?", "2026-07-15")
    assert brief["highlights"][0]["label"] == "ACWR"
    assert db.get_coach_brief(p, "2026-07-15")["highlights"] == hl
    assert db.get_coach_chat(p, 10)[-1]["highlights"] == hl


def test_default_model_is_sonnet5():
    from backend.settings import DEFAULTS
    assert DEFAULTS["coach_model"] == "claude-sonnet-5"


# --- v4.3: coach tone + workout-default addendum ---

def test_tone_addendum_varies_by_setting():
    assert coach._tone_addendum({"coach_tone": "balanced"}) == ""
    tough = coach._tone_addendum({"coach_tone": "tough"})
    assert "no-excuses" in tough.lower()
    concise = coach._tone_addendum({"coach_tone": "concise"})
    assert "brief" in concise.lower()


def test_tone_addendum_includes_workout_defaults():
    s = coach._tone_addendum({"coach_tone": "balanced",
                              "coach_warmup_default_s": 900, "coach_target_pref": "hr"})
    assert "15 min" in s          # 900s -> 15 min
    assert "heart-rate" in s.lower()


def test_call_claude_appends_tone_system_block():
    import json as _json
    captured = {}
    fake = MagicMock()
    fake.stop_reason = "end_turn"
    blk = MagicMock(); blk.type = "text"
    blk.text = _json.dumps({"reply": "ok", "workout": None})
    fake.content = [blk]
    with patch("anthropic.Anthropic") as A:
        A.return_value.messages.create.side_effect = lambda **kw: captured.update(kw) or fake
        coach._call_claude({**_settings(), "coach_tone": "tough"},
                           [{"role": "user", "content": "x"}])
    # base cached prompt + tone block
    assert len(captured["system"]) == 2
    assert "no-excuses" in captured["system"][1]["text"].lower()


# --- workout design -> Garmin conversion ---

DESIGN = {
    "name": "6x800 @ 10K pace",
    "suggested_date": "2026-07-16",
    "rationale": "sharpen for the 10K",
    "steps": [
        {"kind": "warmup", "duration_type": "time", "duration_value": 600,
         "target_type": "heart_rate", "target_min": 120, "target_max": 145,
         "description": "easy jog"},
        {"kind": "repeat", "count": 6, "steps": [
            {"kind": "interval", "duration_type": "distance", "duration_value": 800,
             "target_type": "pace", "target_min": 235, "target_max": 250,
             "description": "10K effort"},
            {"kind": "recovery", "duration_type": "time", "duration_value": 90,
             "target_type": "none", "target_min": None, "target_max": None,
             "description": "walk/jog"},
        ]},
        {"kind": "cooldown", "duration_type": "time", "duration_value": 300,
         "target_type": "none", "target_min": None, "target_max": None,
         "description": ""},
    ],
}


def test_design_to_garmin_structure():
    w = wk.design_to_garmin(DESIGN)
    payload = w.model_dump() if hasattr(w, "model_dump") else w.dict()
    assert payload["workoutName"] == "6x800 @ 10K pace"
    seg = payload["workoutSegments"][0]
    assert seg["sportType"]["sportTypeKey"] == "running"
    steps = seg["workoutSteps"]
    assert steps[0]["stepType"]["stepTypeKey"] == "warmup"
    # HR target: custom bpm range low->high
    assert steps[0]["targetType"]["workoutTargetTypeKey"] == "heart.rate.zone"
    assert steps[0]["targetValueOne"] == 120.0
    assert steps[0]["targetValueTwo"] == 145.0
    # repeat group with 6 iterations and two children
    rep = steps[1]
    assert rep["numberOfIterations"] == 6
    assert len(rep["workoutSteps"]) == 2
    # pace target converts sec/km -> m/s, valueOne = slowest speed
    iv = rep["workoutSteps"][0]
    assert iv["endCondition"]["conditionTypeKey"] == "distance"
    assert iv["endConditionValue"] == 800.0
    assert abs(iv["targetValueOne"] - 1000 / 250) < 1e-6    # slowest (250 s/km)
    assert abs(iv["targetValueTwo"] - 1000 / 235) < 1e-6    # fastest (235 s/km)
    assert iv["targetValueOne"] < iv["targetValueTwo"]


def test_design_estimated_duration():
    w = wk.design_to_garmin(DESIGN)
    payload = w.model_dump() if hasattr(w, "model_dump") else w.dict()
    # 600 + 6*(800*0.36 + 90) + 300 = 3168
    assert payload["estimatedDurationInSecs"] == 3168


def test_pace_to_mps():
    assert abs(wk.pace_to_mps(240) - 4.16667) < 1e-4


# --- push path through the API ---

def _client_with_garmin(tmp_path, garmin):
    p = tmp_path / "dashboard.db"
    _seed(p)
    app = create_app(p, client_factory=lambda: garmin, tokenstore=tmp_path / "g")
    return app.test_client(), p


def test_workout_send_uploads_and_schedules(tmp_path):
    garmin = MagicMock()
    garmin.push_running_workout.return_value = {
        "workout_id": 999, "schedule": {"workoutScheduleId": 55}}
    client, p = _client_with_garmin(tmp_path, garmin)
    resp = client.post("/api/coach/workout/send",
                       json={"design": DESIGN, "date": "2026-07-16"})
    body = resp.get_json()
    assert body["ok"] is True and body["garmin_workout_id"] == 999
    garmin.login.assert_called_once()
    (workout_arg, date_arg) = garmin.push_running_workout.call_args[0]
    assert date_arg == "2026-07-16"
    stored = db.list_coach_workouts(p)[0]
    assert stored["status"] == "scheduled"
    assert stored["garmin_workout_id"] == 999


def test_workout_send_rejects_bad_design(tmp_path):
    client, _ = _client_with_garmin(tmp_path, MagicMock())
    assert client.post("/api/coach/workout/send",
                       json={"design": {"name": "x"}}).status_code == 400
    assert client.post("/api/coach/workout/send",
                       json={"design": DESIGN, "date": "16-07-2026"}).status_code == 400


def test_workout_send_reports_garmin_error_without_crash(tmp_path):
    garmin = MagicMock()
    garmin.push_running_workout.side_effect = RuntimeError("boom")
    client, p = _client_with_garmin(tmp_path, garmin)
    body = client.post("/api/coach/workout/send",
                       json={"design": DESIGN, "date": "2026-07-16"}).get_json()
    assert body["error"] == "RuntimeError"
    assert db.list_coach_workouts(p) == []      # nothing recorded on failure


def test_workout_delete_removes_from_garmin(tmp_path):
    garmin = MagicMock()
    garmin.push_running_workout.return_value = {
        "workout_id": 999, "schedule": {"workoutScheduleId": 55}}
    client, p = _client_with_garmin(tmp_path, garmin)
    row = client.post("/api/coach/workout/send",
                      json={"design": DESIGN, "date": "2026-07-16"}).get_json()
    resp = client.delete(f"/api/coach/workout/{row['id']}")
    assert resp.get_json()["ok"] is True
    garmin.remove_workout.assert_called_once_with(999, 55)
    assert db.get_coach_workout(p, row["id"])["status"] == "removed"


# --- endpoints when not configured ---

def test_coach_endpoints_report_not_configured(tmp_path):
    client, _ = _client_with_garmin(tmp_path, MagicMock())
    assert client.get("/api/coach/brief").get_json()["error"] == "not_configured"
    assert client.post("/api/coach/chat", json={"message": "hi"}).get_json()[
        "error"] == "not_configured"
    st = client.get("/api/coach/status").get_json()
    assert st["configured"] is False


def test_coach_status_configured(tmp_path):
    p = tmp_path / "dashboard.db"
    _seed(p)
    (tmp_path / "settings.json").write_text(json.dumps(
        {"coach_enabled": True, "anthropic_api_key": "sk-test"}))
    app = create_app(p, client_factory=lambda: MagicMock(), tokenstore=tmp_path / "g")
    st = app.test_client().get("/api/coach/status").get_json()
    assert st["configured"] is True and st["model"] == "claude-sonnet-5"
