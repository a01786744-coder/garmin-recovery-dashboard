"""Local Flask API serving cached SQLite data + manual/scheduled sync + auth."""
import os
import re
import hmac
import threading
import logging
from pathlib import Path

from flask import Flask, jsonify, request, Response, send_from_directory, abort

import backend.config as cfg
import backend.db as db
from backend import recovery as rec
from backend.sync import run_sync, sync_activity_detail, rescore_history

log = logging.getLogger("api")


def resolve_host(settings):
    """Which interface to bind: env override, else all interfaces (LAN +
    Tailscale) when phone access is on, else loopback only."""
    env = os.environ.get("GARMIN_DASH_HOST")
    if env:
        return env
    return "0.0.0.0" if settings.get("phone_access") else "127.0.0.1"


class RedactingFilter(logging.Filter):
    """Defense-in-depth log scrubbing: credentials and tokens are never logged
    intentionally, but this strips anything credential/token-shaped from every
    log line before it reaches the file."""
    _patterns = [
        re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),                      # emails
        re.compile(r"(?i)(password|token|authorization)[\"']?\s*[:=]\s*\S+"),
        re.compile(r"[A-Za-z0-9_\-]{40,}"),                          # long token-ish strings
    ]

    def filter(self, record):
        msg = record.getMessage()
        for p in self._patterns:
            msg = p.sub("[REDACTED]", msg)
        record.msg = msg
        record.args = ()
        return True


def _has_tokens(tokenstore):
    """Authenticated iff the token store holds at least one token file. Cheap
    (no network); expired tokens still count as 'have an account' — a failed
    refresh during sync is what triggers a re-login prompt."""
    p = Path(tokenstore)
    return p.is_dir() and any(f.is_file() for f in p.iterdir())


def _clear_tokens(tokenstore):
    """Remove stored token files (logout). Leaves the directory in place."""
    p = Path(tokenstore)
    if not p.is_dir():
        return
    for f in p.iterdir():
        if f.is_file():
            try:
                f.unlink()
            except OSError:
                pass


