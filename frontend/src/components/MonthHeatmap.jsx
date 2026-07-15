import React, { useState } from "react";
import Card from "./ui/Card.jsx";
import SectionTitle from "./ui/SectionTitle.jsx";
import { getTrends } from "../api.js";
import { useAsync } from "../useApi.js";
import { BAND, band } from "../theme.js";
import { localToday } from "../format.js";

const METRICS = [
  ["recovery_score", "Recovery"],
  ["sleep_score", "Sleep"],
  ["strain_score", "Strain"],
];

const DOW = ["M", "T", "W", "T", "F", "S", "S"];

function cellColor(metric, v) {
  if (v == null) return null;
  if (metric === "recovery_score") return BAND[band(v)];        // band colors
  const alpha = 0.25 + 0.75 * Math.min(1, Math.max(0, v) / 100); // value scale
  return metric === "sleep_score"
    ? `rgba(139, 92, 246, ${alpha.toFixed(2)})`                  // purple
    : `rgba(249, 115, 22, ${alpha.toFixed(2)})`;                 // orange
}

// One calendar grid for a single metric.
function MetricGrid({ metric, label, cells, byDate }) {
  return (
    <div className="min-w-0">
      <div className="mb-1.5 text-center text-xs font-medium text-neutral-400">{label}</div>
      <div className="grid grid-cols-7 gap-1">
        {DOW.map((d, i) => (
          <div key={`h${i}`} className="text-center text-[10px] text-neutral-600">{d}</div>
        ))}
        {cells.map((c, i) => {
          if (!c) return <div key={`e${i}`} />;
          const value = byDate[c.iso]?.[metric];
          const bg = c.future ? null : cellColor(metric, value);
          return (
            <div key={c.iso} title={`${c.iso}: ${value ?? "no data"}`}
              className="flex aspect-square items-center justify-center rounded-md text-[10px]"
              style={{
                background: bg || (c.future ? "transparent" : "rgb(var(--neutral-800))"),
                color: bg ? "#fff" : "rgb(var(--neutral-500))",
                opacity: c.future ? 0.25 : 1,
              }}>
              {c.day}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Month calendars for the three daily scores, shown side by side
// (Whoop-style calendar view). Data comes from the existing /api/trends
// endpoint; gray = no data, blank = future.
export default function MonthHeatmap() {
  const [month, setMonth] = useState(() => {
    const d = new Date();
    return new Date(d.getFullYear(), d.getMonth(), 1);
  });
  const trends = useAsync(() => getTrends(190), []);
  const byDate = {};
  for (const r of trends.data?.days || []) byDate[r.date] = r;

  const now = new Date();
  const isCurrentMonth = month.getFullYear() === now.getFullYear()
    && month.getMonth() === now.getMonth();
  const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const lead = (month.getDay() + 6) % 7;   // Monday-first offset
  const todayStr = localToday();

  const cells = [];
  for (let i = 0; i < lead; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) {
    const iso = `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    cells.push({ day: d, iso, future: iso > todayStr });
  }

  const title = month.toLocaleString(undefined, { month: "long", year: "numeric" });

  return (
    <Card>
      <SectionTitle sub="Color by day — spot your patterns">Month view</SectionTitle>

      <div className="mb-3 mt-1 flex items-center justify-center gap-3 text-sm">
        <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}
          className="rounded-md px-2 py-0.5 text-neutral-400 hover:text-neutral-100">‹</button>
        <span className="min-w-[10rem] text-center text-neutral-300">{title}</span>
        <button disabled={isCurrentMonth}
          onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}
          className="rounded-md px-2 py-0.5 text-neutral-400 enabled:hover:text-neutral-100 disabled:opacity-30">›</button>
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3 sm:gap-4">
        {METRICS.map(([metric, label]) => (
          <MetricGrid key={metric} metric={metric} label={label}
            cells={cells} byDate={byDate} />
        ))}
      </div>
    </Card>
  );
}
