# v5.0 D1: morning sync notification payload.
from unittest.mock import MagicMock

import backend.db as db
from backend.api import create_app
from backend.notify import build_sync_notification

BASE = {"morning_notification": True, "recovery_green": 67, "recovery_amber": 34}


def _db(tmp_path, recovery=72):
    p = tmp_path / "t.db"
    db.init_db(p)
    m = {k: None for k in db.DAILY_FIELDS}
    m["hrv_last_night"] = 60  # qualifies the row as a primary day
    db.upsert_daily(p, "2026-07-18", m, recovery=recovery, strain=10)
    return p


def test_notification_payload_has_score_band_and_date(tmp_path):
    p = _db(tmp_path, recovery=72)
    n = build_sync_notification(p, BASE)
    assert n == {"date": "2026-07-18", "recovery_score": 72, "band": "green",
                 "line": None, "planned": None}


def test_notification_band_uses_custom_cutoffs(tmp_path):
    p = _db(tmp_path, recovery=72)
    n = build_sync_notification(p, {**BASE, "recovery_green": 80})
    assert n["band"] == "yellow"


def test_notification_none_when_disabled(tmp_path):
    p = _db(tmp_path)
    assert build_sync_notification(p, {**BASE, "morning_notification": False}) is None


def test_notification_none_without_recovery_score(tmp_path):
    # No fabrication: nothing to announce until a score exists.
    p = _db(tmp_path, recovery=None)
    assert build_sync_notification(p, BASE) is None


def test_notification_line_is_briefs_first_sentence(tmp_path):
    p = _db(tmp_path)
    db.upsert_coach_brief(p, "2026-07-18",
                          "Solid green day — HRV is back above baseline. "
                          "Consider intervals this afternoon.", None, [])
    n = build_sync_notification(p, BASE)
    assert n["line"] == "Solid green day — HRV is back above baseline."


def test_notification_line_truncates_long_first_sentence(tmp_path):
    p = _db(tmp_path)
    db.upsert_coach_brief(p, "2026-07-18", "x" * 400, None, [])
    n = build_sync_notification(p, BASE)
    assert len(n["line"]) <= 141 and n["line"].endswith("…")


def test_notify_endpoint_serves_payload(tmp_path):
    p = _db(tmp_path)
    app = create_app(p, client_factory=lambda: MagicMock())
    body = app.test_client().get("/api/notify/last-sync").get_json()
    assert body["notification"]["recovery_score"] == 72
    assert body["notification"]["band"] == "green"


def test_notify_endpoint_null_when_disabled(tmp_path):
    import backend.settings as st
    p = _db(tmp_path)
    st.save_settings(p.parent / "settings.json", {"morning_notification": False})
    app = create_app(p, client_factory=lambda: MagicMock())
    body = app.test_client().get("/api/notify/last-sync").get_json()
    assert body["notification"] is None


def test_morning_notification_defaults_on():
    import backend.settings as st
    assert st.DEFAULTS["morning_notification"] is True


def test_notification_includes_planned_session(tmp_path):
    p = _db(tmp_path)
    db.save_training_plan(p, {"name": "10k", "date": "2026-09-01",
                              "distance_km": 10, "goal_time_s": None},
                          [{"index": 1, "start": "2026-07-13", "focus": "base",
                            "target_km": 30, "long_run_km": 10, "summary": "s",
                            "workouts": [{"name": "Tempo 5k", "suggested_date": "2026-07-18",
                                          "rationale": "r", "steps": []}]}], None)
    n = build_sync_notification(p, BASE)
    assert n["planned"] == "Tempo 5k"


def test_notification_planned_none_without_plan(tmp_path):
    n = build_sync_notification(_db(tmp_path), BASE)
    assert n["planned"] is None
