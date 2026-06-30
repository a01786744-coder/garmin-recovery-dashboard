import React from "react";
import {
  AreaChart, Area, Line, LineChart, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ReferenceArea,
} from "recharts";
import NoData from "./NoData.jsx";

// Intraday/series chart. data: [{x, y}] where y may be null (gaps preserved).
export default function MiniArea({
  data,
  color = "#38bdf8",
  height = 150,
  area = true,
  band, // optional {low, high} reference band (e.g. HRV baseline)
  yDomain = ["auto", "auto"],
  xTickFormatter,
  yWidth = 30,
}) {
  const hasData = data && data.some((d) => d.y != null);
  if (!hasData) return <NoData height={height} />;
  const Chart = area ? AreaChart : LineChart;
  const gid = "g" + color.replace("#", "");
  return (
    <ResponsiveContainer width="100%" height={height}>
      <Chart data={data} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        {band && band.low != null && band.high != null && (
          <ReferenceArea y1={band.low} y2={band.high} fill="#808080" fillOpacity={0.12} />
        )}
        <XAxis dataKey="x" hide={!xTickFormatter} tickFormatter={xTickFormatter}
          stroke="#52525b" fontSize={10} tickLine={false} axisLine={false} minTickGap={40} />
        <YAxis domain={yDomain} stroke="#52525b" fontSize={10} width={yWidth}
          tickLine={false} axisLine={false} />
        <Tooltip
          contentStyle={{ background: "#18181b", border: "1px solid #27272a", borderRadius: 8, color: "#fff", fontSize: 12 }}
          labelFormatter={xTickFormatter || (() => "")}
        />
        {area ? (
          <Area type="monotone" dataKey="y" stroke={color} strokeWidth={2}
            fill={`url(#${gid})`} dot={false} connectNulls={false} isAnimationActive />
        ) : (
          <Line type="monotone" dataKey="y" stroke={color} strokeWidth={2}
            dot={false} connectNulls={false} isAnimationActive />
        )}
      </Chart>
    </ResponsiveContainer>
  );
}
