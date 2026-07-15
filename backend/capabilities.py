"""Watch-capability detection.

Distribution goal: ONE build that shows only the tabs/cards a user's watch
actually reports. Entry-level watches (no HRV / Training Readiness / VO2max /
training load, etc.) hide those tabs and cards; a Forerunner 970 shows them all.

Rules (these implement the brief's hide-vs-"No data" distinction):

- A category is **supported** if any stored data has *ever* shown it. This is
  **sticky**: once seen it stays unlocked. That is what keeps a card visible on
  a one-off day with no data (it shows "No data", not hidden) and lets an
  upgraded watch unlock categories automatically on the next sync.
- We only treat a category as **unsupported** (and hide it) once the profile is
  **ready** — i.e. we have observed enough full-fetch days to trust a negative.
  Before that, everything shows (never hide prematurely on sparse early data).

Persisted as JSON in the user-data directory (no SQLite tables / migrations).
"""
import datetime as dt
import json
from pathlib import Path

PROFILE_VERSION = 1

# category -> daily_metrics fields whose non-null presence proves support.
DAILY_CATEGORY_FIELDS = {
    "hrv": ["hrv_last_night", "hrv_status"],
    "rhr": ["rhr"],
    "sleep": ["sleep_score", "deep_sleep_s", "light_sleep_s", "rem_sleep_s"],
    "sleep_detail": ["sleep_need_actual", "sleep_need_baseline", "sleep_deep_score",
                     "sleep_rem_score", "sleep_light_score", "sleep_restlessness_score",
                     "awake_count"],
    "respiration": ["resp_waking", "resp_sleep"],
    "body_battery": ["body_battery"],
    "stress": ["stress_avg"],
    "training_readiness": ["training_readiness_score", "tr_sleep_factor",
                           "tr_recovery_factor", "tr_acwr_factor", "tr_hrv_factor",
                           "tr_stress_factor"],
    "training_load_acwr": ["acwr_ratio", "acute_load", "chronic_load",
                           "training_status_label", "load_aerobic_low",
                           "load_aerobic_high", "load_anaerobic"],
    "intensity_minutes": ["intensity_moderate", "intensity_vigorous",
                          "intensity_weekly_total"],
    "steps_floors": ["steps", "floors_ascended", "distance_m", "active_calories"],
    "vo2max": ["vo2max"],
    # v3.9
    "spo2": ["spo2_avg", "spo2_lowest", "spo2_avg_sleep"],
    "hydration": ["hydration_ml", "hydration_goal_ml", "sweat_loss_ml"],
    "recovery_time": ["recovery_time_min"],
    "skin_temp": ["skin_temp_dev_c"],
}

# category -> perf_metrics fields (perf reflects current/all-time values).
PERF_CATEGORY_FIELDS = {
    "vo2max": ["vo2max", "vo2max_cycling", "fitness_age"],
    "race_predictions": ["race_5k", "race_10k", "race_hm", "race_marathon"],
    "endurance": ["endurance_score", "endurance_class"],
    "acclimation": ["heat_acclimation", "altitude_acclimation"],
    # v3.9
    "running_tolerance": ["running_tolerance_load", "running_tolerance_ceiling"],
    "hill_score": ["hill_score"],
    "lactate_threshold": ["lt_hr", "lt_power"],
    "body_weight": ["body_weight_g"],
}

ALL_CATEGORIES = sorted(
    set(DAILY_CATEGORY_FIELDS) | set(PERF_CATEGORY_FIELDS)
    | {"personal_records", "activities"})

# Fields only a full fetch_day sets (the cheap HRV/RHR backfill does not), used
# to count how many full-coverage days we have observed.
FULL_FETCH_MARKERS = ["steps", "stress_avg", "sleep_score", "body_battery",
                      "training_readiness_score"]


def _present(row, fields):
    return any((row or {}).get(f) is not None for f in fields)


def compute_profile(daily_rows, perf_rows, records, activities,
                    prev=None, ready_days=3):
    """Build the capability profile from stored data, sticky-merged with the
    previous profile. `daily_rows` are daily_metrics dicts over the window;
    `perf_rows` is a list of perf dicts (0 or more); `records`/`activities` are
    the stored lists."""
    prev_sup = (prev or {}).get("supported", {})
    supported = {}

    for cat, fields in DAILY_CATEGORY_FIELDS.items():
        supported[cat] = any(_present(r, fields) for r in daily_rows)
    for cat, fields in PERF_CATEGORY_FIELDS.items():
        seen = any(_present(r, fields) for r in (perf_rows or []))
        supported[cat] = supported.get(cat, False) or seen
    supported["personal_records"] = bool(records)
    supported["activities"] = bool(activities)

    # sticky: once supported, always supported (never re-hide an unlocked card)
    for cat in ALL_CATEGORIES:
        supported[cat] = bool(supported.get(cat, False) or prev_sup.get(cat, False))

    observed_days = sum(1 for r in daily_rows if _present(r, FULL_FETCH_MARKERS))
    return {
        "version": PROFILE_VERSION,
        "supported": supported,
        "ready": observed_days >= ready_days,
        "observed_days": observed_days,
    }


def default_profile():
    """Used before any profile exists: show everything, not yet ready."""
    return {
        "version": PROFILE_VERSION,
        "supported": {c: True for c in ALL_CATEGORIES},
        "ready": False,
        "observed_days": 0,
        "device_name": None,
        "baseline_fetch_version": 0,
    }


def load_profile(path):
    p = Path(path)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def save_profile(path, profile):
    profile = dict(profile)
    profile["updated"] = dt.datetime.now().isoformat()
    Path(path).write_text(json.dumps(profile, indent=2))
