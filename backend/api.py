"""Local Flask API serving cached SQLite data + manual/scheduled sync + auth."""
import os
import re
import threading
import logging
from pathlib import Path

from flask import Flask, jsonify, request, Response

import backend.config as cfg
import backend.db as db
from backend.sync import run_sync, sync_activity_detail

log = logging.getLogger("api")


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
               tokenstore=cfg.TOKENSTORE_DIR, auth_client_factory=None):
    app = Flask(__name__, static_folder=None)
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
        rows = db.get_trends(db_path, 1)
        metrics = rows[-1] if rows else None
        sync = db.get_last_sync(db_path)
        window = st.load_settings(Path(db_path).parent / "settings.json")["baseline_window_days"]
        return jsonify({
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

    @app.get("/api/insights")
    def insights():
        from backend import insights as ins
        daily = db.get_trends(db_path, 90)
        acts = db.get_recent_activities(db_path, 50)
        return jsonify({
            "weekly": ins.weekly_recap(daily, acts),
            "streaks": ins.streaks(daily, acts),
            "insights": ins.auto_insights(daily),
            "correlations": ins.correlations(daily),
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

    @app.get("/api/sync-status")
    def sync_status():
        return jsonify(db.get_last_sync(db_path) or {"status": "never"})

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
        return jsonify(run_sync(client, db_path))

    # --- Auth: in-app login / MFA / logout (no file editing by the user) ---

    @app.get("/api/auth/status")
    def auth_status():
        return jsonify({"authenticated": _has_tokens(tokenstore)})

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
        data = request.get_json(silent=True) or {}
        return jsonify(st.save_settings(Path(db_path).parent / "settings.json", data))

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

    return app


def _scheduled_loop(db_path, client_factory):
    from backend import settings as st
    s = st.load_settings(Path(db_path).parent / "settings.json")
    try:
        client = client_factory()
        client.login()
        run_sync(client, db_path, backfill_days=s["baseline_window_days"])
    except Exception as e:
        log.warning("scheduled sync failed: %s", type(e).__name__)
        db.write_sync_log(db_path, "error", type(e).__name__, {})
    finally:
        # Re-read the interval each cycle so a settings change takes effect on
        # the next run without restarting the app.
        interval = s["sync_interval_minutes"] * 60
        t = threading.Timer(interval, _scheduled_loop, args=(db_path, client_factory))
        t.daemon = True
        t.start()


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
    _scheduled_loop(cfg.DB_PATH, factory)   # immediate + every 30 min
    app.run(host="127.0.0.1", port=5057)


if __name__ == "__main__":
    main()
