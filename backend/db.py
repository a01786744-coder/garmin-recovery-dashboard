"""SQLite persistence. Missing metrics are stored as NULL (never fabricated)."""
import json
import sqlite3

DAILY_FIELDS = [
    "hrv_last_night", "hrv_status", "rhr", "sleep_score",
    "deep_sleep_s", "light_sleep_s", "rem_sleep_s", "awake_sleep_s",
    "steps", "calories", "body_battery", "training_readiness_score",
    "stress_avg", "vo2max",
    # v2 expansion
    "floors_ascended", "intensity_moderate", "intensity_vigorous",
    "intensity_weekly_total", "intensity_weekly_goal",
    "highly_active_s", "active_s", "sedentary_s",
    "active_calories", "resting_calories", "distance_m",
    "resp_waking", "resp_sleep",
    "sleep_need_actual", "sleep_need_baseline",
    "sleep_deep_score", "sleep_rem_score", "sleep_light_score",
    "sleep_restlessness_score", "awake_count",
    # Stage-quality qualifiers (EXCELLENT/GOOD/FAIR/POOR) from sleepScores.
    "sleep_deep_qual", "sleep_rem_qual", "sleep_light_qual",
    "sleep_restlessness_qual",
    "training_status_label", "acwr_ratio", "acute_load", "chronic_load",
    "load_aerobic_low", "load_aerobic_high", "load_anaerobic",
    "tr_sleep_factor", "tr_recovery_factor", "tr_acwr_factor",
    "tr_hrv_factor", "tr_stress_factor",
    # v3.9: recovery time + naps + skin temp (free from payloads fetch_day
    # already pulls); SpO2 + hydration (one extra call each, today only).
    "recovery_time_min", "nap_time_s", "skin_temp_dev_c",
    "spo2_avg", "spo2_lowest", "spo2_avg_sleep",
    "hydration_ml", "hydration_goal_ml", "sweat_loss_ml",
]

# Daily fields stored as TEXT rather than REAL.
TEXT_FIELDS = ("hrv_status", "training_status_label",
               "sleep_deep_qual", "sleep_rem_qual", "sleep_light_qual",
               "sleep_restlessness_qual")


def _conn(path):
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    return c


def _ensure_columns(c, table, wanted):
    """Add any missing columns to an existing table (lightweight migration so
    a DB created with an older schema gains new columns instead of erroring)."""
    existing = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
    for col, typ in wanted:
        if col not in existing:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")


def init_db(path):
    with _conn(path) as c:
        cols = ", ".join(f"{f} TEXT" if f in TEXT_FIELDS else f"{f} REAL"
                         for f in DAILY_FIELDS)
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS daily_metrics (
                date TEXT PRIMARY KEY, {cols},
                recovery_score INTEGER, strain_score INTEGER
            )""")
        # Migrate older DBs: add any daily_metrics columns introduced later.
        _ensure_columns(c, "daily_metrics",
                        [(f, "TEXT" if f in TEXT_FIELDS else "REAL") for f in DAILY_FIELDS]
                        + [("recovery_score", "INTEGER"), ("strain_score", "INTEGER")])
        c.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                activity_id INTEGER PRIMARY KEY, date TEXT, type TEXT,
                duration_s REAL, avg_hr REAL, max_hr REAL,
                training_load REAL, aerobic_te REAL, anaerobic_te REAL
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT, message TEXT, availability TEXT
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS daily_intraday (
                date TEXT, metric TEXT, json TEXT, PRIMARY KEY (date, metric)
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS journal (
                date TEXT PRIMARY KEY, tags TEXT, note TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS perf_metrics (
                date TEXT PRIMARY KEY, vo2max REAL, vo2max_cycling REAL,
                fitness_age REAL, race_5k REAL, race_10k REAL, race_hm REAL,
                race_marathon REAL, endurance_score REAL, endurance_class REAL,
                heat_acclimation REAL, altitude_acclimation REAL
            )""")
        # v3.9: performance-snapshot metrics added later — migrate older DBs.
        _ensure_columns(c, "perf_metrics", [
            ("running_tolerance_load", "REAL"), ("running_tolerance_ceiling", "REAL"),
            ("hill_score", "REAL"), ("lt_hr", "REAL"), ("lt_power", "REAL"),
            ("body_weight_g", "REAL"),
        ])
        c.execute("""
            CREATE TABLE IF NOT EXISTS personal_records (
                id INTEGER PRIMARY KEY, type_id INTEGER, value REAL,
                activity_id INTEGER, activity_name TEXT, start_time TEXT
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS activity_detail (
                activity_id INTEGER PRIMARY KEY, polyline_json TEXT,
                splits_json TEXT, hr_zones_json TEXT, weather_json TEXT,
                summary_json TEXT, fetched_at TEXT
            )""")
        # v3.8: strength exercise sets cached alongside the rest of the detail.
        # v3.9: running dynamics + power snapshot for the activity.
        _ensure_columns(c, "activity_detail",
                        [("exercise_sets_json", "TEXT"), ("dynamics_json", "TEXT")])


