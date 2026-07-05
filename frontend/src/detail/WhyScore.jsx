import React from "react";
import { round } from "../format.js";

// "Why this score" blocks for the two custom metrics, fed by the backend's
// recovery_explain / strain_explain payloads (no client-side math).

function dirChip(z) {
  if (z == null) return null;
  if (z >= 0.15) return <span className="text-emerald-400">▲ pushes it up</span>;
  if (z <= -0.15) return <span className="text-red-400">▼ drags it down</span>;
  return <span className="text-neutral-500">≈ near baseline</span>;
}

export function RecoveryWhy({ explain }) {
  if (!explain) return null;
  const rows = [
    ["Overnight HRV", explain.hrv, "ms", "higher than baseline is good"],
    ["Resting HR", explain.rhr, "bpm", "lower than baseline is good"],
  ];
  return (
    <div className="mb-5">
      <div className="mb-2 text-sm text-neutral-400">Why this score</div>
      <div className="space-y-2">
        {rows.map(([label, r, unit, hint]) => (
          <div key={label} className="flex items-center justify-between rounded-lg bg-neutral-900/70 px-3 py-2 text-sm">
            <div>
              <div className="text-neutral-200">{label}</div>
              <div className="text-[11px] text-neutral-600">{hint}</div>
            </div>
            <div className="text-right">
              <div className="text-neutral-100">
                {round(r.today)} {unit}
                <span className="text-neutral-500"> vs {r.baseline} baseline</span>
              </div>
              <div className="text-[11px]">{dirChip(r.z)}</div>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-1.5 text-[11px] text-neutral-600">
        HRV counts {Math.round(explain.weights.hrv * 100)}%, resting HR{" "}
        {Math.round(explain.weights.rhr * 100)}% — both against your recent baseline.
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
        Daily life = steps + intensity minutes; it counts at half on workout days
        because workouts already include their own steps.
      </p>
    </div>
  );
}
