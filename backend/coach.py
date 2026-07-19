"""AI coach: daily brief, chat, and structured workout design via Claude.

Privacy contract (opt-in feature, off by default):
- The ONLY data sent to Anthropic is the compact context from build_context():
  recent daily metrics, activities, journal tags, and performance numbers.
  Never credentials, tokens, email, or precise location.
- The API key lives in settings.json (like the access PIN) and is never logged.
- Responses are constrained to a JSON schema so the coach can only ever reply
  with text plus an optional structured workout — which the user reviews in
  the app before anything is pushed to Garmin.
"""
import json
import logging
import re

import backend.db as db

log = logging.getLogger("coach")

# The model occasionally double-escapes inside the JSON string, which leaves
# literal "\n" / "—" artifacts in the decoded text. Fix them up.
_UNICODE_ESC = re.compile(r"\\u([0-9a-fA-F]{4})")


def clean_text(text):
    if not text:
        return text
    text = _UNICODE_ESC.sub(lambda m: chr(int(m.group(1), 16)), text)
    return text.replace("\\n", "\n").replace("\\t", " ")

CONTEXT_DAYS = 30
CHAT_HISTORY_TURNS = 20

# Daily fields worth the coach's attention (compact: omit nulls per day).
_CONTEXT_FIELDS = [
    "recovery_score", "strain_score", "sleep_score", "hrv_last_night",
    "hrv_status", "rhr", "training_readiness_score", "recovery_time_min",
    "sleep_need_actual", "sleep_need_baseline", "nap_time_s", "resp_sleep",
    "spo2_avg", "skin_temp_dev_c", "stress_avg", "body_battery", "steps",
    "acwr_ratio", "acute_load", "chronic_load", "training_status_label",
]

_PERF_FIELDS = ["vo2max", "fitness_age", "race_5k", "race_10k", "race_hm",
                "race_marathon", "endurance_score", "hill_score", "lt_hr",
                "lt_power", "running_tolerance_load",
                "running_tolerance_ceiling", "body_weight_g",
                "heat_acclimation", "altitude_acclimation"]


def build_context(db_path):
    """Compact JSON-able snapshot of the athlete. This is the complete set of
    data that ever leaves the machine when the coach is used."""
    days = []
    for r in db.get_trends(db_path, CONTEXT_DAYS):
        d = {k: r[k] for k in _CONTEXT_FIELDS if r.get(k) is not None}
        if d:
            d["date"] = r["date"]
            days.append(d)
    acts = [{k: a[k] for k in ("date", "type", "duration_s", "avg_hr",
                               "training_load", "aerobic_te", "anaerobic_te")
             if a.get(k) is not None}
            for a in db.get_recent_activities(db_path, 20)]
    perf = db.get_latest_perf(db_path) or {}
    journal = [{"date": j["date"],
                "tags": [t for t, v in (j.get("tags") or {}).items() if v],
                "note": (j.get("note") or "")[:200]}
               for j in db.get_journal_range(db_path, 14)]
    return {
        "days": days,
        "recent_activities": acts,
        "performance": {k: perf.get(k) for k in _PERF_FIELDS
                        if perf.get(k) is not None},
        "journal": [j for j in journal if j["tags"] or j["note"]],
    }


# ---- structured output schema -------------------------------------------
# Structured outputs don't allow recursion, so repeats nest plain steps only.

_STEP = {
    "type": "object",
    "properties": {
        "kind": {"type": "string",
                 "enum": ["warmup", "interval", "recovery", "cooldown", "rest"]},
        "duration_type": {"type": "string", "enum": ["time", "distance"]},
        "duration_value": {"type": "number",
                           "description": "seconds if time, meters if distance"},
        "target_type": {"type": "string", "enum": ["none", "pace", "heart_rate"]},
        "target_min": {"anyOf": [{"type": "number"}, {"type": "null"}],
                       "description": "pace: FASTEST pace as seconds per km; heart_rate: min bpm"},
        "target_max": {"anyOf": [{"type": "number"}, {"type": "null"}],
                       "description": "pace: SLOWEST pace as seconds per km; heart_rate: max bpm"},
        "description": {"type": "string"},
    },
    "required": ["kind", "duration_type", "duration_value", "target_type",
                 "target_min", "target_max", "description"],
    "additionalProperties": False,
}

