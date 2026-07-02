"""Orchestrate a Whoop-style sync.

Primary day is TODAY: Garmin files last night's sleep and HRV under the wake
date, so today's record holds last night's sleep+HRV plus today's accumulating
wellness and workouts. Recovery for a day compares that day's HRV/RHR to the
trailing 30-day baseline (days strictly before it). On a fresh DB the baseline
and trends are empty, so we backfill missing days in the window (HRV/RHR only,
via fetch_baseline) oldest->newest — paced and 429-tolerant: a transport/rate
error stops the backfill, keeps what we have, marks the sync 'partial', and
resumes on the next run.
"""
import datetime as dt
import logging
import time
from pathlib import Path

import backend.db as db
from backend import recovery as rec
from backend import capabilities as caps
from backend.config import (
    BASELINE_WINDOW_DAYS, CAPABILITY_READY_DAYS, BASELINE_FETCH_VERSION,
)
from backend.garmin_client import (
    GarminAuthError, GarminRateLimitError, GarminConnectionError,
    GarminMFARequired,
)

log = logging.getLogger("sync")


def _capability_path(db_path):
    # Co-locate the profile with the DB so it lands in the same user-data dir.
    return Path(db_path).parent / "capabilities.json"


def _update_capabilities(db_path, device_name=None, baseline_fetch_version=None):
    """Recompute + persist the capability profile from already-stored data
    (no extra Garmin calls). Sticky + readiness-gated (see capabilities.py).
    Also carries the detected device name (sticky) and the backfill version."""
    prev = caps.load_profile(_capability_path(db_path))
    perf = db.get_latest_perf(db_path)
    profile = caps.compute_profile(
        db.get_trends(db_path, BASELINE_WINDOW_DAYS),
        [perf] if perf else [],
        db.get_personal_records(db_path),
        db.get_recent_activities(db_path, 10),
        prev=prev,
        ready_days=CAPABILITY_READY_DAYS,
    )
    profile["device_name"] = device_name or (prev or {}).get("device_name")
    profile["baseline_fetch_version"] = (
        baseline_fetch_version if baseline_fetch_version is not None
        else (prev or {}).get("baseline_fetch_version", 0)
    )
    caps.save_profile(_capability_path(db_path), profile)
    return profile

_FETCH_ERRORS = (GarminAuthError, GarminRateLimitError, GarminConnectionError,
                 GarminMFARequired)


def _recovery_for(db_path, date_str, hrv_today, rhr_today, window=BASELINE_WINDOW_DAYS):
    hrv_hist = db.get_history_before(db_path, "hrv_last_night", date_str, window)
    rhr_hist = db.get_history_before(db_path, "rhr", date_str, window)
    return rec.recovery_score(hrv_today, rhr_today, hrv_hist, rhr_hist,
                              min_days=rec.min_days_for_window(window))


def rescore_history(db_path, window=BASELINE_WINDOW_DAYS):
    """Recompute recovery AND strain for every stored day from already-stored
    data — no Garmin calls. Heals history after a formula fix or a
    baseline-window settings change (scores were previously frozen at sync
    time)."""
    for d in db.get_dates(db_path):
        row = db.get_daily(db_path, d) or {}
        recovery = _recovery_for(db_path, d, row.get("hrv_last_night"),
                                 row.get("rhr"), window)
        strain = rec.strain_score(db.get_activities_on(db_path, d), row)
        db.update_scores(db_path, d, recovery=recovery, strain=strain)


