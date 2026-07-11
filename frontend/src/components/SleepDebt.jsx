import React from "react";
import {
  BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import Card from "./ui/Card.jsx";
import SectionTitle from "./ui/SectionTitle.jsx";
import { fmtDay } from "../format.js";

function hm(mins) {
  const m = Math.abs(Math.round(mins));
  const h = Math.floor(m / 60);
  return h > 0 ? `${h}h ${m % 60}m` : `${m}m`;
}

// Cumulative sleep debt (Whoop/Oura-style): how far behind (or ahead of) your
// Garmin sleep need you are over the last 7/14 days. Backend counts only days
// with real data — never assumes a missing night.
export default function SleepDebt({ debt }) {
  if (!debt) return null;
  const inDebt = debt.debt7_min > 0;
  const data = (debt.series || []).map((r) => ({ date: r.date, y: r.deficit_min }));

  return (
    <Card>
      <SectionTitle sub="Need minus slept, per night — bars above the line are lost sleep">
        Sleep debt
      </SectionTitle>
      <div className="mb-2 flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <div>
          <span className={"text-2xl font-bold " + (inDebt ? "text-amber-400" : "text-emerald-400")}>
            {inDebt ? `${hm(debt.debt7_min)} short` : `${hm(debt.debt7_min)} ahead`}
          </span>
          <span className="ml-2 text-xs text-neutral-500">last 7 days ({debt.days7} with data)</span>
        </div>
        <div className="text-sm text-neutral-400">
          14-day: <b className={debt.debt14_min > 0 ? "text-amber-400" : "text-emerald-400"}>
            {debt.debt14_min > 0 ? `${hm(debt.debt14_min)} short` : `${hm(debt.debt14_min)} ahead`}
          </b>
          <span className="ml-1 text-xs text-neutral-600">({debt.days14} with data)</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <BarChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: 0 }}>
          <XAxis dataKey="date" stroke="#52525b" fontSize={10} tickLine={false}
            axisLine={false} minTickGap={30}
            tickFormatter={(d) => (typeof d === "string" ? fmtDay(d) : "")} />
          <YAxis stroke="#52525b" fontSize={10} width={34} tickLine={false}
            axisLine={false} tickFormatter={(v) => `${Math.round(v / 60)}h`} />
          <ReferenceLine y={0} stroke="#71717a" />
          <Tooltip
            labelFormatter={(d) => fmtDay(d)}
            formatter={(v) => [v == null ? "—" : (v > 0 ? `${hm(v)} short` : `${hm(v)} extra`), "vs need"]}
            contentStyle={{ background: "#18181b", border: "1px solid #27272a",
              borderRadius: 8, color: "#fff", fontSize: 12 }} />
          <Bar dataKey="y" maxBarSize={16} radius={[3, 3, 0, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.y == null ? "transparent" : d.y > 0 ? "#eab308" : "#22c55e"}
                fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
