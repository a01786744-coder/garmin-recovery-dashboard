import React from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import Card from "./ui/Card.jsx";
import SectionTitle from "./ui/SectionTitle.jsx";
import { fmtDay } from "../format.js";
import { sportGroup, SPORT_COLORS } from "../sports.js";

// Weekly training volume, stacked by sport group (last 8 weeks, hours).
export default function SportVolume({ activities }) {
  const acts = activities || [];
  if (!acts.length) return null;

  // Bucket by ISO week start (Monday).
  const weeks = {};
  for (const a of acts) {
    if (!a.date || !a.duration_s) continue;
    const d = new Date(a.date + "T12:00:00");
    d.setDate(d.getDate() - ((d.getDay() + 6) % 7));   // back to Monday
    const wk = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    const g = sportGroup(a.type);
    weeks[wk] = weeks[wk] || { week: wk };
    weeks[wk][g] = (weeks[wk][g] || 0) + a.duration_s / 3600;
  }
  const data = Object.values(weeks).sort((a, b) => a.week.localeCompare(b.week)).slice(-8);
  if (!data.length) return null;
  const groups = Object.keys(SPORT_COLORS).filter((g) => data.some((w) => w[g]));

  return (
    <Card>
      <SectionTitle sub="Hours per week, by sport">Weekly volume</SectionTitle>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: 0 }}>
          <XAxis dataKey="week" stroke="#52525b" fontSize={10} tickLine={false}
            axisLine={false} tickFormatter={(w) => fmtDay(w)} />
          <YAxis stroke="#52525b" fontSize={10} width={28} tickLine={false}
            axisLine={false} tickFormatter={(v) => `${v}h`} />
          <Tooltip
            labelFormatter={(w) => `Week of ${fmtDay(w)}`}
            formatter={(v, name) => [`${Math.round(v * 10) / 10} h`, name]}
            contentStyle={{ background: "#18181b", border: "1px solid #27272a",
              borderRadius: 8, color: "#fff", fontSize: 12 }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {groups.map((g) => (
            <Bar key={g} dataKey={g} stackId="v" fill={SPORT_COLORS[g]}
              maxBarSize={34} radius={[2, 2, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
