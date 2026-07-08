import React from "react";
import Grid from "../components/ui/Grid.jsx";
import Card from "../components/ui/Card.jsx";
import StatTile from "../components/ui/StatTile.jsx";
import MiniArea from "../components/ui/MiniArea.jsx";
import SectionTitle from "../components/ui/SectionTitle.jsx";
import NoData from "../components/ui/NoData.jsx";
import Badge from "../components/ui/Badge.jsx";
import { ACCENT } from "../theme.js";
import { secsToHms, round, num, titleCase, fmtDay } from "../format.js";
import { visible } from "../caps.js";
import MonthHeatmap from "../components/MonthHeatmap.jsx";

// Garmin personal-record type labels + how to format the value. Types not in
// this map are hidden rather than shown as a raw "record N".
const PR_TYPES = {
  1: ["1 km", "time"], 2: ["1 mile", "time"], 3: ["5 km", "time"],
  4: ["10 km", "time"], 5: ["Half marathon", "time"], 6: ["Marathon", "time"],
  7: ["Longest run", "dist"], 8: ["Longest ride", "dist"],
  9: ["Total ascent (ride)", "dist"],
  12: ["Most steps (day)", "steps"], 13: ["Most steps (week)", "steps"],
  14: ["Most steps (month)", "steps"],
  15: ["Step-goal streak (best)", "days"],
  16: ["Step-goal streak (current)", "days"],
};
function prLabel(t) { return (PR_TYPES[t] || [titleCase(`record ${t}`)])[0]; }
function prValue(t, v) {
  const kind = (PR_TYPES[t] || [null, "raw"])[1];
  if (v == null) return "—";
  if (kind === "time") return secsToHms(v);
  if (kind === "dist") return v >= 1000 ? `${(v / 1000).toFixed(2)} km` : `${round(v)} m`;
  if (kind === "steps") return Math.round(v).toLocaleString();
  if (kind === "days") return `${round(v)} ${v === 1 ? "day" : "days"}`;
  return num(v, 1);
}

const ENDUR_CLASS = ["—", "Untrained", "Novice", "Intermediate", "Trained",
  "Well trained", "Expert", "Superior", "Elite"];

export default function Trends({ today, trends, caps, onOpen }) {
  const perf = today?.perf || {};
  const records = today?.records || [];
  const hrv = (trends?.hrv || []).map((d) => ({ x: d.date, y: d.value }));
  const rhr = (trends?.rhr || []).map((d) => ({ x: d.date, y: d.value }));
  const show = (cat) => visible(caps, cat);

  return (
    <div className="space-y-4">
      <MonthHeatmap />
      <Grid className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {show("hrv") && (
        <Card onClick={() => onOpen("hrv")} className="cursor-pointer">
          <SectionTitle sub="14-day overnight average (ms)">HRV trend</SectionTitle>
          <MiniArea data={hrv} color={ACCENT.hrv} height={170} area={false}
            xTickFormatter={(d) => (typeof d === "string" ? fmtDay(d) : "")} />
        </Card>
        )}
        {show("rhr") && (
        <Card onClick={() => onOpen("rhr")} className="cursor-pointer">
          <SectionTitle sub="14-day (bpm)">Resting HR trend</SectionTitle>
          <MiniArea data={rhr} color={ACCENT.rhr} height={170} area={false}
            xTickFormatter={(d) => (typeof d === "string" ? fmtDay(d) : "")} />
        </Card>
        )}
      </Grid>

      <Grid className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {show("vo2max") && <StatTile label="VO₂max" value={perf.vo2max} digits={0} accent="#22c55e" onClick={() => onOpen("vo2max")} />}
        {show("vo2max") && <StatTile label="Fitness age" value={perf.fitness_age} accent="#38bdf8" />}
        {show("endurance") && (
        <StatTile label="Endurance" value={perf.endurance_score} accent="#a78bfa"
          sub={perf.endurance_class != null ? ENDUR_CLASS[perf.endurance_class] : null}
          onClick={() => onOpen("endurance")} />
        )}
        {show("acclimation") && <StatTile label="Heat acclim." value={perf.heat_acclimation} unit="%" accent="#f97316" />}
      </Grid>

      <Grid className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {show("race_predictions") && (
        <Card>
          <SectionTitle sub="Garmin race time predictions">Race predictions</SectionTitle>
          {["race_5k", "race_10k", "race_hm", "race_marathon"].every((k) => perf[k] == null) ? (
            <NoData />
          ) : (
            <div className="grid grid-cols-2 gap-3">
              {[["race_5k", "5K"], ["race_10k", "10K"], ["race_hm", "Half"], ["race_marathon", "Marathon"]].map(
                ([k, label]) => (
                  <div key={k} className="rounded-xl bg-neutral-950/40 p-3">
                    <div className="text-xs text-neutral-500">{label}</div>
                    <div className="text-xl font-bold text-neutral-50">{secsToHms(perf[k])}</div>
                  </div>
                )
              )}
            </div>
          )}
        </Card>
        )}

        {show("personal_records") && (
        <Card>
          <SectionTitle sub="All-time bests">Personal records</SectionTitle>
          {records.filter((r) => PR_TYPES[r.type_id]).length === 0 ? (
            <NoData />
          ) : (
            <ul className="divide-y divide-line/5 max-h-[260px] overflow-y-auto">
              {records.filter((r) => PR_TYPES[r.type_id]).map((r) => (
                <li key={r.id} className="flex items-center justify-between py-2 text-sm">
                  <div>
                    <div className="text-neutral-200">{prLabel(r.type_id)}</div>
                    <div className="text-[11px] text-neutral-600">
                      {(r.start_time || "").slice(0, 10)} · {r.activity_name || ""}
                    </div>
                  </div>
                  <span className="font-semibold text-neutral-100">{prValue(r.type_id, r.value)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        )}
      </Grid>
    </div>
  );
}
