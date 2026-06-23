"""Insights computed from stored daily data. Pure functions; no fabrication —
thin data yields empty/zero results, never invented numbers."""
from statistics import mean, median

MIN_TREND_DAYS = 4      # non-null days needed in EACH 7-day window for a % trend
MIN_BEST_DAYS = 10      # "best in N days" needs this much history
MIN_PAIRS = 8           # a correlation needs this many paired days
CORR_MIN_GAP = 3.0      # min recovery-point gap to report a correlation
GREEN_RECOVERY = 67
SLEEP_GOAL = 70

_RECAP_FIELDS = ["recovery_score", "sleep_score", "strain_score",
                 "hrv_last_night", "rhr"]


def _vals(rows, field):
    return [r.get(field) for r in rows if r.get(field) is not None]


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return round(mean(xs), 1) if xs else None


def weekly_recap(daily, activities):
    last7, prev7 = daily[-7:], daily[-14:-7]
    out = {}
    for f in _RECAP_FIELDS:
        a, b = _avg(_vals(last7, f)), _avg(_vals(prev7, f))
        out[f] = {"this": a, "last": b,
                  "delta": (round(a - b, 1) if a is not None and b is not None else None)}
    this_dates = {r["date"] for r in last7}
    last_dates = {r["date"] for r in prev7}
    act_dates = [a.get("date") for a in (activities or [])]
    out["workouts"] = {"this": sum(d in this_dates for d in act_dates),
                       "last": sum(d in last_dates for d in act_dates)}
    out["strain_total"] = {"this": round(sum(_vals(last7, "strain_score")), 0),
                           "last": round(sum(_vals(prev7, "strain_score")), 0)}
    return out


def _cur_streak(daily, pred):
    n = 0
    for r in reversed(daily):
        if pred(r):
            n += 1
        else:
            break
    return n


def streaks(daily, activities):
    act_dates = {a.get("date") for a in (activities or [])}
    worn_fields = ("steps", "rhr", "hrv_last_night", "sleep_score")
    return {
        "green_recovery": _cur_streak(daily, lambda r: (r.get("recovery_score") or 0) >= GREEN_RECOVERY),
        "sleep_goal": _cur_streak(daily, lambda r: (r.get("sleep_score") or 0) >= SLEEP_GOAL),
        "worn": _cur_streak(daily, lambda r: any(r.get(f) is not None for f in worn_fields)),
        "workout": _cur_streak(daily, lambda r: r.get("date") in act_dates),
    }


def _pct_change(daily, field):
    last7, prev7 = _vals(daily[-7:], field), _vals(daily[-14:-7], field)
    if len(last7) < MIN_TREND_DAYS or len(prev7) < MIN_TREND_DAYS:
        return None
    a, b = mean(last7), mean(prev7)
    return None if b == 0 else (a - b) / b * 100


def auto_insights(daily):
    out = []
    hv = _pct_change(daily, "hrv_last_night")
    if hv is not None and abs(hv) >= 3:
        out.append({"metric": "hrv", "tone": "good" if hv > 0 else "warn",
                    "text": f"HRV trending {'up' if hv > 0 else 'down'} {abs(round(hv))}% vs last week"})
    rv = _pct_change(daily, "rhr")
    if rv is not None and abs(rv) >= 3:
        out.append({"metric": "rhr", "tone": "good" if rv < 0 else "warn",
                    "text": f"Resting HR trending {'down' if rv < 0 else 'up'} {abs(round(rv))}% vs last week"})
    for field, key, label in [("recovery_score", "recovery", "Recovery"),
                              ("sleep_score", "sleep", "Sleep"),
                              ("hrv_last_night", "hrv", "HRV")]:
        vals = _vals(daily, field)
        if len(vals) >= MIN_BEST_DAYS and daily[-1].get(field) is not None and daily[-1][field] == max(vals):
            out.append({"metric": key, "tone": "good", "text": f"Best {label} in {len(vals)} days"})
    rc = _pct_change(daily, "recovery_score")
    if rc is not None and abs(rc) >= 5:
        out.append({"metric": "recovery", "tone": "good" if rc > 0 else "warn",
                    "text": f"Recovery {'climbing' if rc > 0 else 'dipping'} this week"})
    return out


def _sleep_seconds(r):
    s = sum(r.get(k) or 0 for k in ("deep_sleep_s", "light_sleep_s", "rem_sleep_s"))
    return s or None


def _median_split(pairs):
    """pairs: list of (x, next_day_recovery). Returns the high-vs-low recovery
    gap when there are enough pairs and both groups are populated."""
    if len(pairs) < MIN_PAIRS:
        return None
    m = median(p[0] for p in pairs)
    high = [y for x, y in pairs if x > m]
    low = [y for x, y in pairs if x <= m]
    if not high or not low:
        return None
    return {"gap": mean(high) - mean(low), "high": mean(high), "low": mean(low), "median": m}


def _pairs(daily, value_fn):
    out = []
    for i in range(len(daily) - 1):
        x = value_fn(daily[i])
        y = daily[i + 1].get("recovery_score")
        if x is not None and y is not None:
            out.append((x, y))
    return out


def correlations(daily):
    out = []
    s = _median_split(_pairs(daily, _sleep_seconds))
    if s and abs(s["gap"]) >= CORR_MIN_GAP:
        hrs = round(s["median"] / 3600, 1)
        out.append({
            "text": f"On nights you sleep over {hrs}h, next-day Recovery averages "
                    f"{round(abs(s['gap']))} points {'higher' if s['gap'] > 0 else 'lower'}.",
            "detail": f"{round(s['high'])} vs {round(s['low'])}",
        })
    st = _median_split(_pairs(daily, lambda r: r.get("strain_score")))
    if st and abs(st["gap"]) >= CORR_MIN_GAP:
        out.append({
            "text": f"After higher-strain days, next-day Recovery averages "
                    f"{round(abs(st['gap']))} points {'higher' if st['gap'] > 0 else 'lower'}.",
            "detail": f"{round(st['high'])} vs {round(st['low'])}",
        })
    return out