_ALL_TABLES = ["daily_metrics", "activities", "sync_log", "daily_intraday",
               "perf_metrics", "personal_records", "activity_detail"]


def clear_all_data(path):
    """Delete every row from every table (account switch / fresh start). Clears
    rows only — does NOT drop tables, alter schema, or delete the DB file."""
    with _conn(path) as c:
        for t in _ALL_TABLES:
            c.execute(f"DELETE FROM {t}")


def count_daily(path):
    with _conn(path) as c:
        return c.execute("SELECT COUNT(*) AS n FROM daily_metrics").fetchone()["n"]


def get_all_daily(path):
    with _conn(path) as c:
        rows = c.execute("SELECT * FROM daily_metrics ORDER BY date").fetchall()
        return [dict(r) for r in rows]


def export_all(path):
    """All of the user's own stored data, for export. Intraday/activity-detail
    blobs are excluded (large, derived); the scalar time series + activities +
    performance + records are what's useful out of the app."""
    with _conn(path) as c:
        def rows(sql):
            return [dict(r) for r in c.execute(sql).fetchall()]
        return {
            "daily_metrics": rows("SELECT * FROM daily_metrics ORDER BY date"),
            "activities": rows("SELECT * FROM activities ORDER BY date"),
            "perf_metrics": rows("SELECT * FROM perf_metrics ORDER BY date"),
            "personal_records": rows("SELECT * FROM personal_records ORDER BY type_id"),
        }


def upsert_daily(path, date, metrics, recovery, strain, merge=False):
    """Insert or update a day. merge=True (used by the backfill) makes None a
    no-op per column — a sparse re-fetch must never wipe richer fields the
    daily sync already stored (sleep need, readiness, respiration, ...)."""
    cols = ["date"] + DAILY_FIELDS + ["recovery_score", "strain_score"]
    vals = [date] + [metrics.get(f) for f in DAILY_FIELDS] + [recovery, strain]
    placeholders = ", ".join("?" for _ in cols)
    if merge:
        updates = ", ".join(f"{c2}=COALESCE(excluded.{c2}, daily_metrics.{c2})"
                            for c2 in cols if c2 != "date")
    else:
        updates = ", ".join(f"{c2}=excluded.{c2}" for c2 in cols if c2 != "date")
    with _conn(path) as c:
        c.execute(
            f"INSERT INTO daily_metrics ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(date) DO UPDATE SET {updates}", vals)


def upsert_activities(path, activities):
    with _conn(path) as c:
        for a in activities:
            if a.get("activity_id") is None:
                continue
            c.execute("""
                INSERT INTO activities (activity_id, date, type, duration_s,
                    avg_hr, max_hr, training_load, aerobic_te, anaerobic_te)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(activity_id) DO UPDATE SET
                    date=excluded.date, type=excluded.type,
                    duration_s=excluded.duration_s, avg_hr=excluded.avg_hr,
                    max_hr=excluded.max_hr, training_load=excluded.training_load,
                    aerobic_te=excluded.aerobic_te, anaerobic_te=excluded.anaerobic_te
            """, [a.get(k) for k in ("activity_id", "date", "type", "duration_s",
                  "avg_hr", "max_hr", "training_load", "aerobic_te", "anaerobic_te")])


def get_daily(path, date):
    with _conn(path) as c:
        row = c.execute("SELECT * FROM daily_metrics WHERE date=?", (date,)).fetchone()
        return dict(row) if row else None


