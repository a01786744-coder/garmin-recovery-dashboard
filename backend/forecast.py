"""v5.3 F1: tomorrow-morning recovery forecast.

A transparent heuristic (NOT a Garmin/Whoop metric, NOT ML) that projects
tomorrow's recovery from today's state — how hard you went, your accumulated
sleep debt, how ramped your training load is, and which way HRV is trending.
Everything comes from already-stored data; no Garmin or Claude calls.

The forecast anchors on your recent recovery norm and nudges it by each driver,
then brackets the result by tonight's sleep (which you haven't had yet): a poor
night pulls toward `low`, a full night toward `high`. Returns None when there
isn't enough recent history to anchor on (never fabricated).
"""
from statistics import mean

from backend import insights
from backend.recovery import recovery_band


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _recent(vals, n):
    xs = [v for v in vals if v is not None]
    return xs[-n:] if xs else []


def _hrv_trend_points(rows):
    """Recent HRV direction as a recovery-point nudge (+/-), 0 if unclear."""
    hrv = [r.get("hrv_last_night") for r in rows]
    recent = _recent(hrv, 3)
    prior = [h for h in hrv[:-3] if h is not None]
    if len(recent) < 2 or len(prior) < 2:
        return 0.0
    diff = mean(recent) - mean(prior)
    base = mean(prior) or 1.0
    return _clamp((diff / base) * 60.0, -6.0, 6.0)   # ~10% swing => 6 pts


# Poor vs full sleep tonight, as recovery-point offsets around the point estimate.
SLEEP_LOW, SLEEP_HIGH = -9.0, 7.0


def forecast_recovery(daily, green=67, amber=34):
    rows = (daily or [])[-14:]
    rec_hist = _recent([r.get("recovery_score") for r in rows], 7)
    if len(rec_hist) < 2:
        return None                       # nothing to anchor on
    today = rows[-1]

    base = mean(rec_hist)
    drivers = []

    strain = today.get("strain_score")
    if strain is not None:
        eff = -0.20 * max(0.0, strain - 35.0)
        if strain >= 55:
            drivers.append({"label": "Today's strain", "effect": round(eff, 1),
                            "detail": "hard day — expect a dip"})
        elif eff < -0.5:
            drivers.append({"label": "Today's strain", "effect": round(eff, 1),
                            "detail": "moderate load"})
        base += eff

    debt = insights.sleep_debt(rows)
    if debt and debt["days7"] >= 3:
        hours = debt["debt7_min"] / 60.0
        eff = _clamp(-hours * 1.5, -12.0, 4.0)   # surplus can help a little
        if abs(eff) >= 1:
            drivers.append({"label": "Sleep debt", "effect": round(eff, 1),
                            "detail": f"{'+' if hours < 0 else ''}{-round(hours, 1)}h vs need this week"
                            if hours < 0 else f"{round(hours, 1)}h short this week"})
            base += eff

    acwr = today.get("acwr_ratio")
    if acwr is not None and acwr > 1.3:
        eff = _clamp(-8.0 * (acwr - 1.3) / 0.2, -12.0, 0.0)
        drivers.append({"label": "Load ramp (ACWR)", "effect": round(eff, 1),
                        "detail": f"ratio {round(acwr, 2)} — ramping fast"})
        base += eff

    hrv_eff = _hrv_trend_points(rows)
    if abs(hrv_eff) >= 1:
        drivers.append({"label": "HRV trend", "effect": round(hrv_eff, 1),
                        "detail": "rising" if hrv_eff > 0 else "sliding"})
        base += hrv_eff

    point = _clamp(base, 0.0, 100.0)
    low = _clamp(point + SLEEP_LOW, 0.0, 100.0)
    high = _clamp(point + SLEEP_HIGH, 0.0, 100.0)
    drivers.sort(key=lambda d: abs(d["effect"]), reverse=True)

    return {
        "point": int(round(point)),
        "low": int(round(low)),
        "high": int(round(high)),
        "band": recovery_band(round(point), green, amber),
        "drivers": drivers[:4],
    }