def create_app(db_path=cfg.DB_PATH, client_factory=None,
               tokenstore=cfg.TOKENSTORE_DIR, auth_client_factory=None,
               static_dir=None):
    app = Flask(__name__, static_folder=None)
    static_dir = static_dir or cfg.resolve_static_dir()
    db.init_db(db_path)
    # Holds the in-progress GarminClient between /auth/login and /auth/mfa
    # (single-user local app, so one pending login at a time).
    pending = {}

    @app.after_request
    def _local_cors(resp):
        # The dashboard runs from a file:// origin inside Electron and fetches
        # this API cross-origin; without an Access-Control-Allow-Origin header
        # Chromium blocks the renderer from reading the responses. Safe here:
        # the server only ever binds to 127.0.0.1 (never a public interface).
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    @app.before_request
    def _gate_non_loopback():
        # The desktop app talks to the API over loopback and needs no PIN. Any
        # other remote address (a phone over LAN/Tailscale) must present the
        # configured access PIN on /api/*; static assets load freely so the phone
        # can render the PIN prompt. An empty configured PIN denies all remotes.
        if not request.path.startswith("/api/"):
            return None
        if request.remote_addr in ("127.0.0.1", "::1", None):
            return None
        from backend import settings as st
        pin = st.load_settings(Path(db_path).parent / "settings.json")["access_pin"]
        supplied = request.headers.get("X-Access-Pin", "")
        if not pin or not hmac.compare_digest(supplied, pin):
            return jsonify({"error": "pin_required"}), 401
        return None

    def _trends(days):
        rows = db.get_trends(db_path, days)
        return {
            "days": rows,
            "hrv": [{"date": r["date"], "value": r["hrv_last_night"]} for r in rows],
            "rhr": [{"date": r["date"], "value": r["rhr"]} for r in rows],
            "perf": db.get_perf_history(db_path, days),
        }

    @app.get("/api/today")
    def today():
        from backend import settings as st
        # Most recent day WITH data, not strictly the latest date — so an empty
        # "today" (before the watch syncs last night's sleep) shows yesterday's
        # data instead of a blank dashboard.
        metrics = db.get_primary_day(db_path)
        sync = db.get_last_sync(db_path)
        cfg = st.load_settings(Path(db_path).parent / "settings.json")
        window = cfg["baseline_window_days"]
        # Baseline progress for the Recovery gauge ("Baseline 3/4 days").
        need = rec.min_days_for_window(window)
        if metrics:
            hrv_hist = db.get_history_before(db_path, "hrv_last_night", metrics["date"], window)
            rhr_hist = db.get_history_before(db_path, "rhr", metrics["date"], window)
            have = min(sum(v is not None for v in hrv_hist),
                       sum(v is not None for v in rhr_hist))
            # "Why this score" payloads for the detail panels. Extras built by
            # the same helper the sync scorer uses, so they always agree.
            from backend.sync import recovery_extras, strain_zones
            recovery_explain = rec.recovery_explanation(
                metrics.get("hrv_last_night"), metrics.get("rhr"),
                hrv_hist, rhr_hist, min_days=need, hrv_weight=cfg["hrv_weight"],
                extras=recovery_extras(db_path, metrics["date"], metrics, window))
            day_acts = db.get_activities_on(db_path, metrics["date"])
            strain_explain = rec.strain_breakdown(
                day_acts, metrics, strain_zones(db_path, day_acts))
        else:
            have, recovery_explain, strain_explain = 0, None, None
        return jsonify({
            "baseline": {"have": have, "need": need},
            "recovery_explain": recovery_explain,
            "strain_explain": strain_explain,
            "metrics": metrics,
            "activities": db.get_recent_activities(db_path, 10),
            "perf": db.get_latest_perf(db_path),
            "records": db.get_personal_records(db_path),
            "sync": sync,
            "progress": {
                # Onboarding: the first full backfill fills history over time
                # (paced, 429-tolerant). "complete" once a sync finished without
                # a rate-limit interruption (run_sync sets status "ok" only then).
                "days_synced": db.count_daily(db_path),
                "target_days": window,
                "complete": (sync or {}).get("status") == "ok",
            },
        })

    @app.get("/api/activities")
    def activities_list():
        # Full recent history for the Activities tab (filters + weekly volume);
        # /api/today keeps its short list for the Overview.
        limit = min(max(int(request.args.get("limit", 100)), 1), 500)
        return jsonify({"activities": db.get_recent_activities(db_path, limit)})

    @app.get("/api/days")
    def days():
        # Dates that have data, for stepping back through history.
        return jsonify({"dates": db.get_dates(db_path)})

    @app.get("/api/day/<date>")
    def day(date):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            return jsonify({"error": "bad date"}), 400
        # Same day-shaped payload as /api/today, for an arbitrary past date.
        # perf/records/sync are global (not date-specific) so the views still work.
        return jsonify({
            "metrics": db.get_daily(db_path, date),
            "activities": db.get_activities_on(db_path, date),
            "perf": db.get_latest_perf(db_path),
            "records": db.get_personal_records(db_path),
            "sync": db.get_last_sync(db_path),
        })

    @app.get("/api/journal/<date>")
    def get_journal_route(date):
        from backend.insights import JOURNAL_TAGS
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            return jsonify({"error": "bad date"}), 400
        saved = db.get_journal(db_path, date)
        if saved:
            tags = {t: bool(saved["tags"].get(t)) for t in JOURNAL_TAGS}
            return jsonify({"date": date, "tags": tags, "note": saved["note"], "saved": True})
        # Sticky prefill: default to the most recent saved entry's answers so
        # the user only flips what changed. Notes never carry forward.
        prev = db.get_journal_before(db_path, date)
        tags = {t: bool((prev or {}).get("tags", {}).get(t)) for t in JOURNAL_TAGS}
        return jsonify({"date": date, "tags": tags, "note": "", "saved": False})

    @app.post("/api/journal/<date>")
    def post_journal_route(date):
        from backend.insights import JOURNAL_TAGS
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            return jsonify({"error": "bad date"}), 400
        data = request.get_json(silent=True) or {}
        tags = {t: bool((data.get("tags") or {}).get(t)) for t in JOURNAL_TAGS}
        note = str(data.get("note") or "")
        db.upsert_journal(db_path, date, tags, note)
        return jsonify({"date": date, "tags": tags, "note": note, "saved": True})

    @app.get("/api/insights")
    def insights():
        from backend import insights as ins
        from backend import forecast as fc
        from backend import settings as st
        daily = db.get_trends(db_path, 90)
        acts = db.get_recent_activities(db_path, 50)
        primary = db.get_primary_day(db_path) or {}
        scfg = st.load_settings(Path(db_path).parent / "settings.json")
        return jsonify({
            "forecast": fc.forecast_recovery(daily, scfg["recovery_green"],
                                             scfg["recovery_amber"]),
            "weekly": ins.weekly_recap(daily, acts),
            "streaks": ins.streaks(daily, acts),
            "insights": ins.auto_insights(daily),
            "correlations": (ins.correlations(daily)
                             + ins.journal_correlations(daily, db.get_journal_range(db_path, 90))),
            "recap": {
                "morning": ins.morning_summary(primary, daily),
                "afternoon": ins.afternoon_summary(primary, daily),
            },
            "week_extremes": ins.week_extremes(daily),
            "sleep_debt": ins.sleep_debt(daily),
        })

    @app.get("/api/trends")
    def trends():
        days = int(request.args.get("days", 30))
        return jsonify(_trends(days))

    @app.get("/api/intraday")
    def intraday():
        date = request.args.get("date")
        metric = request.args.get("metric")
        return jsonify({
            "date": date, "metric": metric,
            "series": db.get_intraday(db_path, date, metric) if date and metric else None,
        })

    @app.get("/api/performance")
    def performance():
        return jsonify({
            "perf": db.get_latest_perf(db_path),
            "records": db.get_personal_records(db_path),
        })

    @app.get("/api/activity/<int:activity_id>")
    def activity(activity_id):
        detail = db.get_activity_detail(db_path, activity_id)
        if detail is None and client_factory is not None:
            client = client_factory()
            try:
                client.login()
                detail = sync_activity_detail(client, db_path, activity_id)
            except Exception as e:  # never crash; return whatever we have
                log.warning("activity detail sync failed: %s", type(e).__name__)
        return jsonify(detail or {})

    @app.get("/api/capabilities")
    def capabilities():
        from backend import capabilities as caps
        prof = caps.load_profile(Path(db_path).parent / "capabilities.json")
        return jsonify(prof or caps.default_profile())

    # ---- v4.0: AI coach ----------------------------------------------------

    def _coach_settings():
        from backend import settings as st
        return st.load_settings(Path(db_path).parent / "settings.json")

    def _today_str():
        import datetime as _dt
        return _dt.date.today().isoformat()

    @app.get("/api/coach/status")
    def coach_status():
        from backend import coach
        s = _coach_settings()
        return jsonify({"enabled": bool(s.get("coach_enabled")),
                        "configured": coach.is_configured(s),
                        "model": s.get("coach_model")})

    @app.get("/api/coach/brief")
    def coach_brief():
        from backend import coach
        s = _coach_settings()
        if not coach.is_configured(s):
            return jsonify({"error": "not_configured"}), 200
        force = request.args.get("force") == "1"
        try:
            return jsonify(coach.daily_brief(db_path, s, _today_str(), force=force))
        except Exception as e:
            log.warning("coach brief failed: %s", type(e).__name__)
            return jsonify({"error": type(e).__name__}), 200

    @app.get("/api/coach/chat")
    def coach_chat_history():
        return jsonify({"messages": db.get_coach_chat(db_path, 50)})

    @app.post("/api/coach/chat")
    def coach_chat():
        from backend import coach
        s = _coach_settings()
        if not coach.is_configured(s):
            return jsonify({"error": "not_configured"}), 200
        message = str((request.get_json(silent=True) or {}).get("message") or "").strip()
        if not message:
            return jsonify({"error": "empty message"}), 400
        try:
            return jsonify(coach.chat(db_path, s, message, _today_str()))
        except Exception as e:
            log.warning("coach chat failed: %s", type(e).__name__)
            return jsonify({"error": type(e).__name__}), 200

    @app.delete("/api/coach/chat")
    def coach_chat_clear():
        db.clear_coach_chat(db_path)
        return jsonify({"ok": True})

    @app.get("/api/coach/workouts")
    def coach_workouts():
        return jsonify({"workouts": db.list_coach_workouts(db_path)})

    @app.post("/api/coach/workout/send")
    def coach_workout_send():
        # The ONLY write to the user's Garmin account. Reached exclusively via
        # the explicit "Send to watch" confirmation in the UI.
        from backend import workouts as wk
        body = request.get_json(silent=True) or {}
        design, date = body.get("design"), body.get("date")
        if not design or not isinstance(design.get("steps"), list):
            return jsonify({"error": "invalid workout design"}), 400
        if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)):
            return jsonify({"error": "bad date"}), 400
        if client_factory is None:
            return jsonify({"error": "no client"}), 503
        client = client_factory()
        try:
            client.login()
            result = client.push_running_workout(wk.design_to_garmin(design), date)
        except Exception as e:
            log.warning("workout push failed: %s", type(e).__name__)
            return jsonify({"error": type(e).__name__}), 200
        row_id = db.add_coach_workout(
            db_path, design.get("name") or "Coach workout", date, design,
            result.get("workout_id"), result.get("schedule"),
            "scheduled" if date else "uploaded")
        return jsonify({"ok": True, "id": row_id,
                        "garmin_workout_id": result.get("workout_id")})

    @app.delete("/api/coach/workout/<int:row_id>")
    def coach_workout_delete(row_id):
        w = db.get_coach_workout(db_path, row_id)
        if not w:
            return jsonify({"error": "not found"}), 404
        if client_factory is not None and w.get("garmin_workout_id"):
            client = client_factory()
            try:
                client.login()
                schedule_id = ((w.get("schedule") or {}).get("workoutScheduleId")
                               or (w.get("schedule") or {}).get("id"))
                client.remove_workout(w["garmin_workout_id"], schedule_id)
            except Exception as e:
                log.warning("workout removal failed: %s", type(e).__name__)
        db.update_coach_workout_status(db_path, row_id, "removed")
        return jsonify({"ok": True})

    # --- v5.0 C1: training plan ---

    @app.get("/api/coach/plan")
    def plan_get():
        return jsonify({"plan": db.get_training_plan(db_path)})

    @app.post("/api/coach/plan/generate")
    def plan_generate():
        from backend import coach, plan as pl
        s = _coach_settings()
        if not coach.is_configured(s):
            return jsonify({"error": "not_configured"}), 200
        body = request.get_json(silent=True) or {}
        try:
            out = pl.generate_plan(db_path, s, body.get("race"),
                                   today_str=_today_str())
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            log.warning("plan generate failed: %s", type(e).__name__)
            return jsonify({"error": type(e).__name__}), 200
        return jsonify({"plan": out})

    @app.post("/api/coach/plan/adapt")
    def plan_adapt():
        from backend import coach, plan as pl
        s = _coach_settings()
        if not coach.is_configured(s):
            return jsonify({"error": "not_configured"}), 200
        try:
            out = pl.adapt_plan(db_path, s, today_str=_today_str())
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            log.warning("plan adapt failed: %s", type(e).__name__)
            return jsonify({"error": type(e).__name__}), 200
        return jsonify({"plan": out})

    @app.post("/api/coach/plan/push-week")
    def plan_push_week():
        # Writes to the user's Garmin account through the same explicit-confirm
        # path as single workouts: the UI only calls this after "Send week to
        # watch → Confirm".
        from backend import workouts as wk
        body = request.get_json(silent=True) or {}
        stored = db.get_training_plan(db_path)
        if not stored:
            return jsonify({"error": "no plan"}), 404
        week = next((w for w in stored["weeks"]
                     if w.get("index") == body.get("week_index")), None)
        if not week:
            return jsonify({"error": "week not found"}), 404
        designs = week.get("workouts") or []
        if not designs:
            return jsonify({"error": "week has no detailed workouts yet — "
                                     "adapt the plan first"}), 400
        if client_factory is None:
            return jsonify({"error": "no client"}), 503
        client = client_factory()
        try:
            client.login()
            pushed = 0
            for design in designs:
                date = design.get("suggested_date")
                if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)):
                    date = None
                result = client.push_running_workout(wk.design_to_garmin(design), date)
                db.add_coach_workout(
                    db_path, design.get("name") or "Plan workout", date, design,
                    result.get("workout_id"), result.get("schedule"),
                    "scheduled" if date else "uploaded")
                pushed += 1
        except Exception as e:
            log.warning("plan week push failed: %s", type(e).__name__)
            return jsonify({"error": type(e).__name__, "pushed": pushed}), 200
        return jsonify({"ok": True, "pushed": pushed})

    @app.delete("/api/coach/plan")
    def plan_delete():
        db.delete_training_plan(db_path)
        return jsonify({"ok": True})

    @app.get("/api/sync-status")
    def sync_status():
        # data_dir included as a support diagnostic: makes "which database is
        # this app actually using?" answerable without forensics.
        body = db.get_last_sync(db_path) or {"status": "never"}
        body["data_dir"] = str(Path(db_path).parent)
        return jsonify(body)

    @app.get("/api/notify/last-sync")
    def notify_last_sync():
        # Electron main polls this and shows the morning notification once per
        # date; the backend only describes it (null = opted out / no data yet).
        from backend import settings as st
        from backend.notify import build_sync_notification
        cfg = st.load_settings(Path(db_path).parent / "settings.json")
        return jsonify({"notification": build_sync_notification(db_path, cfg)})

    @app.post("/api/sync")
    def manual_sync():
        if client_factory is None:
            return jsonify({"status": "error", "message": "no client"}), 503
        client = client_factory()
        try:
            client.login()
        except Exception as e:
            db.write_sync_log(db_path, "error", type(e).__name__, {})
            return jsonify({"status": "error", "message": type(e).__name__}), 200
        # Same window/weighting as the scheduled loop — a manual sync must not
        # rescore history under different params and diverge from stored scores.
        from backend import settings as st
        cfg = st.load_settings(Path(db_path).parent / "settings.json")
        result = run_sync(client, db_path, backfill_days=cfg["baseline_window_days"],
                          hrv_weight=cfg["hrv_weight"])
        _maybe_auto_brief(db_path, cfg)
        return jsonify(result)

    # --- Auth: in-app login / MFA / logout (no file editing by the user) ---

    @app.get("/api/auth/status")
    def auth_status():
        # needs_relogin: the stored token is dead (3 straight auth failures) —
        # the UI should prompt a fresh sign-in instead of failing silently.
        recent = db.last_sync_statuses(db_path, 3)
        needs_relogin = (len(recent) == 3 and
                         all(s == "error" and m == "GarminAuthError" for s, m in recent))
        return jsonify({"authenticated": _has_tokens(tokenstore),
                        "needs_relogin": needs_relogin})

    @app.post("/api/auth/login")
    def auth_login():
        from backend.garmin_client import (
            GarminClient, GarminMFARequired, GarminAuthError,
            GarminRateLimitError, GarminConnectionError,
        )
        data = request.get_json(silent=True) or {}
        email, password = data.get("email"), data.get("password")
        if not email or not password:
            return jsonify({"status": "error", "message": "missing_credentials"}), 400
        make = auth_client_factory or (lambda e, p, ts: GarminClient(e, p, ts))
        client = make(email, password, tokenstore)
        try:
            client.login()  # persists tokens on success
        except GarminMFARequired as e:
            pending["client"] = client
            pending["state"] = e.client_state
            return jsonify({"status": "mfa_required"})
        except GarminAuthError:
            return jsonify({"status": "error", "message": "authentication_failed"})
        except GarminRateLimitError:
            return jsonify({"status": "error", "message": "rate_limited"})
        except GarminConnectionError:
            return jsonify({"status": "error", "message": "connection_error"})
        # Success: only tokens are persisted; drop the client (and its password
        # reference) from memory now that we no longer need credentials.
        pending.clear()
        del client
        return jsonify({"status": "ok"})

    @app.post("/api/auth/mfa")
    def auth_mfa():
        from backend.garmin_client import GarminAuthError
        data = request.get_json(silent=True) or {}
        code = data.get("code")
        client = pending.get("client")
        if not client or not code:
            return jsonify({"status": "error", "message": "no_pending_login"}), 400
        try:
            client.complete_mfa(pending.get("state"), code)  # persists tokens
        except GarminAuthError:
            # keep pending so the user can re-enter the code
            return jsonify({"status": "error", "message": "mfa_failed"})
        pending.clear()
        return jsonify({"status": "ok"})

    @app.post("/api/auth/logout")
    def auth_logout():
        _clear_tokens(tokenstore)
        pending.clear()
        return jsonify({"status": "ok"})

    @app.post("/api/auth/switch-account")
    def auth_switch_account():
        # Sign out AND wipe this account's local data so the next account starts
        # clean (rows only — no schema change or DB-file deletion). The capability
        # profile is removed so it re-detects for the new watch.
        _clear_tokens(tokenstore)
        pending.clear()
        db.clear_all_data(db_path)
        try:
            (Path(db_path).parent / "capabilities.json").unlink(missing_ok=True)
        except OSError:
            pass
        return jsonify({"status": "ok"})

    # --- Settings (units, sync interval, baseline window, tab visibility) ---

    @app.get("/api/settings")
    def get_settings_route():
        from backend import settings as st
        return jsonify(st.load_settings(Path(db_path).parent / "settings.json"))

    @app.post("/api/settings")
    def post_settings_route():
        from backend import settings as st
        spath = Path(db_path).parent / "settings.json"
        prev = st.load_settings(spath)
        data = request.get_json(silent=True) or {}
        saved = st.save_settings(spath, data)
        # A new baseline window OR a changed HRV/RHR weighting changes stored
        # recovery scores — heal history immediately instead of waiting for the
        # next sync. (Band cutoffs are display-only; the frontend recolors.)
        if (saved["baseline_window_days"] != prev["baseline_window_days"]
                or saved["hrv_weight"] != prev["hrv_weight"]):
            rescore_history(db_path, saved["baseline_window_days"], saved["hrv_weight"])
        return jsonify(saved)

    # --- v4.3: config backup / restore (settings + custom tabs + journal;
    # distinct from the health-data export). Local only.
    @app.get("/api/config-backup")
    def config_backup():
        import json as _json
        from backend import settings as st
        cfg = dict(st.load_settings(Path(db_path).parent / "settings.json"))
        cfg.pop("anthropic_api_key", None)   # never write the key into a backup file
        body = _json.dumps({
            "version": 1,
            "settings": cfg,
            "journal": db.get_journal_range(db_path, 3650),
        }, indent=2, default=str)
        return Response(body, mimetype="application/json", headers={
            "Content-Disposition": "attachment; filename=garmin-dashboard-config.json"})

    @app.post("/api/config-restore")
    def config_restore():
        from backend import settings as st
        data = request.get_json(silent=True) or {}
        cfg = data.get("settings") if isinstance(data.get("settings"), dict) else {}
        cfg.pop("anthropic_api_key", None)   # a backup never carries the key; keep the current one
        saved = st.save_settings(Path(db_path).parent / "settings.json", cfg)
        restored = 0
        for j in (data.get("journal") or []):
            if isinstance(j, dict) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(j.get("date", ""))):
                db.upsert_journal(db_path, j["date"], j.get("tags") or {}, j.get("note") or "")
                restored += 1
        rescore_history(db_path, saved["baseline_window_days"], saved["hrv_weight"])
        return jsonify({"ok": True, "journal_restored": restored, "settings": saved})

    # --- Export the user's own data (local download) ---

    @app.get("/api/export/json")
    def export_json():
        import json as _json
        body = _json.dumps(db.export_all(db_path), indent=2, default=str)
        return Response(body, mimetype="application/json", headers={
            "Content-Disposition": "attachment; filename=garmin-dashboard-export.json"})

    @app.get("/api/export/csv")
    def export_csv():
        import csv
        import io
        cols = ["date"] + db.DAILY_FIELDS + ["recovery_score", "strain_score"]
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in db.get_all_daily(db_path):
            w.writerow(r)
        return Response(buf.getvalue(), mimetype="text/csv", headers={
            "Content-Disposition": "attachment; filename=garmin-dashboard-daily.csv"})

    # --- Serve the built SPA (the /api routes above take precedence) ---

    @app.get("/")
    def _spa_index():
        return send_from_directory(static_dir, "index.html")

    @app.get("/<path:filename>")
    def _spa_static(filename):
        if filename.startswith("api/"):
            abort(404)
        full = os.path.join(static_dir, filename)
        if os.path.isfile(full):
            return send_from_directory(static_dir, filename)
        return send_from_directory(static_dir, "index.html")  # SPA fallback

    return app


