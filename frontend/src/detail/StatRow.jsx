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
