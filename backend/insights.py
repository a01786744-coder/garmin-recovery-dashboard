"""Insights computed from stored daily data. Pure functions; no fabrication —
thin data yields empty/zero results, never invented numbers."""
import datetime as _dt
from statistics import mean, median

MIN_TREND_DAYS = 4      # non-null days needed in EACH 7-day window for a % trend
MIN_BEST_DAYS = 10      # "best in N days" needs this much history
MIN_PAIRS = 8           # a correlation needs this many paired days
CORR_MIN_GAP = 3.0      # min recovery-point gap to report a correlation
GREEN_RECOVERY = 67
SLEEP_GOAL = 70

# Fixed journal tag set (v1 — no custom tags). Order = display order.
JOURNAL_TAGS = ["alcohol", "caffeine_late", "late_meal", "high_stress",
                "sick", "travel", "screens_in_bed", "nap"]
MIN_TAG_DAYS = 4        # tagged AND untagged days needed to report a tag effect

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


# Journal tags are tested against the day AFTER the entry (both metrics are
# filed under the wake date): what you did on day D shows up in D+1's row.
_JOURNAL_METRICS = [
    ("recovery", "recovery_score", "next-day recovery"),
    ("sleep", "sleep_score", "next-night sleep"),
]


def journal_correlations(daily, entries):
    """Per-tag effect on next-day recovery AND next-night sleep: mean metric
    after tagged days vs after untagged days. Reports only tags with >=
    MIN_TAG_DAYS days on each side and a gap >= CORR_MIN_GAP. Items carry
    structured tag/metric/delta fields for the UI. Empty on thin data."""
    out = []
    for metric_key, field, phrase in _JOURNAL_METRICS:
        by_date = {r["date"]: r.get(field) for r in (daily or [])}
        for tag in JOURNAL_TAGS:
            tagged, untagged = [], []
            for e in (entries or []):
                try:
                    nxt = (_dt.date.fromisoformat(e["date"]) + _dt.timedelta(days=1)).isoformat()
                except (KeyError, ValueError):
                    continue
                v = by_date.get(nxt)
                if v is None:
                    continue
                if (e.get("tags") or {}).get(tag):
                    tagged.append(v)
                else:
                    untagged.append(v)
            if len(tagged) >= MIN_TAG_DAYS and len(untagged) >= MIN_TAG_DAYS:
                gap = mean(tagged) - mean(untagged)
                if abs(gap) >= CORR_MIN_GAP:
                    label = tag.replace("_", " ")
                    out.append({
                        "tag": tag,
                        "metric": metric_key,
                        "delta": round(gap, 1),
                        "text": f"On {label} days, {phrase} averages "
                                f"{round(abs(gap))} points {'lower' if gap < 0 else 'higher'}.",
                        "detail": f"{round(mean(tagged))} vs {round(mean(untagged))}",
                    })
    return out


def week_extremes(daily):
    """Best and worst recovery day of the last 7 rows; None when nothing is
    scored (never invented)."""
    scored = [(r["date"], r["recovery_score"]) for r in (daily or [])[-7:]
              if r.get("recovery_score") is not None]
    if not scored:
        return None
    best = max(scored, key=lambda p: p[1])
    worst = min(scored, key=lambda p: p[1])
    return {"best": {"date": best[0], "recovery": best[1]},
            "worst": {"date": worst[0], "recovery": worst[1]}}


# --- Today-tab recap summaries (plain-language; empty on thin data) ---

def _hm(seconds):
    h = int(seconds // 3600)
    m = round((seconds % 3600) / 60)
    return f"{h}h {m}m" if h else f"{m}m"


def _band_word(score):
    if score >= GREEN_RECOVERY:
        return "green"
    return "yellow" if score >= 34 else "red"


def _hrv_baseline(daily):
    vals = _vals(daily or [], "hrv_last_night")
    return round(mean(vals)) if len(vals) >= 5 else None


def _near(x, base):
    if x >= base * 1.05:
        return "above"
    if x <= base * 0.95:
        return "below"
    return "near"


def _join(parts):
    if not parts:
        return ""
    text = ", ".join(parts)
    return text[0].upper() + text[1:] + "."


def morning_summary(metrics, daily):
    """One-line overnight-recovery recap from today's metrics (+ history for the
    HRV baseline). Empty string when nothing usable is present."""
    m = metrics or {}
    parts = []
    sleep_s = _sleep_seconds(m)
    if sleep_s:
        clause = f"you slept {_hm(sleep_s)}"
        if m.get("sleep_score") is not None:
            clause += f" (sleep score {round(m['sleep_score'])})"
        parts.append(clause)
    if m.get("recovery_score") is not None:
        parts.append(f"recovery is {_band_word(m['recovery_score'])} at {round(m['recovery_score'])}")
    hrv = m.get("hrv_last_night")
    if hrv is not None:
        base = _hrv_baseline(daily)
        if base is not None:
            parts.append(f"overnight HRV {round(hrv)}ms is {_near(hrv, base)} your {base}ms baseline")
        else:
            parts.append(f"overnight HRV is {round(hrv)}ms")
    if m.get("training_readiness_score") is not None:
        parts.append(f"Training Readiness is {round(m['training_readiness_score'])}")
    return _join(parts)


def afternoon_summary(metrics, daily):
    """One-line day-so-far recap from today's metrics. Empty when nothing usable."""
    m = metrics or {}
    parts = []
    if m.get("body_battery") is not None:
        parts.append(f"Body Battery is at {round(m['body_battery'])}")
    if m.get("steps") is not None:
        parts.append(f"you're at {round(m['steps']):,} steps")
    if m.get("stress_avg") is not None:
        parts.append(f"average stress is {round(m['stress_avg'])}")
    if m.get("intensity_weekly_total") is not None and m.get("intensity_weekly_goal"):
        parts.append(f"{round(m['intensity_weekly_total'])} of {round(m['intensity_weekly_goal'])} weekly intensity minutes")
    return _join(parts)
