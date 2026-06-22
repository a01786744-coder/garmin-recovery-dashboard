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
    "training_status_label", "acwr_ratio", "acute_load", "chronic_load",
    "load_aerobic_low", "load_aerobic_high", "load_anaerobic",
    "tr_sleep_factor", "tr_recovery_factor", "tr_acwr_factor",
    "tr_hrv_factor", "tr_stress_factor",
]

# Daily fields stored as TEXT rather than REAL.
TEXT_FIELDS = ("hrv_status", "training_status_label")


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
            CREATE TABLE IF NOT EXISTS perf_metrics (
                date TEXT PRIMARY KEY, vo2max REAL, vo2max_cycling REAL,
                fitness_age REAL, race_5k REAL, race_10k REAL, race_hm REAL,
                race_marathon REAL, endurance_score REAL, endurance_class REAL,
                heat_acclimation REAL, altitude_acclimation REAL
            )""")
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


def upsert_daily(path, date, metrics, recovery, strain):
    cols = ["date"] + DAILY_FIELDS + ["recovery_score", "strain_score"]
    vals = [date] + [metrics.get(f) for f in DAILY_FIELDS] + [recovery, strain]
    placeholders = ", ".join("?" for _ in cols)
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


def get_existing_dates(path, days):
    """Set of date strings present among the most recent `days` rows. Used to
    skip days already stored during backfill."""
    with _conn(path) as c:
        rows = c.execute(
            "SELECT date FROM daily_metrics ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
        return {r["date"] for r in rows}


def get_recent_activities(path, limit):
    with _conn(path) as c:
        rows = c.execute(
            "SELECT * FROM activities ORDER BY date DESC, activity_id DESC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]


def write_sync_log(path, status, message, availability):
    with _conn(path) as c:
        c.execute(
            "INSERT INTO sync_log (status, message, availability) VALUES (?,?,?)",
            (status, message, json.dumps(availability or {})))


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
              "heat_acclimation", "altitude_acclimation"]


def upsert_perf(path, date, perf):
    cols = ["date"] + _PERF_COLS
    vals = [date] + [perf.get(k) for k in _PERF_COLS]
    ph = ", ".join("?" for _ in cols)
    upd = ", ".join(f"{c2}=excluded.{c2}" for c2 in cols if c2 != "date")
    with _conn(path) as c:
        c.execute(f"INSERT INTO perf_metrics ({', '.join(cols)}) VALUES ({ph}) "
                  f"ON CONFLICT(date) DO UPDATE SET {upd}", vals)


def get_latest_perf(path):
    with _conn(path) as c:
        row = c.execute("SELECT * FROM perf_metrics ORDER BY date DESC LIMIT 1").fetchone()
        return dict(row) if row else None


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
                           hr_zones_json=None, weather_json=None, summary_json=None):
    import datetime as _dt
    blobs = [json.dumps(x) if x is not None else None
             for x in (polyline_json, splits_json, hr_zones_json, weather_json, summary_json)]
    with _conn(path) as c:
        c.execute("""INSERT INTO activity_detail (activity_id, polyline_json, splits_json,
            hr_zones_json, weather_json, summary_json, fetched_at) VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(activity_id) DO UPDATE SET polyline_json=excluded.polyline_json,
            splits_json=excluded.splits_json, hr_zones_json=excluded.hr_zones_json,
            weather_json=excluded.weather_json, summary_json=excluded.summary_json,
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
        return {"polyline": _load(row["polyline_json"]), "splits": _load(row["splits_json"]),
                "hr_zones": _load(row["hr_zones_json"]), "weather": _load(row["weather_json"]),
                "summary": _load(row["summary_json"]), "fetched_at": row["fetched_at"]}
