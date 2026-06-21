"""Custom recovery & strain scores. NOT Garmin or Whoop metrics.

Recovery formula (approximation of Whoop's documented behavior — HRV-dominant,
RHR secondary, compared to a personal 30-day baseline; the real Whoop formula
is proprietary and not public):

    hrv_std = max(std(hrv_hist), 0.05 * mean(hrv_hist))   # 5%-of-mean floor
    rhr_std = max(std(rhr_hist), 2.0)                      # ~2 bpm floor
    z_hrv     = clamp((hrv_today - mean(hrv_hist)) / hrv_std, -3, 3)
    z_rhr_inv = clamp(-(rhr_today - mean(rhr_hist)) / rhr_std, -3, 3)
    z         = 0.7 * z_hrv + 0.3 * z_rhr_inv             # HRV-dominant
    score     = round(100 / (1 + exp(-(1.0*z + 0.3))))    # +0.3 centers neutral ~58

Color bands match Whoop's published cutoffs: green >=67, yellow 34-66, red <=33.
Requires >= BASELINE_MIN_DAYS of history; otherwise returns None ("building
baseline"). Today's HRV or RHR missing also returns None (never fabricate).
"""
import math
from statistics import mean, pstdev
from backend.config import BASELINE_MIN_DAYS


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def recovery_score(hrv_today, rhr_today, hrv_hist, rhr_hist):
    hrv_hist = [h for h in (hrv_hist or []) if h is not None]
    rhr_hist = [r_ for r_ in (rhr_hist or []) if r_ is not None]
    if hrv_today is None or rhr_today is None:
        return None
    if len(hrv_hist) < BASELINE_MIN_DAYS or len(rhr_hist) < BASELINE_MIN_DAYS:
        return None

    hrv_mean, rhr_mean = mean(hrv_hist), mean(rhr_hist)
    hrv_std = max(pstdev(hrv_hist), 0.05 * hrv_mean) if hrv_mean else max(pstdev(hrv_hist), 1.0)
    rhr_std = max(pstdev(rhr_hist), 2.0)

    z_hrv = _clamp((hrv_today - hrv_mean) / hrv_std, -3, 3)
    z_rhr_inv = _clamp(-(rhr_today - rhr_mean) / rhr_std, -3, 3)
    z = 0.7 * z_hrv + 0.3 * z_rhr_inv
    score = 100 / (1 + math.exp(-(1.0 * z + 0.3)))
    return int(round(min(100, max(0, score))))


def recovery_band(score):
    if score is None:
        return None
    if score >= 67:
        return "green"
    if score >= 34:
        return "yellow"
    return "red"


def strain_score(activities_for_day):
    """Custom 0-100 strain from the day's activity training load.

    Sum each activity's training_load (fallback: duration_minutes * (avg_hr/100)
    when training_load is missing), then map to 0-100 via a saturating curve
    (1 - exp(-total/150): a daily load of ~345 maps to ~90). Returns None when
    there are no activities with usable data.
    """
    acts = activities_for_day or []
    total = 0.0
    used = False
    for a in acts:
        load = a.get("training_load")
        if load is None:
            dur = a.get("duration_s")
            hr = a.get("avg_hr")
            if dur and hr:
                load = (dur / 60.0) * (hr / 100.0)
        if load:
            total += load
            used = True
    if not used:
        return None
    score = 100 * (1 - math.exp(-total / 150.0))   # saturating
    return int(round(min(100, max(0, score))))
