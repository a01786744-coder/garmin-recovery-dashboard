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
import CompareChart from "../components/CompareChart.jsx";
import LongTrends from "../components/LongTrends.jsx";
import { PR_TYPES, prLabel, prValue } from "../records.js";
import RacePredictorChart from "../components/RacePredictorChart.jsx";

const ENDUR_CLASS = ["—", "Untrained", "Novice", "Intermediate", "Trained",
  "Well trained", "Expert", "Superior", "Elite"];

function HrvStatusBadge({ status }) {
  if (!status) return null;
  const s = String(status).toUpperCase();
  const color = s === "BALANCED" ? "#22c55e"
    : s === "UNBALANCED" || s === "LOW" ? "#ef4444"
    : s === "POOR" ? "#f97316" : "#52525b";
  return <Badge color={color}>{titleCase(status.toLowerCase())}</Badge>;
}

// Weight is stored in grams; show kg or lb per the user's unit setting.
function weightStr(grams, units) {
  if (grams == null) return null;
  return units === "imperial"
    ? `${(grams * 0.00220462).toFixed(1)} lb`
    : `${(grams / 1000).toFixed(1)} kg`;
}

export default function Trends({ today, trends, caps, units, onOpen }) {
  const perf = today?.perf || {};
  const m = today?.metrics || {};
  const records = today?.records || [];
  const hrv = (trends?.hrv || []).map((d) => ({ x: d.date, y: d.value }));
  const rhr = (trends?.rhr || []).map((d) => ({ x: d.date, y: d.value }));
  const show = (cat) => visible(caps, cat);
  const tol = perf.running_tolerance_ceiling
    ? Math.min(1, (perf.running_tolerance_load || 0) / perf.running_tolerance_ceiling)
    : null;

  return (
    <div className="space-y-4">
      <CompareChart />
      <MonthHeatmap />
      <Grid className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {show("hrv") && (
        <Card onClick={() => onOpen("hrv")} className="cursor-pointer">
          <div className="flex items-center justify-between">
            <SectionTitle sub="14-day overnight average (ms)">HRV trend</SectionTitle>
            <HrvStatusBadge status={m.hrv_status} />
          </div>
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

      <LongTrends />

      <Grid className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {show("vo2max") && <StatTile label="VO₂max" value={perf.vo2max} digits={0} accent="#22c55e" onClick={() => onOpen("vo2max")} />}
        {show("vo2max") && perf.fitness_age != null &&
          <StatTile label="Fitness age" value={perf.fitness_age} digits={0} unit="yrs" accent="#38bdf8" />}
        {show("hill_score") && <StatTile label="Hill score" value={perf.hill_score} digits={0} accent="#f59e0b" />}
        {show("endurance") && (
        <StatTile label="Endurance" value={perf.endurance_score} accent="#a78bfa"
          sub={perf.endurance_class != null ? ENDUR_CLASS[perf.endurance_class] : null}
          onClick={() => onOpen("endurance")} />
        )}
        {show("body_weight") && perf.body_weight_g != null &&
          <StatTile label="Body weight" value={weightStr(perf.body_weight_g, units)} accent="#a3e635" />}
        {show("acclimation") && <StatTile label="Heat acclim." value={perf.heat_acclimation} unit="%" accent="#f97316" />}
        {show("acclimation") && perf.altitude_acclimation != null &&
          <StatTile label="Altitude acclim." value={perf.altitude_acclimation} digits={0} unit="m" accent="#f97316" />}
        {show("lactate_threshold") && perf.lt_hr != null &&
          <StatTile label="Threshold HR" value={perf.lt_hr} digits={0} unit="bpm" accent="#ef4444" />}
        {show("lactate_threshold") && perf.lt_power != null &&
          <StatTile label="Run FTP" value={perf.lt_power} digits={0} unit="W" accent="#eab308" />}
      </Grid>

      {show("running_tolerance") && perf.running_tolerance_ceiling != null && (
        <Card>
          <SectionTitle sub="This week's impact load vs your tolerance ceiling">Running tolerance</SectionTitle>
          <div className="mt-2 h-3 w-full overflow-hidden rounded-full bg-neutral-800">
            <div className="h-full rounded-full transition-all"
              style={{ width: `${Math.round((tol || 0) * 100)}%`,
                background: tol > 0.9 ? "#ef4444" : tol > 0.7 ? "#f59e0b" : "#22c55e" }} />
          </div>
          <div className="mt-2 flex justify-between text-xs text-neutral-400">
            <span>Load {Math.round(perf.running_tolerance_load).toLocaleString()}</span>
            <span>Ceiling {Math.round(perf.running_tolerance_ceiling).toLocaleString()}</span>
          </div>
        </Card>
      )}

      {show("race_predictions") && (
      <Card>
        <SectionTitle sub="Garmin's predicted finish times, tracked over time">Race predictor</SectionTitle>
        <RacePredictorChart perf={trends?.perf} />
      </Card>
      )}

      <Grid className="grid grid-cols-1 lg:grid-cols-2 gap-4">
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