def _scheduled_loop(db_path, client_factory, first=False):
    from backend import settings as st
    s = st.load_settings(Path(db_path).parent / "settings.json")
    # Respect the user's sync preferences: a paused sync skips work entirely,
    # and sync_on_launch=False skips only the very first (launch) run.
    skip = s["sync_paused"] or (first and not s["sync_on_launch"])
    if not skip:
        try:
            client = client_factory()
            client.login()
            run_sync(client, db_path, backfill_days=s["baseline_window_days"],
                     hrv_weight=s["hrv_weight"])
            _maybe_auto_brief(db_path, s)
        except Exception as e:
            log.warning("scheduled sync failed: %s", type(e).__name__)
            db.write_sync_log(db_path, "error", type(e).__name__, {})
    # Re-read the interval each cycle so a settings change takes effect on the
    # next run without restarting the app.
    interval = s["sync_interval_minutes"] * 60
    t = threading.Timer(interval, _scheduled_loop, args=(db_path, client_factory))
    t.daemon = True
    t.start()


def _maybe_auto_brief(db_path, settings):
    """Pre-generate today's coach brief after a sync, if the user opted in and
    the coach is configured. Cached per date, so at most one Claude call/day."""
    from backend import coach
    if not (settings.get("coach_auto_brief") and coach.is_configured(settings)):
        return
    import datetime as _dt
    try:
        coach.daily_brief(db_path, settings, _dt.date.today().isoformat())
    except Exception as e:
        log.warning("auto-brief failed: %s", type(e).__name__)


