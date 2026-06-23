# Detail Views, Evolution Graphs & Insights — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Clicking any metric opens a Whoop-style slide-in detail panel (up-to-90-day evolution graph + stats + insights); activities show per-split graphs; Overview gains a tested insights/streaks/weekly-recap/correlations section — all from real local data.

**Architecture:** A tested backend `insights.py` computes weekly recap, streaks, auto-insights, and correlations from stored daily rows; `/api/insights` serves them and `/api/trends` gains a `perf` series. The frontend adds a registry-driven `DetailPanel` opened from any gauge/tile, plus an Overview insights section. No new dependencies, no new Garmin calls.

**Tech Stack:** Python 3.11 (Flask, pytest), SQLite, React + Tailwind + framer-motion + recharts.

## Global Constraints

- **No fabricated data:** every number computed from stored data; thin data → explicit "Not enough history yet" / empty list, never a placeholder number.
- **Capability-gated:** detail panels/insights only for supported metrics; hidden cards/tabs stay hidden (existing `caps`/`visible` rules unchanged).
- **Custom metrics labeled:** Recovery and Strain keep "Estimated · custom" notes in panels.
- **Local-first, never crashes:** insights/perf from local SQLite only; fetch failures keep last-good UI.
- **No new dependencies** (React, framer-motion, recharts only). **No new Garmin API calls.**
- Backend daily rows come from `db.get_trends(path, days)` → list of dicts ascending by date, each containing `date` + all `DAILY_FIELDS` + `recovery_score`/`strain_score`.
- All 80 existing backend tests must still pass.

## File structure

- `backend/insights.py` (new) — pure insight computations.
- `backend/db.py` — add `get_perf_history`.
- `backend/api.py` — `perf` in `/api/trends`; new `/api/insights`.
- `backend/tests/test_insights.py`, `test_phase6_api.py` (new).
- `frontend/src/detail/registry.js`, `frontend/src/detail/DetailPanel.jsx`, `frontend/src/detail/EvolutionChart.jsx`, `frontend/src/detail/StatRow.jsx` (new).
- `frontend/src/components/Insights.jsx` (new) — Overview insights section.
- `frontend/src/api.js` — `getInsights`.
- `frontend/src/components/ui/AnimatedGauge.jsx`, `StatTile.jsx` — optional `onClick`.
- `frontend/src/App.jsx` — open/close panel + 90-day cache + insights fetch.
- `frontend/src/tabs/*.jsx` — click-wiring; Activities split charts.

---

### Task 1: Backend — perf history in `/api/trends`

**Files:**
- Modify: `backend/db.py`, `backend/api.py`
- Test: `backend/tests/test_phase6_api.py`

**Interfaces:**
- Produces `db.get_perf_history(path, days) -> list[dict]` (perf_metrics rows within the last `days` dates, ascending). `/api/trends?days=N` response gains `"perf": [...]`.

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_phase6_api.py
from unittest.mock import MagicMock
import backend.db as db
from backend.api import create_app

def _client(tmp_path):
    p = tmp_path / "dashboard.db"
    db.init_db(p)
    app = create_app(p, client_factory=lambda: MagicMock(), tokenstore=tmp_path / "garth")
    return app.test_client(), p

def test_get_perf_history(tmp_path):
    p = tmp_path / "d.db"; db.init_db(p)
    db.upsert_perf(p, "2026-06-20", {"vo2max": 59})
    db.upsert_perf(p, "2026-06-22", {"vo2max": 60})
    hist = db.get_perf_history(p, 90)
    assert [r["date"] for r in hist] == ["2026-06-20", "2026-06-22"]   # ascending
    assert hist[-1]["vo2max"] == 60

