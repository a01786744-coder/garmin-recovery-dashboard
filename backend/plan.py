"""v5.0 C1: adaptive multi-week training plan.

The coach generates a plan toward a race: detailed workouts (the same design
JSON the single-workout flow uses) for the next couple of weeks, outlines for
the rest. "Adapt" revises the remaining weeks from what actually happened —
completed sessions, recovery trend — and materializes the upcoming week.

Nothing here talks to Garmin: pushing a week to the watch goes through the
same explicit send path as single workouts (api.py), which is the app's only
write to the user's account.
"""
import datetime as dt
import json

from backend import coach, db

MAX_WEEKS = 24

_WEEK = {
    "type": "object",
    "properties": {
        "index": {"type": "integer", "description": "1-based week number"},
        "start": {"type": "string", "description": "Monday of the week, YYYY-MM-DD"},
        "focus": {"type": "string",
                  "description": "short phase label: base / build / peak / taper / recovery"},
        "target_km": {"type": "number", "description": "planned volume for the week"},
        "long_run_km": {"anyOf": [{"type": "number"}, {"type": "null"}]},
        "summary": {"type": "string", "description": "1-2 sentences on the week's intent"},
        "workouts": {
            "anyOf": [
                {"type": "array", "items": coach.WORKOUT_SCHEMA},
                {"type": "null"},
            ],
            "description": "Detailed sessions ONLY for the next 2 weeks; null for later weeks",
        },
    },
    "required": ["index", "start", "focus", "target_km", "long_run_km",
                 "summary", "workouts"],
    "additionalProperties": False,
}

PLAN_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string",
                  "description": "the coach's message about the plan/changes"},
        "weeks": {"type": "array", "items": _WEEK, "maxItems": MAX_WEEKS},
    },
    "required": ["reply", "weeks"],
    "additionalProperties": False,
}


def _week_for(weeks, today_str):
    """The plan week containing `today_str` (Mon–Sun), or None."""
    for w in weeks or []:
        start = w.get("start")
        if not start:
            continue
        try:
            d0 = dt.date.fromisoformat(start)
        except ValueError:
            continue
        if d0 <= dt.date.fromisoformat(today_str) <= d0 + dt.timedelta(days=6):
            return w
    return None


def todays_session(db_path, today_str):
    """The workout design scheduled for `today_str` in the active plan, or
    None. Matches on each workout's suggested_date."""
    stored = db.get_training_plan(db_path)
    if not stored:
        return None
    for w in stored["weeks"]:
        for wk in w.get("workouts") or []:
            if wk.get("suggested_date") == today_str:
                return wk
    return None


def plan_context(db_path, today_str):
    """Compact plan snapshot for the coach: the race, this week's outline, and
    today's planned session (if any). None when no plan is active."""
    stored = db.get_training_plan(db_path)
    if not stored:
        return None
    week = _week_for(stored["weeks"], today_str)
    days_to_race = None
    try:
        days_to_race = (dt.date.fromisoformat(stored["race"]["date"])
                        - dt.date.fromisoformat(today_str)).days
    except (ValueError, KeyError, TypeError):
        pass
    return {
        "race": stored["race"],
        "days_to_race": days_to_race,
        "this_week": None if not week else {
            "index": week.get("index"), "focus": week.get("focus"),
            "target_km": week.get("target_km"), "summary": week.get("summary")},
        "today_planned": todays_session(db_path, today_str),
    }


def _validate_race(race, today_str):
    if not isinstance(race, dict):
        raise ValueError("race required")
    try:
        date = dt.date.fromisoformat(str(race.get("date")))
    except (TypeError, ValueError):
        raise ValueError("race date must be YYYY-MM-DD")
    if date <= dt.date.fromisoformat(today_str):
        raise ValueError("race date must be in the future")
    try:
        distance = float(race.get("distance_km") or 0)
    except (TypeError, ValueError):
        distance = 0
    if distance <= 0:
        raise ValueError("race distance required")
    goal = race.get("goal_time_s")
    return {"name": str(race.get("name") or "Race")[:80],
            "date": date.isoformat(), "distance_km": distance,
            "goal_time_s": int(goal) if goal else None}


def _race_line(race):
    goal = race.get("goal_time_s")
    goal_txt = ""
    if goal:
        h, m = divmod(int(goal) // 60, 60)
        goal_txt = f", goal time {h}:{m:02d}:{int(goal) % 60:02d}"
    return (f"{race['name']}: {race['distance_km']} km on {race['date']}"
            f"{goal_txt}")


_PLAN_RULES = (
    "Plan rules: weeks run Monday-Sunday and week 1 starts next Monday (or "
    "today's week if the race is close). Give DETAILED workouts (using the "
    "workout design format) only for the first 2 weeks; later weeks get "
    "workouts=null and an outline (focus, target_km, long_run_km, summary). "
    "Respect the athlete's current volume and recovery — build gradually, "
    "keep the acute:chronic load ratio in the optimal band, include recovery "
    "weeks roughly every 4th week, and taper before the race. Never prescribe "
    "more than the athlete's data supports."
)


def generate_plan(db_path, settings, race, today_str=None):
    """Create and store a plan toward `race`. Replaces any existing plan."""
    today_str = today_str or dt.date.today().isoformat()
    race = _validate_race(race, today_str)
    prompt = (coach._context_block(db_path, today_str)
              + f"\n\nBuild a training plan for this race — {_race_line(race)}. "
              + _PLAN_RULES
              + "\nIn `reply`, give the athlete the plan's overall strategy in "
                "a few sentences.")
    data = coach._call_claude(settings, [{"role": "user", "content": prompt}],
                              schema=PLAN_RESPONSE_SCHEMA, max_tokens=16000)
    weeks = data.get("weeks") or []
    if not weeks:
        raise RuntimeError("coach returned an empty plan")
    db.save_training_plan(db_path, race, weeks, coach.clean_text(data.get("reply") or ""))
    plan = db.get_training_plan(db_path)
    return {**plan, "reply": plan["notes"]}


def adapt_plan(db_path, settings, today_str=None):
    """Revise the remaining weeks of the stored plan from what actually
    happened; materialize detailed workouts for the upcoming ~2 weeks."""
    today_str = today_str or dt.date.today().isoformat()
    stored = db.get_training_plan(db_path)
    if not stored:
        raise ValueError("no training plan to adapt")
    prompt = (coach._context_block(db_path, today_str)
              + f"\n\nThe athlete is following this training plan toward "
              + _race_line(stored["race"]) + ":\n"
              + json.dumps({"weeks": stored["weeks"]}, separators=(",", ":"))
              + "\n\nReview how the recent week actually went (completed "
                "activities, recovery, load) and return the FULL weeks array "
                "revised: keep past weeks exactly as they are, adjust future "
                "weeks where the data calls for it, and give DETAILED workouts "
                "for the next 2 weeks (workouts=null beyond that). "
              + _PLAN_RULES
              + "\nIn `reply`, tell the athlete what you changed and why "
                "(or that nothing needed changing).")
    data = coach._call_claude(settings, [{"role": "user", "content": prompt}],
                              schema=PLAN_RESPONSE_SCHEMA, max_tokens=16000)
    weeks = data.get("weeks") or []
    if not weeks:
        raise RuntimeError("coach returned an empty plan")
    reply = coach.clean_text(data.get("reply") or "")
    db.save_training_plan(db_path, stored["race"], weeks, stored["notes"])
    plan = db.get_training_plan(db_path)
    return {**plan, "reply": reply}
