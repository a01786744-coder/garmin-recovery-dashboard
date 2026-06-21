import React from "react";
const STAGES = [
  ["deep_sleep_s", "Deep", "#1d4ed8"], ["light_sleep_s", "Light", "#3b82f6"],
  ["rem_sleep_s", "REM", "#8b5cf6"], ["awake_sleep_s", "Awake", "#52525b"],
];
export default function SleepStages({ metrics }) {
  const vals = STAGES.map(([k]) => metrics?.[k]);
  const total = vals.reduce((s, v) => s + (v || 0), 0);
  return (
    <div className="bg-neutral-900 rounded-xl p-4">
      <div className="text-neutral-300 text-sm mb-2">Last night sleep stages</div>
      {!total ? (
        <div className="h-10 flex items-center text-neutral-600 text-sm">No data</div>
      ) : (
        <>
          <div className="flex h-6 rounded overflow-hidden">
            {STAGES.map(([k, , c]) => (
              <div key={k} style={{ width: `${((metrics[k] || 0) / total) * 100}%`, background: c }} />
            ))}
          </div>
          <div className="flex gap-4 mt-2 text-xs text-neutral-400">
            {STAGES.map(([k, label, c]) => (
              <span key={k}><span style={{ color: c }}>■</span> {label} {Math.round((metrics[k] || 0) / 60)}m</span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
