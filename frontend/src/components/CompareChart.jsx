import React, { useState } from "react";
import {
  ComposedChart, Bar, Cell, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";
import Card from "./ui/Card.jsx";
import SectionTitle from "./ui/SectionTitle.jsx";
import NoData from "./ui/NoData.jsx";
import { getTrends } from "../api.js";
import { useAsync } from "../useApi.js";
import { BAND, band, ACCENT } from "../theme.js";
import { fmtDay } from "../format.js";

// Whoop-style overlay: Recovery as band-colored bars, a second metric as a
// line on the same 0-100 scale.
const PAIRS = [
  ["sleep_score", "Sleep vs Recovery", "Sleep", ACCENT.sleep],
  ["strain_score", "Strain vs Recovery", "Strain", ACCENT.strain],
];

const RANGES = [[30, "30d"], [60, "60d"], [90, "90d"], [183, "6m"], [365, "1y"]];

export default function CompareChart() {
  const [pair, setPair] = useState("sleep_score");
  const [days, setDays] = useState(30);
  const trends = useAsync(() => getTrends(days), [days]);
  const [, , lineLabel, lineColor] = PAIRS.find(([k]) => k === pair);

  const data = (trends.data?.days || []).map((r) => ({
    date: r.date,
    recovery: r.recovery_score,
    other: r[pair],
  }));
  const hasData = data.some((d) => d.recovery != null || d.other != null);

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <SectionTitle sub="Recovery bars (colored by zone) with an overlay line">
          Compare
        </SectionTitle>
        <div className="flex flex-wrap gap-2">
          <div className="flex gap-1 rounded-lg border border-line/10 bg-neutral-950/60 p-0.5 text-xs">
            {PAIRS.map(([k, , label]) => (
              <button key={k} onClick={() => setPair(k)}
                className={"rounded-md px-2.5 py-1 transition-colors " +
                  (pair === k ? "bg-line/10 text-neutral-50" : "text-neutral-400 hover:text-neutral-200")}>
                {label}
              </button>
            ))}
          </div>
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
      </div>

      {!hasData ? (
        <NoData height={220} />
      ) : (
        <ResponsiveContainer width="100%" height={230}>
          <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <XAxis dataKey="date" stroke="#52525b" fontSize={10} tickLine={false}
              axisLine={false} minTickGap={40}
              tickFormatter={(d) => (typeof d === "string" ? fmtDay(d) : "")} />
            <YAxis domain={[0, 100]} stroke="#52525b" fontSize={10} width={30}
              tickLine={false} axisLine={false} />
            <Tooltip
              labelFormatter={(d) => fmtDay(d)}
              formatter={(v, name) => [v == null ? "—" : Math.round(v),
                name === "recovery" ? "Recovery" : lineLabel]}
              contentStyle={{ background: "#18181b", border: "1px solid #27272a",
                borderRadius: 8, color: "#fff", fontSize: 12 }} />
            <Bar dataKey="recovery" radius={[3, 3, 0, 0]} maxBarSize={18}>
              {data.map((d, i) => (
                <Cell key={i} fill={band(d.recovery) ? BAND[band(d.recovery)] : "transparent"}
                  fillOpacity={0.85} />
              ))}
            </Bar>
            <Line type="monotone" dataKey="other" stroke={lineColor} strokeWidth={2}
              dot={false} connectNulls={false} />
          </ComposedChart>
        </ResponsiveContainer>
      )}

      <div className="mt-1 flex justify-center gap-5 text-[11px] text-neutral-500">
        <span><span className="mr-1 inline-block h-2 w-2 rounded-sm bg-emerald-500" />Recovery (bars, by zone)</span>
        <span><span className="mr-1 inline-block h-2 w-2 rounded-full"
          style={{ background: lineColor }} />{lineLabel} (line)</span>
      </div>
    </Card>
  );
}