def test_trends_includes_perf(tmp_path):
    client, p = _client(tmp_path)
    db.upsert_perf(p, "2026-06-22", {"vo2max": 60, "endurance_score": 6892})
    body = client.get("/api/trends?days=90").get_json()
    assert "perf" in body
    assert body["perf"][-1]["vo2max"] == 60
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/Scripts/python -m pytest backend/tests/test_phase6_api.py -v`
Expected: FAIL (`get_perf_history` undefined / no `perf` key).

- [ ] **Step 3: Implement**

In `backend/db.py` (after `get_latest_perf`):
```python
def get_perf_history(path, days):
    with _conn(path) as c:
        rows = c.execute(
            "SELECT * FROM perf_metrics ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]
```

In `backend/api.py`, extend the `_trends` helper inside `create_app`:
```python
    def _trends(days):
        rows = db.get_trends(db_path, days)
        return {
            "days": rows,
            "hrv": [{"date": r["date"], "value": r["hrv_last_night"]} for r in rows],
            "rhr": [{"date": r["date"], "value": r["rhr"]} for r in rows],
            "perf": db.get_perf_history(db_path, days),
        }
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/Scripts/python -m pytest backend/tests/test_phase6_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/db.py backend/api.py backend/tests/test_phase6_api.py
git commit -m "feat: expose perf history series in /api/trends"
```

---

### Task 2: Backend — insights engine (`insights.py`)

**Files:**
- Create: `backend/insights.py`
- Test: `backend/tests/test_insights.py`

**Interfaces:**
- Produces pure functions over `daily` (ascending list of daily rows) and `activities` (list with `date`):
  - `weekly_recap(daily, activities) -> dict`
  - `streaks(daily, activities) -> dict`
  - `auto_insights(daily) -> list[dict]` (each `{text, tone, metric}`)
  - `correlations(daily) -> list[dict]` (each `{text, detail}`)

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_insights.py
import backend.insights as ins

def _day(date, **kw):
    base = {"date": date, "recovery_score": None, "sleep_score": None,
            "strain_score": None, "hrv_last_night": None, "rhr": None,
            "deep_sleep_s": None, "light_sleep_s": None, "rem_sleep_s": None}
    base.update(kw); return base

def test_weekly_recap_deltas():
    daily = [_day(f"2026-05-{d:02d}", recovery_score=50) for d in range(1, 8)]
    daily += [_day(f"2026-05-{d:02d}", recovery_score=60) for d in range(8, 15)]
    wk = ins.weekly_recap(daily, [])
    assert wk["recovery_score"]["this"] == 60
    assert wk["recovery_score"]["last"] == 50
    assert wk["recovery_score"]["delta"] == 10

def test_weekly_recap_null_side_gives_none_delta():
    daily = [_day(f"2026-05-{d:02d}", recovery_score=60) for d in range(8, 15)]  # only this week
    wk = ins.weekly_recap(daily, [])
    assert wk["recovery_score"]["this"] == 60
    assert wk["recovery_score"]["last"] is None
    assert wk["recovery_score"]["delta"] is None

def test_streaks_green_recovery_and_break():
    daily = [_day("2026-06-18", recovery_score=70), _day("2026-06-19", recovery_score=40),
             _day("2026-06-20", recovery_score=80), _day("2026-06-21", recovery_score=72)]
    s = ins.streaks(daily, [])
    assert s["green_recovery"] == 2          # last two days >= 67, the 40 breaks it

def test_streaks_workout():
    daily = [_day("2026-06-20"), _day("2026-06-21")]
    acts = [{"date": "2026-06-21"}]
    assert ins.streaks(daily, acts)["workout"] == 1

def test_auto_insights_hrv_trend_up():
    daily = [_day(f"2026-06-{d:02d}", hrv_last_night=40) for d in range(8, 15)]
    daily += [_day(f"2026-06-{d:02d}", hrv_last_night=48) for d in range(15, 22)]
    out = ins.auto_insights(daily)
    assert any(i["metric"] == "hrv" and "up" in i["text"].lower() for i in out)

def test_auto_insights_thin_data_empty():
    assert ins.auto_insights([_day("2026-06-21", hrv_last_night=40)]) == []

def test_correlations_thin_data_empty():
    assert ins.correlations([_day("2026-06-21", recovery_score=60)]) == []

def test_correlations_sleep_to_recovery():
    # 10 days: long-sleep nights are followed by higher recovery
    daily = []
    for i in range(10):
        long = i % 2 == 0
        daily.append(_day(f"2026-06-{i+1:02d}",
                          deep_sleep_s=3600, light_sleep_s=(20000 if long else 9000),
                          rem_sleep_s=3600,
                          recovery_score=(75 if long else 55)))
    # next-day recovery encodes the prior night via the alternating pattern
    out = ins.correlations(daily)
    assert any("sleep" in c["text"].lower() for c in out)
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/Scripts/python -m pytest backend/tests/test_insights.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `backend/insights.py`**

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/Scripts/python -m pytest backend/tests/test_insights.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/insights.py backend/tests/test_insights.py
git commit -m "feat: add tested insights engine (recap, streaks, auto-insights, correlations)"
```

---

### Task 3: Backend — `/api/insights` endpoint

**Files:**
- Modify: `backend/api.py`
- Test: `backend/tests/test_phase6_api.py`

**Interfaces:**
- Produces `GET /api/insights` → `{"weekly": ..., "streaks": ..., "insights": [...], "correlations": [...]}` computed from `db.get_trends(db_path, 90)` + `db.get_recent_activities(db_path, 50)`.

- [ ] **Step 1: Write failing test (append)**

```python
def test_insights_endpoint(tmp_path):
    client, p = _client(tmp_path)
    for d in range(1, 15):
        m = {k: None for k in db.DAILY_FIELDS}
        m["recovery_score_placeholder"] = None  # not a real col; ignored
        db.upsert_daily(p, f"2026-06-{d:02d}", {k: None for k in db.DAILY_FIELDS},
                        recovery=(50 if d <= 7 else 60), strain=None)
    body = client.get("/api/insights").get_json()
    assert set(body) == {"weekly", "streaks", "insights", "correlations"}
    assert body["weekly"]["recovery_score"]["this"] == 60
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/Scripts/python -m pytest backend/tests/test_phase6_api.py::test_insights_endpoint -v`
Expected: FAIL (404 / missing route).

- [ ] **Step 3: Implement** — add inside `create_app` (near `/api/today`):

```python
    @app.get("/api/insights")
    def insights():
        from backend import insights as ins
        daily = db.get_trends(db_path, 90)
        acts = db.get_recent_activities(db_path, 50)
        return jsonify({
            "weekly": ins.weekly_recap(daily, acts),
            "streaks": ins.streaks(daily, acts),
            "insights": ins.auto_insights(daily),
            "correlations": ins.correlations(daily),
        })
```

- [ ] **Step 4: Run to verify pass + full suite**

Run: `.venv/Scripts/python -m pytest backend -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api.py backend/tests/test_phase6_api.py
git commit -m "feat: add /api/insights endpoint"
```

---

### Task 4: Frontend — DetailPanel foundation + registry

**Files:**
- Create: `frontend/src/detail/registry.js`, `frontend/src/detail/StatRow.jsx`, `frontend/src/detail/EvolutionChart.jsx`, `frontend/src/detail/DetailPanel.jsx`
- Modify: `frontend/src/api.js`

**Interfaces:**
- Consumes `getTrends(90)` shape `{days:[{date, <fields>}], perf:[{date, <perf>}]}`, `/api/intraday`, `caps`.
- Produces `METRICS` registry, `getInsights()`, and `<DetailPanel metricKey trends90 today caps onClose />`.

- [ ] **Step 1: `frontend/src/api.js`** — add insights call

```js
export const getInsights = () => j("/api/insights");
```

- [ ] **Step 2: `frontend/src/detail/registry.js`**

```js
// Each metric: where its series lives and how to present it.
export const METRICS = {
  recovery:           { label: "Recovery", source: "daily", field: "recovery_score", band: true, custom: true, accent: "#22c55e", max: 100 },
  sleep:              { label: "Sleep", source: "daily", field: "sleep_score", accent: "#8b5cf6", max: 100 },
  strain:             { label: "Strain", source: "daily", field: "strain_score", custom: true, accent: "#f97316", max: 100 },
  body_battery:       { label: "Body Battery", source: "daily", field: "body_battery", accent: "#38bdf8", intraday: "body_battery", max: 100 },
  rhr:                { label: "Resting HR", source: "daily", field: "rhr", unit: "bpm", accent: "#f97316" },
  hrv:                { label: "HRV", source: "daily", field: "hrv_last_night", unit: "ms", accent: "#22c55e", intraday: "hrv" },
  training_readiness: { label: "Training Readiness", source: "daily", field: "training_readiness_score", accent: "#22c55e", max: 100 },
  stress:             { label: "Stress", source: "daily", field: "stress_avg", accent: "#eab308", intraday: "stress", max: 100 },
  steps:              { label: "Steps", source: "daily", field: "steps", accent: "#a3e635" },
  floors:             { label: "Floors", source: "daily", field: "floors_ascended", accent: "#38bdf8" },
  intensity:          { label: "Intensity (wk)", source: "daily", field: "intensity_weekly_total", accent: "#f97316" },
  vo2max:             { label: "VO₂max", source: "perf", field: "vo2max", accent: "#22c55e" },
  endurance:          { label: "Endurance", source: "perf", field: "endurance_score", accent: "#a78bfa" },
};

// Build a [{date, value}] series for a metric from the 90-day trends payload.
export function metricSeries(trends90, key) {
  const m = METRICS[key];
  if (!m || !trends90) return [];
  const rows = m.source === "perf" ? trends90.perf : trends90.days;
  return (rows || []).map((r) => ({ date: r.date, value: r[m.field] }));
}
```

- [ ] **Step 3: `frontend/src/detail/StatRow.jsx`**

```jsx
import React from "react";

function stat(series, n) {
  const vals = series.map((d) => d.value).filter((v) => v != null);
  if (!vals.length) return null;
  const lastN = vals.slice(-n);
  return Math.round((lastN.reduce((a, b) => a + b, 0) / lastN.length) * 10) / 10;
}

export default function StatRow({ series, unit }) {
  const vals = series.map((d) => d.value).filter((v) => v != null);
  const current = vals.length ? vals[vals.length - 1] : null;
  const avg30 = stat(series, 30);
  const items = [
    ["Current", current],
    ["7-day avg", stat(series, 7)],
    ["30-day avg", avg30],
    ["Min", vals.length ? Math.min(...vals) : null],
    ["Max", vals.length ? Math.max(...vals) : null],
    ["Δ vs avg", current != null && avg30 != null ? Math.round((current - avg30) * 10) / 10 : null],
  ];
  return (
    <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
      {items.map(([label, v]) => (
        <div key={label} className="rounded-lg bg-neutral-950/40 p-2 text-center">
          <div className="text-[10px] uppercase tracking-wide text-neutral-500">{label}</div>
          <div className="text-base font-semibold text-neutral-100">
            {v == null ? "—" : v}{v != null && unit ? <span className="text-[10px] text-neutral-500"> {unit}</span> : null}
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: `frontend/src/detail/EvolutionChart.jsx`**

```jsx
import React from "react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import NoData from "../components/ui/NoData.jsx";

export default function EvolutionChart({ series, color = "#38bdf8", height = 220 }) {
  const data = (series || []).map((d) => ({ x: d.date, y: d.value }));
  const vals = data.map((d) => d.y).filter((v) => v != null);
  if (vals.length < 2) return <NoData label="Not enough history yet" height={height} />;
  const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
  const gid = "ev" + color.replace("#", "");
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="x" stroke="#52525b" fontSize={10} tickLine={false} axisLine={false}
          minTickGap={48} tickFormatter={(d) => (typeof d === "string" ? d.slice(5) : "")} />
        <YAxis domain={["auto", "auto"]} stroke="#52525b" fontSize={10} width={32}
          tickLine={false} axisLine={false} />
        <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #27272a", borderRadius: 8, color: "#fff", fontSize: 12 }} />
        <ReferenceLine y={avg} stroke="#a1a1aa" strokeDasharray="4 4"
          label={{ value: `avg ${Math.round(avg)}`, fill: "#a1a1aa", fontSize: 10, position: "insideTopRight" }} />
        <Area type="monotone" dataKey="y" stroke={color} strokeWidth={2} fill={`url(#${gid})`}
          dot={false} connectNulls={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 5: `frontend/src/detail/DetailPanel.jsx`**

```jsx
import React, { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { METRICS, metricSeries } from "./registry.js";
import EvolutionChart from "./EvolutionChart.jsx";
import StatRow from "./StatRow.jsx";
import MiniArea from "../components/ui/MiniArea.jsx";
import NoData from "../components/ui/NoData.jsx";
import { getIntraday } from "../api.js";
import { useAsync, pairsToXY } from "../useApi.js";
import { gmtToLocalClock } from "../format.js";

export default function DetailPanel({ metricKey, trends90, today, insights, onClose }) {
  const m = metricKey ? METRICS[metricKey] : null;
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const date = today?.metrics?.date;
  const intraday = useAsync(
    () => (m?.intraday && date ? getIntraday(date, m.intraday) : null),
    [m?.intraday, date]
  );

  return (
    <AnimatePresence>
      {m && (
        <motion.div className="fixed inset-0 z-50 flex justify-end bg-black/60"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onClick={onClose}>
          <motion.aside
            className="h-full w-full max-w-xl overflow-y-auto border-l border-white/10 bg-neutral-950 p-5"
            initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 40, opacity: 0 }}
            transition={{ type: "spring", stiffness: 320, damping: 34 }}
            onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h2 className="text-xl font-bold text-neutral-50">{m.label}</h2>
                {m.custom && <p className="text-[11px] text-neutral-500">Estimated · custom metric (not Garmin/Whoop)</p>}
              </div>
              <button onClick={onClose} className="text-neutral-500 hover:text-neutral-200">✕</button>
            </div>

            <div className="mb-4 text-sm text-neutral-400">Up to 90-day evolution</div>
            <EvolutionChart series={metricSeries(trends90, metricKey)} color={m.accent} />

            <div className="my-5">
              <StatRow series={metricSeries(trends90, metricKey)} unit={m.unit} />
            </div>

            {m.intraday && (
              <div className="mb-5">
                <div className="mb-2 text-sm text-neutral-400">Today</div>
                {intraday.loading ? <NoData label="Loading…" height={150} />
                  : <MiniArea data={pairsToXY(intraday.data?.series)} color={m.accent} height={150}
                      xTickFormatter={(t) => (typeof t === "number" ? "" : gmtToLocalClock(t))} />}
              </div>
            )}

            {insights?.insights?.filter((i) => i.metric === metricKey).length > 0 && (
              <div className="space-y-2">
                <div className="text-sm text-neutral-400">Insights</div>
                {insights.insights.filter((i) => i.metric === metricKey).map((i, k) => (
                  <div key={k} className={"rounded-lg px-3 py-2 text-sm " +
                    (i.tone === "warn" ? "bg-amber-500/10 text-amber-300" : "bg-emerald-500/10 text-emerald-300")}>
                    {i.text}
                  </div>
                ))}
              </div>
            )}
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

- [ ] **Step 6: Build to verify it compiles**

Run: `cd "/c/Users/rodri/Documents/garmin-dashboard/frontend" && npm run build`
Expected: builds (component not yet mounted; just must compile).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/detail frontend/src/api.js
git commit -m "feat: add DetailPanel, metric registry, evolution chart, stat row"
```

---

### Task 5: Frontend — open panel from any metric + click-wiring

**Files:**
- Modify: `frontend/src/App.jsx`, `frontend/src/components/ui/AnimatedGauge.jsx`, `frontend/src/components/ui/StatTile.jsx`, `frontend/src/tabs/Overview.jsx`, `frontend/src/tabs/Sleep.jsx`, `frontend/src/tabs/Training.jsx`, `frontend/src/tabs/Trends.jsx`

**Interfaces:**
- Consumes `DetailPanel`, `getInsights`, `getTrends`. Produces an `onOpen(metricKey)` passed to every tab; gauges/tiles call it.

- [ ] **Step 1: Make `AnimatedGauge` and `StatTile` optionally clickable**

In `AnimatedGauge.jsx`, accept `onClick`; wrap the outer `<div className="flex flex-col items-center">` so when `onClick` is set it becomes a button-like element:
```jsx
export default function AnimatedGauge({ value, max = 100, label, sublabel, unit, digits = 0, color = "#3b82f6", nullText = "No data", size = 150, onClick }) {
  // ...unchanged internals...
  // change the root element:
  const Root = onClick ? "button" : "div";
  return (
    <Root type={onClick ? "button" : undefined} onClick={onClick}
      className={"flex flex-col items-center " + (onClick ? "cursor-pointer hover:opacity-90 transition-opacity" : "")}>
      {/* existing children unchanged */}
    </Root>
  );
}
```

In `StatTile.jsx`, accept `onClick` and pass it to the `Card` (Card is a motion.div; add `onClick` + cursor when set):
```jsx
export default function StatTile({ label, value, unit, digits = 0, sub, accent = "#a1a1aa", icon, onClick }) {
  // ...
  return (
    <Card onClick={onClick} className={"flex flex-col justify-between min-h-[92px] " + (onClick ? "cursor-pointer" : "")}>
      {/* unchanged */}
    </Card>
  );
}
```
(`Card` already spreads `...rest` onto its `motion.div`, so `onClick` flows through.)

- [ ] **Step 2: App — panel state, 90-day cache, insights fetch**

In `App.jsx`, add imports + state:
```jsx
import DetailPanel from "./detail/DetailPanel.jsx";
import { getInsights, getTrends as getTrendsApi } from "./api.js";
```
(Existing `getTrends` import remains; reuse it.) Add state:
```jsx
  const [insights, setInsights] = useState(null);
  const [trends90, setTrends90] = useState(null);
  const [detailKey, setDetailKey] = useState(null);
```
In `load()` add insights to the `Promise.all`:
```jsx
      const [t, tr, cp, ins] = await Promise.all([getToday(), getTrends(14), getCapabilities(), getInsights()]);
      setToday(t); setTrends(tr); setCaps(cp); setInsights(ins);
```
Add an opener that lazy-fetches 90-day history once:
```jsx
  const openDetail = useCallback(async (key) => {
    setDetailKey(key);
    if (!trends90) {
      try { setTrends90(await getTrends(90)); } catch (e) { /* panel still shows today + insights */ }
    }
  }, [trends90]);
```
Render the panel (anywhere inside the top-level wrapper, e.g. before `</div>` end):
```jsx
      <DetailPanel metricKey={detailKey} trends90={trends90} today={today}
        insights={insights} onClose={() => setDetailKey(null)} />
```
Pass `onOpen={openDetail}` to the active tab:
```jsx
      <Active today={today} trends={trends} caps={caps} units={units} onOpen={openDetail} />
```

- [ ] **Step 3: Overview — wire clicks**

In `Overview.jsx`, accept `onOpen` and add `onClick` to gauges/tiles:
```jsx
export default function Overview({ today, caps, onOpen }) {
  // ...
  // Recovery gauge: <AnimatedGauge ... onClick={() => onOpen("recovery")} />
  // Sleep gauge:    onClick={() => onOpen("sleep")}
  // Strain gauge:   onClick={() => onOpen("strain")}
  // StatTiles: add onClick={() => onOpen("<key>")} matching registry keys:
  //   Body Battery->body_battery, Resting HR->rhr, Training Readiness->training_readiness,
  //   Stress->stress, Steps->steps, Floors->floors. (Active kcal tile: no panel — leave unclickable.)
}
```

- [ ] **Step 4: Sleep / Training / Trends — wire clicks**

- `Sleep.jsx` (`onOpen` prop): Sleep Score gauge → `onOpen("sleep")`; "Overnight HRV avg" tile → `onOpen("hrv")`; "Resting HR" tile → `onOpen("rhr")`.
- `Training.jsx` (`onOpen` prop): Strain gauge → `onOpen("strain")`; ACWR gauge → (no registry metric) leave; Readiness tile → `onOpen("training_readiness")`; Intensity tile → `onOpen("intensity")`.
- `Trends.jsx` (`onOpen` prop): VO₂max tile → `onOpen("vo2max")`; Endurance tile → `onOpen("endurance")`; HRV trend card → wrap title area with a button `onClick={() => onOpen("hrv")}`; RHR trend card → `onOpen("rhr")`. (Add `onClick` to the `StatTile`s and an onClick on the trend `Card`s.)

Each tab passes `onOpen` straight through from `App`. Tabs that don't use it ignore it.

- [ ] **Step 5: Build + verify compiles**

Run: `cd "/c/Users/rodri/Documents/garmin-dashboard/frontend" && npm run build`
Expected: builds clean.

- [ ] **Step 6: Commit**

```bash
cd "/c/Users/rodri/Documents/garmin-dashboard"
git add frontend/src
git commit -m "feat: open detail panel from any metric (gauges + tiles + trend cards)"
```

---

### Task 6: Frontend — activity per-split graphs

**Files:**
- Modify: `frontend/src/tabs/Activities.jsx`

**Interfaces:**
- Consumes `data.splits` (lapDTOs: `averageHR`, `averageSpeed`) already fetched via `/api/activity/<id>`.

- [ ] **Step 1: Add split charts in `Detail`**

In `Activities.jsx`, import `MiniArea` and after the existing `<SplitsTable .../>` add HR-per-split and pace-per-split charts (only when splits exist). Pace from `averageSpeed` (m/s) → seconds/unit:
```jsx
// inside Detail, after Splits table:
{data?.splits?.length > 1 && (
  <>
    <SectionTitle>HR by split</SectionTitle>
    <MiniArea height={140} color="#ef4444" area={false}
      data={data.splits.map((s, i) => ({ x: i + 1, y: s.averageHR ?? null }))} />
    <SectionTitle>Pace by split</SectionTitle>
    <MiniArea height={140} color="#22c55e" area={false}
      data={data.splits.map((s, i) => ({ x: i + 1, y: s.averageSpeed ? (units === "imperial" ? 1609.34 : 1000) / s.averageSpeed : null }))} />
    <p className="text-[11px] text-neutral-600">Pace shown as seconds per {units === "imperial" ? "mile" : "km"} (lower is faster).</p>
  </>
)}
```
`Detail` already receives `units`.

- [ ] **Step 2: Build + verify compiles**

Run: `cd "/c/Users/rodri/Documents/garmin-dashboard/frontend" && npm run build`
Expected: builds clean.

- [ ] **Step 3: Commit**

```bash
cd "/c/Users/rodri/Documents/garmin-dashboard"
git add frontend/src/tabs/Activities.jsx
git commit -m "feat: per-split HR and pace graphs in activity detail"
```

---

### Task 7: Frontend — Overview insights section

**Files:**
- Create: `frontend/src/components/Insights.jsx`
- Modify: `frontend/src/tabs/Overview.jsx`

**Interfaces:**
- Consumes `insights` (`{weekly, streaks, insights, correlations}`) and `caps`.
- Produces `<InsightsSection insights caps />` rendered at the top of Overview.

- [ ] **Step 1: `frontend/src/components/Insights.jsx`**

```jsx
import React from "react";
import { motion } from "framer-motion";
import Card from "./ui/Card.jsx";
import Grid from "./ui/Grid.jsx";
import SectionTitle from "./ui/SectionTitle.jsx";
import NoData from "./ui/NoData.jsx";
import { visible } from "../caps.js";

function delta(d) {
  if (d == null) return null;
  const up = d > 0;
  return <span className={up ? "text-emerald-400" : d < 0 ? "text-red-400" : "text-neutral-500"}>
    {up ? "▲" : d < 0 ? "▼" : ""}{Math.abs(d)}</span>;
}

const RECAP_ROWS = [
  ["recovery_score", "Recovery"], ["sleep_score", "Sleep"],
  ["hrv_last_night", "HRV"], ["rhr", "Resting HR"], ["strain_score", "Strain"],
];

export default function InsightsSection({ insights, caps }) {
  if (!insights) return null;
  const { weekly, streaks, insights: auto = [], correlations = [] } = insights;
  const streakItems = [
    ["green_recovery", "green recovery days", caps == null || visible(caps, "hrv")],
    ["workout", "workout days", caps == null || visible(caps, "activities")],
    ["sleep_goal", "sleep-goal nights", caps == null || visible(caps, "sleep")],
    ["worn", "days worn", true],
  ].filter(([k, , ok]) => ok && (streaks?.[k] || 0) > 0);

  return (
    <Grid className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card>
        <SectionTitle>Insights</SectionTitle>
        {auto.length === 0 ? <NoData label="Building insights as data grows…" /> : (
          <div className="space-y-2">
            {auto.slice(0, 3).map((i, k) => (
              <motion.div key={k} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                transition={{ delay: k * 0.05 }}
                className={"rounded-lg px-3 py-2 text-sm " +
                  (i.tone === "warn" ? "bg-amber-500/10 text-amber-300" : "bg-emerald-500/10 text-emerald-300")}>
                {i.text}
              </motion.div>
            ))}
          </div>
        )}
        {correlations[0] && (
          <div className="mt-3 rounded-lg bg-neutral-950/40 p-3 text-sm text-neutral-300">
            <div className="mb-0.5 text-[11px] uppercase tracking-wide text-neutral-500">Discovery</div>
            {correlations[0].text} <span className="text-neutral-500">({correlations[0].detail})</span>
          </div>
        )}
      </Card>

      <Card>
        <SectionTitle>This week vs last</SectionTitle>
        <div className="space-y-1.5">
          {RECAP_ROWS.map(([f, label]) => {
            const w = weekly?.[f];
            return (
              <div key={f} className="flex items-center justify-between text-sm">
                <span className="text-neutral-400">{label}</span>
                <span className="text-neutral-200">
                  {w?.this == null ? "—" : w.this}{" "}
                  {w?.delta != null && <span className="text-xs">({delta(w.delta)})</span>}
                </span>
              </div>
            );
          })}
          <div className="flex items-center justify-between text-sm pt-1 border-t border-white/5">
            <span className="text-neutral-400">Workouts</span>
            <span className="text-neutral-200">{weekly?.workouts?.this ?? "—"}</span>
          </div>
        </div>
        {streakItems.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {streakItems.map(([k, label]) => (
              <motion.span key={k} initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                className="rounded-full bg-white/5 px-2.5 py-1 text-xs text-neutral-300">
                🔥 {streaks[k]} {label}
              </motion.span>
            ))}
          </div>
        )}
      </Card>
    </Grid>
  );
}
```

- [ ] **Step 2: Mount in Overview**

In `Overview.jsx`, accept `insights` prop and render `<InsightsSection insights={insights} caps={caps} />` just under the custom-metric caption (import it). Pass `insights` from `App` → active tab: in `App.jsx` change the active render to also pass `insights={insights}`:
```jsx
      <Active today={today} trends={trends} caps={caps} units={units} onOpen={openDetail} insights={insights} />
```

- [ ] **Step 3: Build + verify compiles**

Run: `cd "/c/Users/rodri/Documents/garmin-dashboard/frontend" && npm run build`
Expected: builds clean.

- [ ] **Step 4: Commit**

```bash
cd "/c/Users/rodri/Documents/garmin-dashboard"
git add frontend/src/components/Insights.jsx frontend/src/tabs/Overview.jsx frontend/src/App.jsx
git commit -m "feat: Overview insights section (auto-insights, weekly recap, streaks, discovery)"
```

---

### Task 8: Live verification

- [ ] **Step 1:** Run full backend suite: `.venv/Scripts/python -m pytest backend -q` — all pass.
- [ ] **Step 2:** Start backend (real data dir) + preview; via DOM snapshots confirm: Overview shows the insights section; clicking the Recovery gauge opens the slide-in panel with an evolution chart + stat row; clicking a tile (e.g. Resting HR) opens its panel; Esc/✕ closes; an activity shows the per-split HR/pace charts. Reset any test state and stop servers.
- [ ] **Step 3 (controller):** summarize and stop.

---

## Self-Review (completed during planning)

- **Spec coverage:** perf history (T1), insights engine all four computations (T2), `/api/insights` (T3), DetailPanel + registry + evolution + stats + intraday extra (T4), click-wiring everywhere + custom-label (T5), activity split graphs (T6), Overview insights/streaks/recap/correlations section (T7), verification (T8). ✓
- **No fabrication:** EvolutionChart "Not enough history yet" (<2 pts); StatRow "—" on null; insights/correlations return `[]` on thin data (tested T2); "Building insights…" UI state. ✓
- **Capability gating:** gated cards aren't rendered (so unclickable); InsightsSection streaks filtered by `visible(caps, …)`. ✓
- **Type consistency:** `metricSeries(trends90, key)` and `METRICS[key].field`/`.source` used consistently; insight objects `{text, tone, metric}` produced in T2 and filtered in T4/T7; `weekly[field].{this,last,delta}` consistent T2↔T7; `getInsights` defined T4 used T5. ✓
- **No new deps / no new Garmin calls:** evolution from stored trends, splits from stored lap data, insights from local SQLite. ✓
