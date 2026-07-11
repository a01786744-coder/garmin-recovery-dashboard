import React, { useState } from "react";
import Grid from "./ui/Grid.jsx";
import Card from "./ui/Card.jsx";
import MiniArea from "./ui/MiniArea.jsx";
import SectionTitle from "./ui/SectionTitle.jsx";
import { getTrends } from "../api.js";
import { useAsync } from "../useApi.js";
import { ACCENT } from "../theme.js";
import { fmtDay } from "../format.js";

const RANGES = [[30, "30d"], [90, "90d"], [183, "6m"], [365, "1y"]];

// Long-term lines for metrics that previously only showed today's number.
// Daily metrics come from trends.days; VO2max/fitness age from the perf series.
const CHARTS = [
  ["Body Battery", "days", "body_battery", ACCENT.body],
  ["Waking respiration", "days", "resp_waking", ACCENT.resp],
  ["VO₂max", "perf", "vo2max", "#22c55e"],
  ["Fitness age", "perf", "fitness_age", "#38bdf8"],
];

export default function LongTrends() {
  const [days, setDays] = useState(90);
  const trends = useAsync(() => getTrends(days), [days]);
  const tick = (d) => (typeof d === "string" ? fmtDay(d) : "");

  const seriesFor = (source, field) => {
    const rows = trends.data?.[source === "days" ? "days" : "perf"] || [];
    return rows.map((r) => ({ x: r.date, y: r[field] }));
  };

  return (
    <Card>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <SectionTitle sub="Metrics that move slowly — watch the long arc">
          Long-term trends
        </SectionTitle>
        <div className="flex gap-1 rounded-lg border border-line/10 bg-neutral-950/60 p-0.5 text-xs">
          {RANGES.map(([d, label]) => (
            <button key={d} onClick={() => setDays(d)}
              className={"rounded-md px-2.5 py-1 transition-colors " +
                (days === d ? "bg-line/10 text-neutral-50" : "text-neutral-400 hover:text-neutral-200")}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <Grid className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {CHARTS.map(([label, source, field, color]) => (
          <div key={field}>
            <div className="mb-1 text-xs text-neutral-500">{label}</div>
            <MiniArea data={seriesFor(source, field)} color={color} height={130}
              area={false} xTickFormatter={tick} />
          </div>
        ))}
      </Grid>
    </Card>
  );
}