def main():
    # Logs go to the user-data dir as well as stdout (Electron inherits stdio).
    # A redaction filter scrubs any credential/token-shaped text from both.
    redactor = RedactingFilter()
    stream_handler = logging.StreamHandler()
    file_handler = logging.FileHandler(cfg.LOG_PATH, encoding="utf-8")
    for h in (stream_handler, file_handler):
        h.addFilter(redactor)
    logging.basicConfig(level=logging.INFO, handlers=[stream_handler, file_handler])
    from backend.garmin_client import GarminClient

    def factory():
        # Auto-sync resumes from stored tokens only — credentials enter solely
        # through the in-app login flow (/api/auth/login), never from .env.
        return GarminClient(None, None, cfg.TOKENSTORE_DIR)

    app = create_app(cfg.DB_PATH, client_factory=factory)
    # Run the first sync (and its rescheduling) in a background thread so the
    # Flask server binds 127.0.0.1:5057 IMMEDIATELY. A long first backfill must
    # never delay the server coming up, or the UI reports "can't reach the
    # service" before the port is even open.
    threading.Thread(target=_scheduled_loop, args=(cfg.DB_PATH, factory),
                     kwargs={"first": True}, daemon=True).start()
    from backend import settings as st
    host = resolve_host(st.load_settings(Path(cfg.DB_PATH).parent / "settings.json"))
    app.run(host=host, port=5057)


if __name__ == "__main__":
    main()
