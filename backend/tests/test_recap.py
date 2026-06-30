"""Tests for the Today-tab recap summary lines (pure functions, no fabrication)."""
from backend.insights import morning_summary, afternoon_summary

# A clean HRV history (no "today") so the baseline is a round 64.
HRV_HISTORY = [{"hrv_last_night": 64} for _ in range(10)]


def _morning_metrics(**over):
    m = {
        "deep_sleep_s": 5400, "light_sleep_s": 14400, "rem_sleep_s": 7200,  # 7h 30m
        "sleep_score": 75, "recovery_score": 70, "hrv_last_night": 66,
        "training_readiness_score": 63,
    }
    m.update(over)
    return m


# --- morning_summary ---

def test_morning_full_sentence():
    s = morning_summary(_morning_metrics(), HRV_HISTORY)
    assert s.startswith("You slept 7h 30m")
    assert "(sleep score 75)" in s
    assert "recovery is green at 70" in s
    assert "overnight HRV 66ms is near your 64ms baseline" in s
    assert "Training Readiness is 63" in s
    assert s.endswith(".")


def test_morning_empty_when_no_data():
    assert morning_summary({}, []) == ""
    assert morning_summary(None, None) == ""


def test_morning_sleep_only_omits_other_clauses():
    m = {"deep_sleep_s": 3600, "light_sleep_s": 10800, "rem_sleep_s": 5400}  # 5h 30m
    s = morning_summary(m, [])
    assert "You slept 5h 30m" in s
    assert "recovery" not in s.lower()
    assert "hrv" not in s.lower()
    assert "readiness" not in s.lower()


def test_morning_hrv_above_and_below_baseline():
    assert "above your 64ms baseline" in morning_summary(_morning_metrics(hrv_last_night=75), HRV_HISTORY)
    assert "below your 64ms baseline" in morning_summary(_morning_metrics(hrv_last_night=55), HRV_HISTORY)


def test_morning_hrv_without_baseline_states_value_only():
    s = morning_summary(_morning_metrics(), [])  # no history -> no baseline
    assert "overnight HRV is 66ms" in s
    assert "baseline" not in s


def test_morning_recovery_band_words():
    assert "recovery is yellow at 40" in morning_summary(_morning_metrics(recovery_score=40), HRV_HISTORY)
    assert "recovery is red at 20" in morning_summary(_morning_metrics(recovery_score=20), HRV_HISTORY)


# --- afternoon_summary ---

def test_afternoon_full_sentence():
    m = {"body_battery": 43, "steps": 8200, "stress_avg": 26,
         "intensity_weekly_total": 120, "intensity_weekly_goal": 150}
    s = afternoon_summary(m, [])
    assert s.startswith("Body Battery is at 43")
    assert "you're at 8,200 steps" in s
    assert "average stress is 26" in s
    assert "120 of 150 weekly intensity minutes" in s
    assert s.endswith(".")


def test_afternoon_empty_when_no_data():
    assert afternoon_summary({}, []) == ""
    assert afternoon_summary(None, None) == ""


def test_afternoon_partial_only_present_clauses():
    s = afternoon_summary({"steps": 5000}, [])
    assert s == "You're at 5,000 steps."
