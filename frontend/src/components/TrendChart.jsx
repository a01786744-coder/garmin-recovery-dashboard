import React from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
export default function TrendChart({ title, data, color }) {
  const hasData = data && data.some((d) => d.value != null);
  return (
    <div className="bg-neutral-900 rounded-xl p-4">
      <div className="text-neutral-300 text-sm mb-2">{title}</div>
      {!hasData ? (
        <div className="h-40 flex items-center justify-center text-neutral-600 text-sm">No data</div>
      ) : (
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={data}>
            <XAxis dataKey="date" hide />
            <YAxis domain={["auto", "auto"]} stroke="#52525b" fontSize={11} width={28} />
            <Tooltip contentStyle={{ background: "#18181b", border: "none", color: "#fff" }} />
            <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2}
              dot={false} connectNulls={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