def run_sync(client, db_path, today=None, backfill_days=BASELINE_WINDOW_DAYS, pacing=1.5):
    today = today or dt.date.today()
    today_str = today.isoformat()
    start_str = (today - dt.timedelta(days=backfill_days)).isoformat()
    existing = db.get_existing_dates(db_path, backfill_days)
    # If the backfill fetch set was expanded (e.g. sleep added), re-fetch the
    # whole window once so older DBs gain the new history.
    prev_profile = caps.load_profile(_capability_path(db_path)) or {}
    need_rebackfill = prev_profile.get("baseline_fetch_version", 0) < BASELINE_FETCH_VERSION

    status = "ok"
    device_name = None
    try:
        # 1. Backfill missing PAST days (oldest first so each day's baseline
        #    is already stored when we score it). Paced + 429-tolerant.
        for i in range(backfill_days, 0, -1):
            d = (today - dt.timedelta(days=i)).isoformat()
            if d in existing and not need_rebackfill:
                continue
            base = client.fetch_baseline(d)
            if client.last_fetch_had_errors:
                status = "partial"          # rate-limited; resume next sync
                break
            metrics = {k: None for k in db.DAILY_FIELDS}
            metrics.update(base)
            recovery = _recovery_for(db_path, d, base.get("hrv_last_night"), base.get("rhr"), backfill_days)
            db.upsert_daily(db_path, d, metrics, recovery, None)
            if pacing:
                time.sleep(pacing)

        # 2. Today (full) + activities through today.
        metrics, availability = client.fetch_day(today_str)
        activities = client.fetch_activities(start_str, today_str)
    except _FETCH_ERRORS as e:
        msg = type(e).__name__
        log.warning("sync failed: %s", msg)
        db.write_sync_log(db_path, "error", msg, {})
        return {"status": "error", "message": msg, "availability": {}}

    db.upsert_activities(db_path, activities)
    recovery = _recovery_for(db_path, today_str,
                             metrics.get("hrv_last_night"), metrics.get("rhr"), backfill_days)
    strain = rec.strain_score([a for a in activities if a.get("date") == today_str], metrics)
    db.upsert_daily(db_path, today_str, metrics, recovery, strain)
    # Newly backfilled days extend the baseline; recompute stored scores so
    # history heals as data accumulates (cheap: local DB only).
    rescore_history(db_path, backfill_days)

    # Today-only extras (cost-controlled: not backfilled). Non-fatal — the core
    # day is already stored, so a failure here must not fail the whole sync.
    try:
        db.upsert_perf(db_path, today_str, client.fetch_performance(today_str))
        for metric, series in client.fetch_intraday(today_str).items():
            if series:
                db.upsert_intraday(db_path, today_str, metric, series)
        prs = client.fetch_personal_records()
        if prs:
            db.replace_personal_records(db_path, prs)
        device_name = client.fetch_device_name()
    except _FETCH_ERRORS as e:
        log.warning("extras fetch failed: %s", type(e).__name__)

    # Re-probe capabilities from stored data (unlocks tabs an upgraded watch
    # starts reporting; never an extra Garmin call). Persist the device name and
    # only advance the backfill version once a backfill fully completed.
    new_version = BASELINE_FETCH_VERSION if status == "ok" else None
    _update_capabilities(db_path, device_name=device_name, baseline_fetch_version=new_version)

    msg = "synced" if status == "ok" else "synced (backfill rate-limited; will resume)"
    db.write_sync_log(db_path, status, msg, availability)
    return {"status": status, "message": msg, "availability": availability}


def sync_activity_detail(client, db_path, activity_id):
    """Fetch + cache one activity's detail (route, splits, HR zones, weather).
    Used on-demand by the API. Returns the stored detail; on a fetch error
    returns whatever was already cached (never raises)."""
    try:
        d = client.fetch_activity_detail(activity_id)
    except _FETCH_ERRORS as e:
        log.warning("activity detail fetch failed: %s", type(e).__name__)
        return db.get_activity_detail(db_path, activity_id)
    db.upsert_activity_detail(db_path, activity_id, polyline_json=d.get("polyline"),
                              splits_json=d.get("splits"), hr_zones_json=d.get("hr_zones"),
                              weather_json=d.get("weather"), summary_json=d.get("summary"))
    return db.get_activity_detail(db_path, activity_id)
