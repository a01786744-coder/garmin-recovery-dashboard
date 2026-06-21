"""Local Flask API serving cached SQLite data + manual/scheduled sync."""
import threading
import logging

from flask import Flask, jsonify, request

import backend.config as cfg
import backend.db as db
from backend.sync import run_sync

log = logging.getLogger("api")


def create_app(db_path=cfg.DB_PATH, client_factory=None):
    app = Flask(__name__, static_folder=None)
    db.init_db(db_path)

    def _trends(days):
        rows = db.get_trends(db_path, days)
        return {
            "days": rows,
            "hrv": [{"date": r["date"], "value": r["hrv_last_night"]} for r in rows],
            "rhr": [{"date": r["date"], "value": r["rhr"]} for r in rows],
        }

    @app.get("/api/today")
    def today():
        rows = db.get_trends(db_path, 1)
        metrics = rows[-1] if rows else None
        return jsonify({
            "metrics": metrics,
            "activities": db.get_recent_activities(db_path, 10),
            "sync": db.get_last_sync(db_path),
        })

    @app.get("/api/trends")
    def trends():
        days = int(request.args.get("days", 30))
        return jsonify(_trends(days))

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

    return app


def _scheduled_loop(db_path, client_factory):
    try:
        client = client_factory()
        client.login()
        run_sync(client, db_path)
    except Exception as e:
        log.warning("scheduled sync failed: %s", type(e).__name__)
        db.write_sync_log(db_path, "error", type(e).__name__, {})
    finally:
        t = threading.Timer(cfg.SYNC_INTERVAL_SECONDS, _scheduled_loop,
                            args=(db_path, client_factory))
        t.daemon = True
        t.start()


def main():
    logging.basicConfig(level=logging.INFO)
    from backend.garmin_client import GarminClient

    def factory():
        return GarminClient(cfg.GARMIN_EMAIL, cfg.GARMIN_PASSWORD, cfg.TOKENSTORE_DIR)

    app = create_app(cfg.DB_PATH, client_factory=factory)
    _scheduled_loop(cfg.DB_PATH, factory)   # immediate + every 30 min
    app.run(host="127.0.0.1", port=5057)


if __name__ == "__main__":
    main()
