import React from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ReferenceArea, ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import NoData from "./ui/NoData.jsx";
import { fmtDay, num } from "../format.js";

// Injury-risk zones for acute:chronic workload ratio (sports-science
// consensus bands; Garmin supplies the daily ratio itself).
const ZONES = [
  { y1: 0.0, y2: 0.8, color: "#71717a", label: "Undertraining" },
  { y1: 0.8, y2: 1.3, color: "#22c55e", label: "Optimal" },
  { y1: 1.3, y2: 1.5, color: "#eab308", label: "Caution" },
  { y1: 1.5, y2: 2.0, color: "#ef4444", label: "High risk" },
];

// ACWR history with colored risk bands. `days` = trends day rows.
export default function AcwrChart({ days, height = 190 }) {
  const data = (days || [])
    .filter((d) => d.date)
    .map((d) => ({ x: d.date, y: d.acwr_ratio ?? null }));
  if (!data.some((d) => d.y != null)) return <NoData height={height} />;

  const maxY = Math.max(2, ...data.map((d) => d.y ?? 0));
  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
          {ZONES.map((z) => (
            <ReferenceArea key={z.label} y1={z.y1} y2={Math.min(z.y2, maxY)}
              fill={z.color} fillOpacity={0.08} />
          ))}
          <ReferenceLine y={1.3} stroke="#eab308" strokeOpacity={0.35} strokeDasharray="4 4" />
          <ReferenceLine y={1.5} stroke="#ef4444" strokeOpacity={0.35} strokeDasharray="4 4" />
          <XAxis dataKey="x" tickFormatter={fmtDay} stroke="#52525b" fontSize={10}
            tickLine={false} axisLine={false} minTickGap={40} />
          <YAxis domain={[0, maxY]} stroke="#52525b" fontSize={10} width={30}
            tickLine={false} axisLine={false} tickFormatter={(v) => num(v, 1)} />
          <Tooltip
            contentStyle={{ background: "#18181b", border: "1px solid #27272a", borderRadius: 8, color: "#fff", fontSize: 12 }}
            labelFormatter={fmtDay}
            formatter={(v) => [num(v, 2), "ACWR"]}
          />
          <Line type="monotone" dataKey="y" stroke="#38bdf8" strokeWidth={2}
            dot={false} connectNulls={false} isAnimationActive />
        </LineChart>
      </ResponsiveContainer>
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-neutral-500">
        {ZONES.map((z) => (
          <span key={z.label} className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-sm" style={{ background: z.color, opacity: 0.7 }} />
            {z.label} {z.y2 >= 2 ? `>${num(z.y1, 1)}` : `${num(z.y1, 1)}–${num(z.y2, 1)}`}
          </span>
        ))}
      </div>
    </div>
  );
}
