"""SQLite persistence. Missing metrics are stored as NULL (never fabricated)."""
import json
import sqlite3

DAILY_FIELDS = [
    "hrv_last_night", "hrv_status", "rhr", "sleep_score",
    "deep_sleep_s", "light_sleep_s", "rem_sleep_s", "awake_sleep_s",
    "steps", "calories", "body_battery", "training_readiness_score",
    "stress_avg", "vo2max",
]


def _conn(path):
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    return c


def init_db(path):
    with _conn(path) as c:
        cols = ", ".join(f"{f} REAL" if f not in ("hrv_status",) else f"{f} TEXT"
                         for f in DAILY_FIELDS)
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS daily_metrics (
                date TEXT PRIMARY KEY, {cols},
                recovery_score INTEGER, strain_score INTEGER
            )""")
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
