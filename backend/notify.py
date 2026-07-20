# v5.0 D1: morning-sync notification payload.
#
# The backend only *describes* the notification; Electron's main process polls
# /api/notify/last-sync and decides when to show it (once per date). Keeping
# the OS-notification side in Electron means the frozen backend stays headless.

from backend import db
from backend import recovery as rec

_MAX_LINE = 140


def _first_sentence(text):
    if not text:
        return None
    s = text.strip().split("\n")[0]
    for stop in (". ", "! ", "? "):
        i = s.find(stop)
        if i != -1:
            s = s[: i + 1]
            break
    s = s.strip()
    if len(s) > _MAX_LINE:
        s = s[:_MAX_LINE] + "…"
    return s or None


def build_sync_notification(db_path, settings):
    """Payload for the morning notification, or None when it shouldn't fire
    (opted out, or no recovery score yet — never fabricate)."""
    if not settings.get("morning_notification"):
        return None
    day = db.get_primary_day(db_path)
    score = day.get("recovery_score") if day else None
    if score is None:
        return None
    band = rec.recovery_band(score,
                             green=settings.get("recovery_green", 67),
                             amber=settings.get("recovery_amber", 34))
    brief = db.get_coach_brief(db_path, day["date"])
    from backend import plan
    session = plan.todays_session(db_path, day["date"])
    return {
        "date": day["date"],
        "recovery_score": score,
        "band": band,
        "line": _first_sentence(brief["text"]) if brief else None,
        "planned": session["name"] if session else None,
    }
