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


def min_days_for_window(window):
    """History required before scoring: half the baseline window, at least 4
    days, capped at BASELINE_MIN_DAYS. Keeps short windows usable (a 7-day
    window needs 4 days, not an impossible 14) without loosening long ones."""
    return min(BASELINE_MIN_DAYS, max(4, int(window) // 2))


def recovery_score(hrv_today, rhr_today, hrv_hist, rhr_hist, min_days=None):
    need = BASELINE_MIN_DAYS if min_days is None else min_days
    hrv_hist = [h for h in (hrv_hist or []) if h is not None]
    rhr_hist = [r_ for r_ in (rhr_hist or []) if r_ is not None]
    if hrv_today is None or rhr_today is None:
        return None
    if len(hrv_hist) < need or len(rhr_hist) < need:
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


def strain_score(activities_for_day, day_metrics=None):
    """Custom 0-100 all-day strain: workout load PLUS daily-life load, so a
    no-workout day still scores from wear data (Whoop-style).

    Components (each counts only when its data exists — never fabricated):
    - workouts: sum of training_load (fallback duration_minutes * avg_hr/100)
    - intensity minutes: moderate + 2*vigorous (Garmin's own weighting)
    - steps: 2.5 per 1000 steps
    Total maps to 0-100 via the saturating curve 1 - exp(-total/150): a lazy
    2k-step day ~ 3, an active 12k-step day ~ 25-35, a run day 45+. Workouts
    also raise steps/intensity, so components overlap slightly — an accepted
    approximation for a wellness estimate. Returns None only when NO component
    has data for the day.
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
    m = day_metrics or {}
    mod, vig = m.get("intensity_moderate"), m.get("intensity_vigorous")
    if mod is not None or vig is not None:
        total += (mod or 0) + 2.0 * (vig or 0)
        used = True
    if m.get("steps") is not None:
        total += 2.5 * (m["steps"] / 1000.0)
        used = True
    if not used:
        return None
    score = 100 * (1 - math.exp(-total / 150.0))   # saturating
    return int(round(min(100, max(0, score))))