_REPEAT = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["repeat"]},
        "count": {"type": "integer"},
        "steps": {"type": "array", "items": _STEP},
    },
    "required": ["kind", "count", "steps"],
    "additionalProperties": False,
}

WORKOUT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "suggested_date": {"type": "string",
                           "description": "YYYY-MM-DD the workout is intended for"},
        "rationale": {"type": "string",
                      "description": "one sentence: why this workout given the athlete's data"},
        "steps": {"type": "array", "items": {"anyOf": [_STEP, _REPEAT]}},
    },
    "required": ["name", "suggested_date", "rationale", "steps"],
    "additionalProperties": False,
}

_HIGHLIGHT = {
    "type": "object",
    "properties": {
        "label": {"type": "string", "description": "short metric name, e.g. 'ACWR'"},
        "value": {"type": "string", "description": "the number/short value, e.g. '1.4'"},
        "tone": {"type": "string", "enum": ["good", "warn", "bad", "neutral"]},
    },
    "required": ["label", "value", "tone"],
    "additionalProperties": False,
}

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string",
                  "description": "the coach's message to the athlete"},
        "highlights": {"type": "array", "items": _HIGHLIGHT,
                       "description": "3-6 key numbers behind the reply"},
        "workout": {"anyOf": [WORKOUT_SCHEMA, {"type": "null"}]},
    },
    "required": ["reply", "highlights", "workout"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are a personal running and fitness coach embedded in the athlete's \
recovery dashboard. You receive their real Garmin data as JSON: daily recovery/strain/sleep \
scores, HRV, training readiness, recovery time, running tolerance (impact load vs ceiling), \
lactate threshold (lt_hr in bpm, lt_power in watts), race predictions (seconds), VO2max, \
recent activities, and their journal.

Rules:
- Ground every statement in the provided data. NEVER invent numbers. If data is missing, say so.
- Be specific and quantitative: cite the athlete's actual values when making a point.
- Balance training and recovery: respect low recovery scores, high recovery_time_min, sleep \
debt, and running tolerance headroom when advising.
- Paces: derive from their race predictions and lactate threshold. Express as seconds per km \
in workout targets (e.g. 4:30/km = 270).
- Heart rate targets in bpm; their lactate threshold HR is the anchor for hard efforts.
- Only include a workout object when the athlete asks for a workout or clearly wants one; \
otherwise set workout to null. Workouts are for RUNNING only (outdoor or treadmill).
- Workout structure: warmup and cooldown always; intervals with explicit pace (sec/km, \
target_min = fastest, target_max = slowest) or heart_rate (bpm) targets; recovery steps \
between repeats. Keep it executable on a Garmin watch.
- Tone: knowledgeable, direct, encouraging.
- Formatting: make the reply scannable, never a wall of text. Short paragraphs (2-3 sentences), \
blank line between them. Use "- " bullet lists for enumerations (causes, recommendations, the \
week's plan). Use **bold** for the few numbers or phrases that matter most. No headers, no \
tables, no other markdown.
- highlights: 3-6 chips with the key numbers behind your reply (label + value + tone: good = \
positive signal, warn = caution, bad = negative, neutral = informational). Example: \
{"label": "ACWR", "value": "1.4", "tone": "warn"}."""


_TONE = {
    "balanced": "",
    "concise": "Style: be brief — a couple of sentences plus a short bullet list at "
               "most. No preamble, no restating the question.",
    "detailed": "Style: be thorough — explain the physiology and the reasoning "
                "behind each recommendation, not just the conclusion.",
    "tough": "Style: be a demanding, no-excuses coach. Push the athlete and call out "
             "choices that hurt recovery (alcohol, skipped rest, overreaching) directly.",
    "encouraging": "Style: be warm and motivating. Lead with what's going well before "
                   "any critique, and frame advice positively.",
}


def _tone_addendum(settings):
    """A small, per-user system block appended after the cached base prompt so
    tone/workout-default preferences apply without invalidating its cache."""
    parts = []
    tone = _TONE.get(settings.get("coach_tone") or "balanced")
    if tone:
        parts.append(tone)
    warm = settings.get("coach_warmup_default_s")
    if warm:
        parts.append(f"Default warmup length ~{round(warm / 60)} min unless the "
                     "session calls for otherwise.")
    pref = settings.get("coach_target_pref")
    if pref == "pace":
        parts.append("Prefer pace (sec/km) targets for intervals.")
    elif pref == "hr":
        parts.append("Prefer heart-rate (bpm) targets for intervals.")
    return "\n".join(parts)


def is_configured(settings):
    return bool(settings.get("coach_enabled") and settings.get("anthropic_api_key"))


def _call_claude(settings, messages, schema=None, max_tokens=4000):
    """One structured call to Claude. Returns the parsed dict for `schema`
    (default: the brief/chat RESPONSE_SCHEMA). Import is local so the app
    still runs if the package were missing."""
    import anthropic
    client = anthropic.Anthropic(api_key=settings["anthropic_api_key"])
    system = [{"type": "text", "text": SYSTEM_PROMPT,
               "cache_control": {"type": "ephemeral"}}]
    addendum = _tone_addendum(settings)
    if addendum:
        system.append({"type": "text", "text": addendum})
    resp = client.messages.create(
        model=settings.get("coach_model") or "claude-sonnet-5",
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        system=system,
        messages=messages,
        output_config={"format": {"type": "json_schema",
                                  "schema": schema or RESPONSE_SCHEMA}},
    )
    if resp.stop_reason == "refusal":
        if schema is not None:
            raise RuntimeError("coach refused the request")
        return {"reply": "The coach couldn't answer that request.",
                "highlights": [], "workout": None}
    text = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)
    if "reply" in data:
        data["reply"] = clean_text(data.get("reply") or "")
    if schema is None:
        data.setdefault("highlights", [])
    return data


def _context_block(db_path, today_str):
    return (f"Today is {today_str}. Athlete data (JSON):\n"
            + json.dumps(build_context(db_path), separators=(",", ":")))


def daily_brief(db_path, settings, today_str, force=False):
    """The coach's morning brief for `today_str`, cached per date so Claude is
    called at most once a day (unless the user explicitly regenerates)."""
    if not force:
        cached = db.get_coach_brief(db_path, today_str)
        if cached:
            return {**cached, "cached": True}
    prompt = (_context_block(db_path, today_str)
              + "\n\nWrite today's morning brief: how the athlete is doing, what "
                "stands out, and what today's training should look like. If a "
                "structured run makes sense today, include it as the workout.")
    data = _call_claude(settings, [{"role": "user", "content": prompt}])
    db.upsert_coach_brief(db_path, today_str, data["reply"], data.get("workout"),
                          data.get("highlights"))
    return {**db.get_coach_brief(db_path, today_str), "cached": False}


def chat(db_path, settings, message, today_str):
    """One chat turn. History is persisted; context is injected fresh each
    call (the API is stateless)."""
    history = db.get_coach_chat(db_path, CHAT_HISTORY_TURNS)
    messages = [{"role": "user", "content": _context_block(db_path, today_str)},
                {"role": "assistant", "content": json.dumps(
                    {"reply": "Understood — I have your current data. What would you like to work on?",
                     "workout": None})}]
    for h in history:
        content = h["content"]
        if h["role"] == "assistant":
            content = json.dumps({"reply": content, "workout": None})
        messages.append({"role": h["role"], "content": content})
    messages.append({"role": "user", "content": message})
    data = _call_claude(settings, messages)
    db.add_coach_chat(db_path, "user", message, None)
    db.add_coach_chat(db_path, "assistant", data["reply"], data.get("workout"),
                      data.get("highlights"))
    return data