def get_trends(path, days):
    with _conn(path) as c:
        rows = c.execute(
            "SELECT * FROM daily_metrics ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


# A day counts as the dashboard's "primary day" once it has last-night markers
# (sleep or overnight HRV) — these drive the Sleep/Recovery gauges. RHR/steps
# can trickle in for an incomplete today, so they must NOT qualify a day on
# their own (that would select an empty-gauge today before sleep has synced).
_PRIMARY_DAY_FIELDS = ("sleep_score", "hrv_last_night")


def get_primary_day(path):
    """The most recent day with last-night data (sleep/HRV), so the dashboard
    shows the latest completed day rather than an empty 'today' before the watch
    has synced last night's data (Whoop-style). Falls back to the most recent
    row when none qualify; None on an empty DB."""
    cond = " OR ".join(f"{f} IS NOT NULL" for f in _PRIMARY_DAY_FIELDS)
    with _conn(path) as c:
        row = c.execute(
            f"SELECT * FROM daily_metrics WHERE {cond} ORDER BY date DESC LIMIT 1"
        ).fetchone()
        if row is None:
            row = c.execute(
                "SELECT * FROM daily_metrics ORDER BY date DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None


def get_history(path, field, days):
    if field not in DAILY_FIELDS:
        raise ValueError(f"unknown field {field}")
    with _conn(path) as c:
        rows = c.execute(
            f"SELECT {field} FROM daily_metrics ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
        return [r[field] for r in reversed(rows)]


def get_history_before(path, field, before_date, days):
    """The `days` most recent values of `field` strictly before `before_date`,
    returned ascending. Used to build a recovery baseline that excludes the day
    being scored."""
    if field not in DAILY_FIELDS:
        raise ValueError(f"unknown field {field}")
    with _conn(path) as c:
        rows = c.execute(
            f"SELECT {field} FROM daily_metrics WHERE date < ? "
            f"ORDER BY date DESC LIMIT ?", (before_date, days)
        ).fetchall()
        return [r[field] for r in reversed(rows)]


def _journal_row(row):
    return {"date": row["date"], "tags": json.loads(row["tags"] or "{}"),
            "note": row["note"] or ""}


def upsert_journal(path, date, tags, note):
    with _conn(path) as c:
        c.execute(
            "INSERT INTO journal(date, tags, note, updated_at) "
            "VALUES(?, ?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(date) DO UPDATE SET tags=excluded.tags, "
            "note=excluded.note, updated_at=CURRENT_TIMESTAMP",
            (date, json.dumps(tags or {}), note or ""))


def get_journal(path, date):
    with _conn(path) as c:
        row = c.execute("SELECT * FROM journal WHERE date=?", (date,)).fetchone()
        return _journal_row(row) if row else None


def get_journal_before(path, date):
    """Most recent entry strictly before `date` — the sticky-prefill source."""
    with _conn(path) as c:
        row = c.execute("SELECT * FROM journal WHERE date < ? "
                        "ORDER BY date DESC LIMIT 1", (date,)).fetchone()
        return _journal_row(row) if row else None


def get_journal_range(path, days):
    """The most recent `days` entries, ascending (for correlations)."""
    with _conn(path) as c:
        rows = c.execute("SELECT * FROM journal ORDER BY date DESC LIMIT ?",
                         (days,)).fetchall()
        return [_journal_row(r) for r in reversed(rows)]


def update_scores(path, date, recovery=..., strain=...):
    """Update only the computed scores for an existing day (used by the rescore
    pass). Pass a value (or None) to set a score; omit to leave it untouched."""
    sets, args = [], []
    if recovery is not ...:
        sets.append("recovery_score=?"); args.append(recovery)
    if strain is not ...:
        sets.append("strain_score=?"); args.append(strain)
    if not sets:
        return
    args.append(date)
    with _conn(path) as c:
        c.execute(f"UPDATE daily_metrics SET {', '.join(sets)} WHERE date=?", args)


def get_existing_dates(path, days):
    """Set of date strings present among the most recent `days` rows. Used to
    skip days already stored during backfill."""
    with _conn(path) as c:
        rows = c.execute(
            "SELECT date FROM daily_metrics ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
        return {r["date"] for r in rows}


def get_dates(path):
    """All dates that have a daily row, ascending. Powers the day browser."""
    with _conn(path) as c:
        rows = c.execute("SELECT date FROM daily_metrics ORDER BY date").fetchall()
        return [r["date"] for r in rows]


def get_recent_activities(path, limit):
    with _conn(path) as c:
        rows = c.execute(
            "SELECT * FROM activities ORDER BY date DESC, activity_id DESC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_activities_on(path, date):
    """Activities recorded on a specific date (for the day browser)."""
    with _conn(path) as c:
        rows = c.execute(
            "SELECT * FROM activities WHERE date=? ORDER BY activity_id DESC", (date,)
        ).fetchall()
        return [dict(r) for r in rows]


def write_sync_log(path, status, message, availability):
    with _conn(path) as c:
        c.execute(
            "INSERT INTO sync_log (status, message, availability) VALUES (?,?,?)",
            (status, message, json.dumps(availability or {})))


def last_sync_statuses(path, n):
    """The most recent n sync outcomes as (status, message), newest first.
    Used to detect a persistently broken session (repeated auth failures)."""
    with _conn(path) as c:
        rows = c.execute(
            "SELECT status, message FROM sync_log ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        return [(r["status"], r["message"]) for r in rows]


def get_last_sync(path):
    with _conn(path) as c:
        row = c.execute(
            "SELECT * FROM sync_log ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            return None
        d = dict(row)
        d["availability"] = json.loads(d.get("availability") or "{}")
        return d


# --- v2: intraday curves, performance metrics, PRs, activity detail ---

def upsert_intraday(path, date, metric, data_list):
    with _conn(path) as c:
        c.execute("INSERT INTO daily_intraday (date, metric, json) VALUES (?,?,?) "
                  "ON CONFLICT(date, metric) DO UPDATE SET json=excluded.json",
                  (date, metric, json.dumps(data_list)))


def get_intraday(path, date, metric):
    with _conn(path) as c:
        row = c.execute("SELECT json FROM daily_intraday WHERE date=? AND metric=?",
                        (date, metric)).fetchone()
        return json.loads(row["json"]) if row else None


_PERF_COLS = ["vo2max", "vo2max_cycling", "fitness_age", "race_5k", "race_10k",
              "race_hm", "race_marathon", "endurance_score", "endurance_class",
              "heat_acclimation", "altitude_acclimation",
              # v3.9
              "running_tolerance_load", "running_tolerance_ceiling",
              "hill_score", "lt_hr", "lt_power", "body_weight_g"]


def upsert_perf(path, date, perf):
    cols = ["date"] + _PERF_COLS
    vals = [date] + [perf.get(k) for k in _PERF_COLS]
    ph = ", ".join("?" for _ in cols)
    # COALESCE: these fields come from several endpoints, any of which can fail
    # independently (returns None). A re-sync must never wipe a value another
    # endpoint stored earlier the same day.
    upd = ", ".join(f"{c2}=COALESCE(excluded.{c2}, perf_metrics.{c2})"
                    for c2 in cols if c2 != "date")
    with _conn(path) as c:
        c.execute(f"INSERT INTO perf_metrics ({', '.join(cols)}) VALUES ({ph}) "
                  f"ON CONFLICT(date) DO UPDATE SET {upd}", vals)


def get_latest_perf(path):
    with _conn(path) as c:
        row = c.execute("SELECT * FROM perf_metrics ORDER BY date DESC LIMIT 1").fetchone()
        return dict(row) if row else None


def get_perf_history(path, days):
    with _conn(path) as c:
        rows = c.execute(
            "SELECT * FROM perf_metrics ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


def replace_personal_records(path, records):
    with _conn(path) as c:
        c.execute("DELETE FROM personal_records")
        for r in records:
            c.execute("INSERT INTO personal_records (id, type_id, value, activity_id, "
                      "activity_name, start_time) VALUES (?,?,?,?,?,?)",
                      [r.get(k) for k in ("id", "type_id", "value", "activity_id",
                                          "activity_name", "start_time")])


def get_personal_records(path):
    with _conn(path) as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM personal_records ORDER BY type_id").fetchall()]


def upsert_activity_detail(path, activity_id, polyline_json=None, splits_json=None,
                           hr_zones_json=None, weather_json=None, summary_json=None,
                           exercise_sets_json=None, dynamics_json=None):
    import datetime as _dt
    blobs = [json.dumps(x) if x is not None else None
             for x in (polyline_json, splits_json, hr_zones_json, weather_json,
                       summary_json, exercise_sets_json, dynamics_json)]
    with _conn(path) as c:
        c.execute("""INSERT INTO activity_detail (activity_id, polyline_json, splits_json,
            hr_zones_json, weather_json, summary_json, exercise_sets_json, dynamics_json,
            fetched_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(activity_id) DO UPDATE SET polyline_json=excluded.polyline_json,
            splits_json=excluded.splits_json, hr_zones_json=excluded.hr_zones_json,
            weather_json=excluded.weather_json, summary_json=excluded.summary_json,
            exercise_sets_json=excluded.exercise_sets_json,
            dynamics_json=excluded.dynamics_json,
            fetched_at=excluded.fetched_at""",
            [activity_id] + blobs + [_dt.datetime.now().isoformat()])


def get_activity_detail(path, activity_id):
    with _conn(path) as c:
        row = c.execute("SELECT * FROM activity_detail WHERE activity_id=?",
                        (activity_id,)).fetchone()
        if not row:
            return None

        def _load(v):
            return json.loads(v) if v else None
        keys = row.keys()
        return {"polyline": _load(row["polyline_json"]), "splits": _load(row["splits_json"]),
                "hr_zones": _load(row["hr_zones_json"]), "weather": _load(row["weather_json"]),
                "summary": _load(row["summary_json"]),
                "exercise_sets": _load(row["exercise_sets_json"]),
                "dynamics": _load(row["dynamics_json"]) if "dynamics_json" in keys else None,
                "fetched_at": row["fetched_at"]}
