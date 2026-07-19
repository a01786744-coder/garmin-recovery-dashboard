import React, { useEffect, useState } from "react";
import Card from "./ui/Card.jsx";
import SectionTitle from "./ui/SectionTitle.jsx";
import WorkoutCard from "./WorkoutCard.jsx";
import CoachText from "./CoachText.jsx";
import { getPlan, generatePlan, adaptPlan, pushPlanWeek, deletePlan } from "../api.js";
import { fmtDay, localToday } from "../format.js";

const DISTANCES = [["5K", 5], ["10K", 10], ["Half", 21.1], ["Marathon", 42.2]];

const FOCUS_COLORS = {
  base: "#38bdf8", build: "#f97316", peak: "#ef4444",
  taper: "#a78bfa", recovery: "#22c55e",
};

function parseGoal(text) {
  // "45:00" or "1:45:00" -> seconds; empty/invalid -> null.
  const m = /^(?:(\d{1,2}):)?([0-5]?\d):([0-5]\d)$/.exec((text || "").trim());
  if (!m) return null;
  return (parseInt(m[1] || 0, 10) * 3600) + (parseInt(m[2], 10) * 60) + parseInt(m[3], 10);
}

function addDays(iso, n) {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function RaceForm({ onCreate, busy, error }) {
  const [name, setName] = useState("");
  const [date, setDate] = useState("");
  const [distance, setDistance] = useState(21.1);
  const [customKm, setCustomKm] = useState("");
  const [goal, setGoal] = useState("");
  const km = customKm ? parseFloat(customKm) : distance;
  const valid = date > localToday() && km > 0;

  return (
    <Card hover={false}>
      <SectionTitle sub="Tell the coach your race — it builds an adaptive plan and keeps it honest against your recovery">
        Training plan
      </SectionTitle>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="text-xs text-neutral-400">Race name
          <input value={name} onChange={(e) => setName(e.target.value)}
            placeholder="City half marathon"
            className="mt-1 w-full rounded-lg border border-line/10 bg-neutral-950/60 px-2.5 py-2 text-sm text-neutral-100 focus:border-accent/40 focus:outline-none" />
        </label>
        <label className="text-xs text-neutral-400">Race date
          <input type="date" value={date} min={addDays(localToday(), 1)}
            onChange={(e) => setDate(e.target.value)}
            className="mt-1 w-full rounded-lg border border-line/10 bg-neutral-950/60 px-2.5 py-2 text-sm text-neutral-100" />
        </label>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {DISTANCES.map(([label, v]) => (
          <button key={label}
            onClick={() => { setDistance(v); setCustomKm(""); }}
            className={"rounded-lg px-3 py-1.5 text-sm " +
              (!customKm && distance === v
                ? "bg-accent/15 text-neutral-50 ring-1 ring-accent/30"
                : "text-neutral-400 hover:text-neutral-200 border border-line/10")}>
            {label}
          </button>
        ))}
        <input value={customKm} onChange={(e) => setCustomKm(e.target.value)}
          placeholder="custom km" inputMode="decimal"
          className="w-24 rounded-lg border border-line/10 bg-neutral-950/60 px-2.5 py-1.5 text-sm text-neutral-100 focus:border-accent/40 focus:outline-none" />
        <input value={goal} onChange={(e) => setGoal(e.target.value)}
          placeholder="goal time (1:45:00, optional)"
          className="w-52 rounded-lg border border-line/10 bg-neutral-950/60 px-2.5 py-1.5 text-sm text-neutral-100 focus:border-accent/40 focus:outline-none" />
      </div>
      <div className="mt-4 flex items-center gap-3">
        <button disabled={!valid || busy}
          onClick={() => onCreate({ name: name.trim() || "Race", date,
            distance_km: km, goal_time_s: parseGoal(goal) })}
          className="rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-40">
          {busy ? "Coach is building your plan…" : "Build my plan"}
        </button>
        {busy && <span className="h-3 w-3 animate-spin rounded-full border-2 border-neutral-600 border-t-neutral-300" />}
        {error && <span className="text-sm text-red-400">{error}</span>}
      </div>
      <p className="mt-3 text-[11px] text-neutral-600">
        The plan details the next two weeks; "Adapt plan" each week revises what's
        ahead from how your training and recovery actually went. Nothing goes to
        your watch without an explicit send.
      </p>
    </Card>
  );
}

function WeekRow({ week, isCurrent, expanded, onToggle }) {
  const [push, setPush] = useState("idle"); // idle | confirm | sending | done | error
  const color = FOCUS_COLORS[(week.focus || "").toLowerCase()] || "#71717a";
  const detailed = Array.isArray(week.workouts) && week.workouts.length > 0;

  const sendWeek = async () => {
    setPush("sending");
    try {
      const res = await pushPlanWeek(week.index);
      setPush(res.ok ? "done" : "error");
    } catch { setPush("error"); }
  };

  return (
    <li className={"rounded-xl border px-3.5 py-2.5 " +
      (isCurrent ? "border-accent/30 bg-accent/[0.04]" : "border-line/5")}>
      <button onClick={onToggle} className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 text-left">
        <span className="text-sm font-semibold text-neutral-100">Wk {week.index}</span>
        <span className="text-xs text-neutral-500">
          {fmtDay(week.start)} – {fmtDay(addDays(week.start, 6))}
        </span>
        <span className="rounded-full px-2 py-0.5 text-[11px] font-medium"
          style={{ background: color + "22", color }}>
          {week.focus}
        </span>
        <span className="text-xs text-neutral-400">{Math.round(week.target_km)} km</span>
        {week.long_run_km != null && (
          <span className="text-xs text-neutral-500">long {Math.round(week.long_run_km)} km</span>
        )}
        {isCurrent && <span className="text-[11px] font-medium text-accent">this week</span>}
        <span className="ml-auto text-xs text-neutral-600">
          {detailed ? `${week.workouts.length} workouts` : "outline"} {expanded ? "▾" : "▸"}
        </span>
      </button>
      {expanded && (
        <div className="mt-2 space-y-2">
          <p className="text-sm text-neutral-300">{week.summary}</p>
          {detailed && week.workouts.map((w, i) => <WorkoutCard key={i} workout={w} />)}
          {detailed && (
            <div className="flex flex-wrap items-center gap-2 pt-1">
              {push === "done" ? (
                <span className="rounded-lg bg-emerald-500/10 px-3 py-1.5 text-sm text-emerald-300">
                  ✓ Week sent — workouts land on your watch at its next sync
                </span>
              ) : push === "confirm" || push === "sending" ? (
                <>
                  <button onClick={sendWeek} disabled={push === "sending"}
                    className="rounded-lg bg-amber-500/90 px-3 py-1.5 text-sm font-medium text-neutral-950 hover:bg-amber-400 disabled:opacity-50">
                    {push === "sending" ? "Sending…"
                      : `Confirm — schedule ${week.workouts.length} workouts on Garmin`}
                  </button>
                  <button onClick={() => setPush("idle")} disabled={push === "sending"}
                    className="rounded-lg px-3 py-1.5 text-sm text-neutral-400 hover:text-neutral-200">
                    Cancel
                  </button>
                </>
              ) : (
                <button onClick={() => setPush("confirm")}
                  className="rounded-lg border border-amber-500/40 px-3 py-1.5 text-sm text-amber-300 hover:bg-amber-500/10">
                  Send week to watch…
                </button>
              )}
              {push === "error" && <span className="text-sm text-red-400">Push failed — try again.</span>}
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export default function TrainingPlan() {
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);        // generate
  const [adapting, setAdapting] = useState(false);
  const [adaptReply, setAdaptReply] = useState(null);
  const [error, setError] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [expanded, setExpanded] = useState(null); // week index

  useEffect(() => {
    getPlan().then((r) => {
      setPlan(r.plan);
      setExpanded(currentWeekIndex(r.plan));
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const today = localToday();
  const currentWeekIndex = (p) => {
    const w = (p?.weeks || []).find((w) => w.start <= today && today < addDays(w.start, 7));
    return w ? w.index : (p?.weeks?.[0]?.index ?? null);
  };

  const create = async (race) => {
    setBusy(true); setError(null);
    try {
      const res = await generatePlan(race);
      if (res.error) { setError(errText(res.error)); }
      else { setPlan(res.plan); setExpanded(currentWeekIndex(res.plan)); }
    } catch (e) { setError(errText(e.message)); }
    setBusy(false);
  };

  const adapt = async () => {
    setAdapting(true); setAdaptReply(null);
    try {
      const res = await adaptPlan();
      if (res.error) setAdaptReply(`Couldn't adapt (${res.error}).`);
      else { setPlan(res.plan); setAdaptReply(res.plan.reply); setExpanded(currentWeekIndex(res.plan)); }
    } catch { setAdaptReply("Couldn't reach the coach — try again."); }
    setAdapting(false);
  };

  const remove = async () => {
    await deletePlan().catch(() => {});
    setPlan(null); setConfirmDelete(false); setAdaptReply(null);
  };

  const errText = (e) =>
    e === "not_configured" ? "Set up the coach in Settings → AI Coach first."
      : `Couldn't build the plan (${e}).`;

  if (loading) return null;
  if (!plan) return <RaceForm onCreate={create} busy={busy} error={error} />;

  const daysLeft = Math.ceil((new Date(plan.race.date) - new Date(today)) / 86400000);

  return (
    <Card hover={false}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <SectionTitle sub={`${plan.race.distance_km} km · ${fmtDay(plan.race.date)}`}>
            {plan.race.name}
          </SectionTitle>
          <div className="mt-1 text-2xl font-bold tracking-tight text-neutral-50">
            {daysLeft} <span className="text-sm font-medium text-neutral-400">days to go</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={adapt} disabled={adapting}
            className="rounded-lg border border-accent/40 px-3 py-1.5 text-sm text-accent hover:bg-accent/10 disabled:opacity-50">
            {adapting ? "Reviewing your week…" : "↻ Adapt plan"}
          </button>
          {confirmDelete ? (
            <>
              <button onClick={remove}
                className="rounded-lg bg-red-600/90 px-3 py-1.5 text-sm text-white hover:bg-red-500">
                Delete plan
              </button>
              <button onClick={() => setConfirmDelete(false)}
                className="rounded-lg px-2 py-1.5 text-sm text-neutral-400 hover:text-neutral-200">
                Cancel
              </button>
            </>
          ) : (
            <button onClick={() => setConfirmDelete(true)} title="Delete plan"
              className="rounded-lg px-2.5 py-1.5 text-sm text-neutral-500 hover:text-red-400">
              🗑
            </button>
          )}
        </div>
      </div>

      {adaptReply && (
        <div className="mt-2 rounded-xl border border-accent/20 bg-accent/[0.05] px-3.5 py-2.5">
          <CoachText text={adaptReply} />
        </div>
      )}
      {!adaptReply && plan.notes && (
        <div className="mt-2"><CoachText text={plan.notes} /></div>
      )}

      <ul className="mt-3 space-y-2">
        {(plan.weeks || []).map((w) => (
          <WeekRow key={w.index} week={w}
            isCurrent={w.start <= today && today < addDays(w.start, 7)}
            expanded={expanded === w.index}
            onToggle={() => setExpanded(expanded === w.index ? null : w.index)} />
        ))}
      </ul>
      <p className="mt-3 text-[11px] text-neutral-600">
        Run "Adapt plan" at the start of each week: the coach reviews what you
        actually did and your recovery, then details the week ahead.
      </p>
    </Card>
  );
}
