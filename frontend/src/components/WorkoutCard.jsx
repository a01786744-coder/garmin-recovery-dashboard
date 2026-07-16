import React, { useState } from "react";
import Card from "./ui/Card.jsx";
import { sendCoachWorkout } from "../api.js";
import { localToday } from "../format.js";

const KIND_COLORS = {
  warmup: "#38bdf8", interval: "#f97316", recovery: "#22c55e",
  cooldown: "#a78bfa", rest: "#71717a", repeat: "#eab308",
};

function paceStr(secPerKm) {
  if (secPerKm == null) return "";
  const m = Math.floor(secPerKm / 60);
  const s = Math.round(secPerKm % 60);
  return `${m}:${String(s).padStart(2, "0")}/km`;
}

function durationStr(step) {
  const v = step.duration_value;
  if (step.duration_type === "distance") {
    return v >= 1000 ? `${(v / 1000).toFixed(v % 1000 ? 1 : 0)} km` : `${Math.round(v)} m`;
  }
  const min = Math.floor(v / 60), s = Math.round(v % 60);
  return s ? `${min}m ${s}s` : `${min} min`;
}

function targetStr(step) {
  if (step.target_type === "pace" && step.target_min != null) {
    return `${paceStr(step.target_min)} – ${paceStr(step.target_max)}`;
  }
  if (step.target_type === "heart_rate" && step.target_min != null) {
    return `${Math.round(step.target_min)}–${Math.round(step.target_max)} bpm`;
  }
  return "—";
}

function StepRow({ step, indent }) {
  return (
    <div className={"flex items-center gap-2 py-1.5 text-sm " + (indent ? "pl-6" : "")}>
      <span className="h-2 w-2 shrink-0 rounded-full"
        style={{ background: KIND_COLORS[step.kind] || "#71717a" }} />
      <span className="w-20 shrink-0 capitalize text-neutral-300">{step.kind}</span>
      <span className="w-20 shrink-0 text-neutral-100">{durationStr(step)}</span>
      <span className="w-36 shrink-0 font-medium text-neutral-100">{targetStr(step)}</span>
      <span className="truncate text-xs text-neutral-500">{step.description}</span>
    </div>
  );
}

// A structured workout proposed by the coach. Nothing is pushed to Garmin
// until the user explicitly reviews the steps and taps "Send to watch".
export default function WorkoutCard({ workout, onSent }) {
  const [date, setDate] = useState(workout.suggested_date || localToday());
  const [state, setState] = useState("idle"); // idle | confirm | sending | sent | error
  const [error, setError] = useState(null);

  if (!workout) return null;

  const send = async () => {
    setState("sending");
    try {
      const res = await sendCoachWorkout(workout, date);
      if (res.error) { setError(res.error); setState("error"); return; }
      setState("sent");
      onSent && onSent(res);
    } catch (e) {
      setError(String(e.message || e)); setState("error");
    }
  };

  return (
    <Card hover={false} className="border border-amber-500/20 bg-amber-500/5">
      <div className="mb-1 flex items-center justify-between gap-2">
        <div>
          <div className="text-sm font-semibold text-neutral-50">🏃 {workout.name}</div>
          {workout.rationale && (
            <div className="mt-0.5 text-xs text-neutral-400">{workout.rationale}</div>
          )}
        </div>
      </div>

      <div className="mt-2 divide-y divide-line/5 rounded-xl bg-neutral-950/40 px-3 py-1">
        {(workout.steps || []).map((s, i) =>
          s.kind === "repeat" ? (
            <div key={i} className="py-1">
              <div className="flex items-center gap-2 py-1 text-sm">
                <span className="h-2 w-2 shrink-0 rounded-full"
                  style={{ background: KIND_COLORS.repeat }} />
                <span className="font-medium text-neutral-100">Repeat ×{s.count}</span>
              </div>
              {(s.steps || []).map((c, k) => <StepRow key={k} step={c} indent />)}
            </div>
          ) : (
            <StepRow key={i} step={s} />
          )
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {state === "sent" ? (
          <span className="rounded-lg bg-emerald-500/10 px-3 py-1.5 text-sm text-emerald-300">
            ✓ Sent — it'll be on your watch after its next sync
          </span>
        ) : state === "confirm" || state === "sending" ? (
          <>
            <label className="text-xs text-neutral-400">Schedule for</label>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
              className="rounded-lg border border-line/10 bg-neutral-950/60 px-2 py-1.5 text-sm text-neutral-100" />
            <button onClick={send} disabled={state === "sending"}
              className="rounded-lg bg-amber-500/90 px-3 py-1.5 text-sm font-medium text-neutral-950 hover:bg-amber-400 disabled:opacity-50">
              {state === "sending" ? "Sending…" : "Confirm — send to Garmin"}
            </button>
            <button onClick={() => setState("idle")} disabled={state === "sending"}
              className="rounded-lg px-3 py-1.5 text-sm text-neutral-400 hover:text-neutral-200">
              Cancel
            </button>
          </>
        ) : (
          <button onClick={() => setState("confirm")}
            className="rounded-lg border border-amber-500/40 px-3 py-1.5 text-sm text-amber-300 hover:bg-amber-500/10">
            Send to watch…
          </button>
        )}
        {state === "error" && (
          <span className="text-sm text-red-400">Failed: {error}</span>
        )}
      </div>
    </Card>
  );
}
