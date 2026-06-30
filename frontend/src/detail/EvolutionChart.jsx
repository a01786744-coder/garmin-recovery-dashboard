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
        <ReferenceLine y={avg} stroke="#71717a" strokeDasharray="4 4"
          label={{ value: `avg ${Math.round(avg)}`, fill: "#71717a", fontSize: 10, position: "insideTopRight" }} />
        <Area type="monotone" dataKey="y" stroke={color} strokeWidth={2} fill={`url(#${gid})`}
          dot={false} connectNulls={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
