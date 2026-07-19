"""Custom recovery & strain scores. NOT Garmin or Whoop metrics.

Recovery (v5.1, multi-factor — modeled on Whoop's documented factor set; the
real formula is proprietary): a weighted blend of per-factor z-scores against
the athlete's own rolling baseline, pushed through the same sigmoid as always.

    Block weights (renormalized over whichever blocks have data today):
      autonomic 0.60  — z_hrv & inverted z_rhr, split by the user's hrv_weight
                        (default 0.7/0.3 -> effective 0.42/0.18). REQUIRED:
                        no HRV or RHR -> no score, exactly as before.
      sleep     0.25  — 60% duration-vs-need (Garmin sleep need) +
                        40% quality (Garmin sleep score)
      resp      0.07  — overnight respiration vs baseline, inverted (elevated
                        breathing is an early illness flag); upside capped +1
      temp      0.04  — skin-temperature deviation, penalty-only (either
                        direction beyond 0.4 C drags the score down)
      spo2      0.04  — sleep SpO2 vs baseline, penalty-only (drops hurt,
                        high readings never inflate)

    z      = sum(w_i * z_i)          # weights renormalized over present blocks
    score  = round(100 / (1 + exp(-(1.0*z + 0.3))))   # neutral day ~58

With no extra factors available the formula reduces EXACTLY to the historical
2-factor HRV/RHR blend, so old scores stay comparable and sparse days never
fabricate anything. Color bands: green >=67, yellow 34-66, red <=33 (Whoop's
published cutoffs), user-tunable.
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


DEFAULT_HRV_WEIGHT = 0.7   # HRV share within the autonomic block

# Block weights (see module docstring). Autonomic is required; the rest join
# only when their data exists, with weights renormalized over present blocks.
BLOCK_WEIGHTS = {"autonomic": 0.60, "sleep": 0.25, "resp": 0.07,
                 "temp": 0.04, "spo2": 0.04}


def _hist_stats(hist, need, std_floor):
    """(mean, std) of a history with a std floor, or None if too short."""
    vals = [v for v in (hist or []) if v is not None]
    if len(vals) < need:
        return None
    return mean(vals), max(pstdev(vals), std_floor)


def _sleep_z(extras):
    """0.6 * duration-vs-need + 0.4 * quality; either half alone if the other
    is missing; None when the block has no data at all."""
    total_s = extras.get("sleep_total_s")
    need_min = extras.get("sleep_need_min")
    score = extras.get("sleep_score")
    z_dur = None
    if total_s is not None and need_min:
        perf = (total_s / 60.0) / need_min
        z_dur = _clamp((perf - 0.9) / 0.12, -3, 3)   # 90% of need = neutral
    z_qual = None if score is None else _clamp((score - 75) / 10.0, -3, 3)
    if z_dur is not None and z_qual is not None:
        return 0.6 * z_dur + 0.4 * z_qual
    return z_dur if z_dur is not None else z_qual


def recovery_explanation(hrv_today, rhr_today, hrv_hist, rhr_hist, min_days=None,
                         hrv_weight=DEFAULT_HRV_WEIGHT, extras=None):
    """Why the score: every contributing factor vs the personal baseline as a
    z-score (positive pushes recovery UP). Same guards as recovery_score —
    returns None whenever the score would be None. `extras` carries the
    optional factor data (sleep/resp/temp/spo2); see recovery_score."""
    need = BASELINE_MIN_DAYS if min_days is None else min_days
    hrv_hist = [h for h in (hrv_hist or []) if h is not None]
    rhr_hist = [r_ for r_ in (rhr_hist or []) if r_ is not None]
    if hrv_today is None or rhr_today is None:
        return None
    if len(hrv_hist) < need or len(rhr_hist) < need:
        return None
    x = extras or {}

    hw = _clamp(hrv_weight, 0.0, 1.0)
    hrv_mean, rhr_mean = mean(hrv_hist), mean(rhr_hist)
    hrv_std = max(pstdev(hrv_hist), 0.05 * hrv_mean) if hrv_mean else max(pstdev(hrv_hist), 1.0)
    rhr_std = max(pstdev(rhr_hist), 2.0)
    z_hrv = _clamp((hrv_today - hrv_mean) / hrv_std, -3, 3)
    z_rhr = _clamp(-(rhr_today - rhr_mean) / rhr_std, -3, 3)

    # Optional blocks — z per block, None = no data (block drops out).
    blocks = {"autonomic": hw * z_hrv + (1 - hw) * z_rhr}
    out = {
        "hrv": {"today": hrv_today, "baseline": round(hrv_mean, 1), "z": round(z_hrv, 2)},
        "rhr": {"today": rhr_today, "baseline": round(rhr_mean, 1), "z": round(z_rhr, 2)},
    }

    z_sleep = _sleep_z(x)
    if z_sleep is not None:
        blocks["sleep"] = z_sleep
        out["sleep"] = {
            "total_min": None if x.get("sleep_total_s") is None else int(x["sleep_total_s"] / 60),
            "need_min": x.get("sleep_need_min"), "score": x.get("sleep_score"),
            "z": round(z_sleep, 2)}

    resp_stats = _hist_stats(x.get("resp_hist"), need, 0.5)
    if x.get("resp_today") is not None and resp_stats:
        rm, rs = resp_stats
        z_resp = _clamp(-(x["resp_today"] - rm) / rs, -3, 1)   # upside capped
        blocks["resp"] = z_resp
        out["resp"] = {"today": x["resp_today"], "baseline": round(rm, 1),
                       "z": round(z_resp, 2)}

    dev = x.get("skin_temp_dev")
    if dev is not None:
        z_temp = -_clamp((abs(dev) - 0.4) / 0.4, 0, 3)         # penalty-only
        blocks["temp"] = z_temp
        out["temp"] = {"dev_c": round(dev, 2), "z": round(z_temp, 2)}

    spo2_stats = _hist_stats(x.get("spo2_hist"), need, 1.0)
    if x.get("spo2_today") is not None and spo2_stats:
        sm, ss = spo2_stats
        z_spo2 = _clamp(min(0.0, (x["spo2_today"] - sm) / ss), -3, 0)  # penalty-only
        blocks["spo2"] = z_spo2
        out["spo2"] = {"today": x["spo2_today"], "baseline": round(sm, 1),
                       "z": round(z_spo2, 2)}

    # Renormalize block weights over what's present; report effective
    # per-factor weights (autonomic split into its hrv/rhr shares).
    wsum = sum(BLOCK_WEIGHTS[b] for b in blocks)
    norm = {b: BLOCK_WEIGHTS[b] / wsum for b in blocks}
    weights = {"hrv": round(norm["autonomic"] * hw, 2),
               "rhr": round(norm["autonomic"] * (1 - hw), 2)}
    for b in ("sleep", "resp", "temp", "spo2"):
        if b in blocks:
            weights[b] = round(norm[b], 2)
    out["weights"] = weights
    out["_z"] = round(sum(norm[b] * blocks[b] for b in blocks), 4)
    return out


def recovery_score(hrv_today, rhr_today, hrv_hist, rhr_hist, min_days=None,
                   hrv_weight=DEFAULT_HRV_WEIGHT, extras=None):
    """extras (all optional; missing pieces simply drop their block):
    sleep_total_s, sleep_need_min, sleep_score, resp_today, resp_hist,
    skin_temp_dev, spo2_today, spo2_hist."""
    ex = recovery_explanation(hrv_today, rhr_today, hrv_hist, rhr_hist,
                              min_days, hrv_weight, extras)
    if ex is None:
        return None
    score = 100 / (1 + math.exp(-(1.0 * ex["_z"] + 0.3)))
    return int(round(min(100, max(0, score))))


def recovery_band(score, green=67, amber=34):
    if score is None:
        return None
    if score >= green:
        return "green"
    if score >= amber:
        return "yellow"
    return "red"


STEP_FLOOR = 3000   # steps below this are sedentary life, not strain


def _edwards_trimp(zones):
    """Edwards TRIMP from Garmin HR-zone times: minutes-in-zone * zone number
    (zones 1-5). Scale is comparable to Garmin's EPOC training load, so it
    slots into the same saturating map."""
    total = 0.0
    for z in zones or []:
        n, secs = z.get("zoneNumber"), z.get("secsInZone")
        if n and secs:
            total += (secs / 60.0) * float(n)
    return total or None


def strain_breakdown(activities_for_day, day_metrics=None, zones_by_activity=None):
    """All-day strain, split into its components (for the detail panel):

    - workout: per activity, the most precise available load —
        1. Garmin training_load (EPOC-based)
        2. Edwards TRIMP from the activity's stored HR-zone times
        3. duration_minutes * avg_hr/100 (last resort)
    - daily:   intensity minutes (moderate + 2*vigorous, Garmin's weighting)
               + steps ABOVE a 3k sedentary floor (2.5 per 1000)
               + 0.5 per floor ascended — counted at **50% on workout days**,
               since workouts already contain their own steps/intensity
               (overlap damping).
    total maps to 0-100 via 1 - exp(-total/150): rest day ~2, active 12k-step
    day ~25-35, run day ~55-70. Each component counts only when its data
    exists; returns None only when NO component has data (never fabricated).
    """
    acts = activities_for_day or []
    zones_by_activity = zones_by_activity or {}
    workout = 0.0
    used = False
    for a in acts:
        load = a.get("training_load")
        if load is None:
            load = _edwards_trimp(zones_by_activity.get(a.get("activity_id")))
        if load is None:
            dur = a.get("duration_s")
            hr = a.get("avg_hr")
            if dur and hr:
                load = (dur / 60.0) * (hr / 100.0)
        if load:
            workout += load
            used = True
    m = day_metrics or {}
    daily_raw = 0.0
    mod, vig = m.get("intensity_moderate"), m.get("intensity_vigorous")
    if mod is not None or vig is not None:
        daily_raw += (mod or 0) + 2.0 * (vig or 0)
        used = True
    if m.get("steps") is not None:
        daily_raw += 2.5 * (max(0, m["steps"] - STEP_FLOOR) / 1000.0)
        used = True
    if m.get("floors_ascended") is not None:
        daily_raw += 0.5 * m["floors_ascended"]
        used = True
    if not used:
        return None
    daily = daily_raw * (0.5 if workout > 0 else 1.0)
    total = workout + daily
    score = 100 * (1 - math.exp(-total / 150.0))   # saturating
    return {"workout": round(workout, 1), "daily": round(daily, 1),
            "total": round(total, 1),
            "score": int(round(min(100, max(0, score))))}


def strain_score(activities_for_day, day_metrics=None, zones_by_activity=None):
    b = strain_breakdown(activities_for_day, day_metrics, zones_by_activity)
    return None if b is None else b["score"]
