import React, { useState } from "react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";
import NoData from "./ui/NoData.jsx";
import { secsToHms, fmtDay } from "../format.js";

// Garmin's daily race-time predictions (already stored in perf_metrics). Lower
// is faster, so an improving athlete's line trends DOWN.
const DISTANCES = [
  { key: "race_5k", label: "5K", color: "#22c55e" },
  { key: "race_10k", label: "10K", color: "#38bdf8" },
  { key: "race_hm", label: "Half", color: "#a78bfa" },
  { key: "race_marathon", label: "Marathon", color: "#f97316" },
];

function delta(first, last) {
  if (first == null || last == null) return null;
  const d = Math.round(last - first);       // seconds; negative = faster
  if (d === 0) return { text: "no change", tone: "flat" };
  const abs = secsToHms(Math.abs(d));
  return d < 0
    ? { text: `▼ ${abs} faster`, tone: "good" }
    : { text: `▲ ${abs} slower`, tone: "bad" };
}

export default function RacePredictorChart({ perf }) {
  const rows = perf || [];
  // Which distances actually have any data?
  const available = DISTANCES.filter((d) => rows.some((r) => r[d.key] != null));
  const [sel, setSel] = useState(available[0]?.key || "race_5k");
  if (!available.length) return <NoData height={200} />;

  const dist = available.find((d) => d.key === sel) || available[0];
  const series = rows
    .filter((r) => r.date && r[dist.key] != null)
    .map((r) => ({ x: r.date, y: r[dist.key] }));

  const first = series[0]?.y;
  const last = series[series.length - 1]?.y;
  const best = series.reduce((m, p) => Math.min(m, p.y), Infinity);
  const d = delta(first, last);
  const toneColor = d?.tone === "good" ? "#22c55e" : d?.tone === "bad" ? "#ef4444" : "#a1a1aa";
  const gid = "rp" + dist.key;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-1.5">
        {available.map((dd) => (
          <button key={dd.key} onClick={() => setSel(dd.key)}
            className={"rounded-lg px-3 py-1.5 text-sm font-medium transition-colors " +
              (dd.key === sel
                ? "text-neutral-50 ring-1 ring-line/20"
                : "text-neutral-400 hover:text-neutral-200")}
            style={dd.key === sel ? { background: `${dd.color}22` } : undefined}>
            <span className="mr-1.5 inline-block h-2 w-2 rounded-full align-middle" style={{ background: dd.color }} />
            {dd.label}
          </button>
        ))}
      </div>

      <div className="mb-3 flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-neutral-500">Predicted now</div>
          <div className="text-2xl font-bold tabular-nums text-neutral-50">{secsToHms(last)}</div>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-wider text-neutral-500">Best</div>
          <div className="text-lg font-semibold tabular-nums text-neutral-200">{secsToHms(best)}</div>
        </div>
        {d && (
          <div>
            <div className="text-[11px] uppercase tracking-wider text-neutral-500">Over {series.length} days</div>
            <div className="text-sm font-semibold tabular-nums" style={{ color: toneColor }}>{d.text}</div>
          </div>
        )}
      </div>

      <ResponsiveContainer width="100%" height={190}>
        <AreaChart data={series} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={dist.color} stopOpacity={0.32} />
              <stop offset="100%" stopColor={dist.color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="x" tickFormatter={fmtDay} stroke="#52525b" fontSize={10}
            tickLine={false} axisLine={false} minTickGap={38} />
          <YAxis domain={["auto", "auto"]} stroke="#52525b" fontSize={10}
            width={54} tickLine={false} axisLine={false} tickFormatter={secsToHms} />
          <Tooltip
            contentStyle={{ background: "#18181b", border: "1px solid #27272a", borderRadius: 8, color: "#fff", fontSize: 12 }}
            labelFormatter={fmtDay} formatter={(v) => [secsToHms(v), dist.label]} />
          <Area type="monotone" dataKey="y" stroke={dist.color} strokeWidth={2}
            fill={`url(#${gid})`} dot={false} isAnimationActive />
        </AreaChart>
      </ResponsiveContainer>
      <p className="mt-1.5 text-[11px] text-neutral-600">
        Garmin's predicted finish time from your training —
        <span className="text-neutral-500"> lower is faster, so the line drops as you improve.</span>
      </p>
    </div>
  );
}
