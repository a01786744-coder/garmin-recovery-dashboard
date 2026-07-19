import React from "react";
import { round, minutesToHm } from "../format.js";

// "Why this score" blocks for the two custom metrics, fed by the backend's
// recovery_explain / strain_explain payloads (no client-side math).

function dirChip(z) {
  if (z == null) return null;
  if (z >= 0.15) return <span className="text-emerald-400">▲ pushes it up</span>;
  if (z <= -0.15) return <span className="text-red-400">▼ drags it down</span>;
  return <span className="text-neutral-500">≈ near baseline</span>;
}

function Row({ label, hint, value, z }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-neutral-900/70 px-3 py-2 text-sm">
      <div>
        <div className="text-neutral-200">{label}</div>
        <div className="text-[11px] text-neutral-600">{hint}</div>
      </div>
      <div className="text-right">
        <div className="text-neutral-100">{value}</div>
        <div className="text-[11px]">{dirChip(z)}</div>
      </div>
    </div>
  );
}

const WEIGHT_LABELS = [["hrv", "HRV"], ["rhr", "resting HR"], ["sleep", "sleep"],
                       ["resp", "respiration"], ["temp", "skin temp"], ["spo2", "SpO2"]];

export function RecoveryWhy({ explain }) {
  if (!explain) return null;
  const { hrv, rhr, sleep, resp, temp, spo2, weights } = explain;
  const sleepValue = sleep && (
    <>
      {sleep.total_min != null ? minutesToHm(sleep.total_min) : "—"}
      {sleep.need_min ? <span className="text-neutral-500"> / need {minutesToHm(sleep.need_min)}</span> : null}
      {sleep.score != null ? <span className="text-neutral-500"> · quality {round(sleep.score)}</span> : null}
    </>
  );
  const weightLine = WEIGHT_LABELS
    .filter(([k]) => weights?.[k] != null)
    .map(([k, label]) => `${label} ${Math.round(weights[k] * 100)}%`)
    .join(" · ");

  return (
    <div className="mb-5">
      <div className="mb-2 text-sm text-neutral-400">Why this score</div>
      <div className="space-y-2">
        <Row label="Overnight HRV" hint="higher than baseline is good"
          value={<>{round(hrv.today)} ms<span className="text-neutral-500"> vs {hrv.baseline} baseline</span></>}
          z={hrv.z} />
        <Row label="Resting HR" hint="lower than baseline is good"
          value={<>{round(rhr.today)} bpm<span className="text-neutral-500"> vs {rhr.baseline} baseline</span></>}
          z={rhr.z} />
        {sleep && (
          <Row label="Sleep" hint="duration vs your need + quality" value={sleepValue} z={sleep.z} />
        )}
        {resp && (
          <Row label="Sleep respiration" hint="elevated breathing can flag illness"
            value={<>{resp.today} br/min<span className="text-neutral-500"> vs {resp.baseline} baseline</span></>}
            z={resp.z} />
        )}
        {temp && (
          <Row label="Skin temperature" hint="deviation from baseline, either direction"
            value={<>{temp.dev_c > 0 ? "+" : ""}{temp.dev_c} °C</>} z={temp.z} />
        )}
        {spo2 && (
          <Row label="Sleep SpO2" hint="drops below your baseline can flag illness"
            value={<>{round(spo2.today)}%<span className="text-neutral-500"> vs {spo2.baseline} baseline</span></>}
            z={spo2.z} />
        )}
      </div>
      <p className="mt-1.5 text-[11px] text-neutral-600">
        {weightLine} — all against your own recent baseline. Factors without
        data today drop out and the rest re-balance.
      </p>
    </div>
  );
}

export function StrainWhy({ explain }) {
  if (!explain) return null;
  const { workout, daily, total } = explain;
  const wPct = total > 0 ? (workout / total) * 100 : 0;
  return (
    <div className="mb-5">
      <div className="mb-2 text-sm text-neutral-400">Why this score</div>
      <div className="rounded-lg bg-neutral-900/70 px-3 py-2.5 text-sm">
        <div className="mb-2 flex h-2.5 overflow-hidden rounded-full bg-neutral-800">
          {total > 0 && <div className="h-full bg-orange-500" style={{ width: `${wPct}%` }} />}
          {total > 0 && <div className="h-full bg-sky-500" style={{ width: `${100 - wPct}%` }} />}
        </div>
        <div className="flex justify-between text-[13px]">
          <span className="text-orange-400">Workouts {round(workout)}</span>
          <span className="text-sky-400">Daily life {round(daily)}</span>
          <span className="text-neutral-400">load {round(total)}</span>
        </div>
      </div>
      <p className="mt-1.5 text-[11px] text-neutral-600">
        Workouts use Garmin's training load (or heart-rate-zone TRIMP when it's
        missing). Daily life = steps above 3k + intensity minutes + floors; it
        counts at half on workout days because workouts already include their
        own steps.
      </p>
    </div>
  );
}
