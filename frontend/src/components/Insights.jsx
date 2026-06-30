import React from "react";
import { motion } from "framer-motion";
import Card from "./ui/Card.jsx";
import Grid from "./ui/Grid.jsx";
import SectionTitle from "./ui/SectionTitle.jsx";
import NoData from "./ui/NoData.jsx";
import { visible } from "../caps.js";

function delta(d) {
  if (d == null) return null;
  const up = d > 0;
  return <span className={up ? "text-emerald-400" : d < 0 ? "text-red-400" : "text-neutral-500"}>
    {up ? "▲" : d < 0 ? "▼" : ""}{Math.abs(d)}</span>;
}

const RECAP_ROWS = [
  ["recovery_score", "Recovery"], ["sleep_score", "Sleep"],
  ["hrv_last_night", "HRV"], ["rhr", "Resting HR"], ["strain_score", "Strain"],
];

export default function InsightsSection({ insights, caps }) {
  if (!insights) return null;
  const { weekly, streaks, insights: auto = [], correlations = [] } = insights;
  const streakItems = [
    ["green_recovery", "green recovery days", caps == null || visible(caps, "hrv")],
    ["workout", "workout days", caps == null || visible(caps, "activities")],
    ["sleep_goal", "sleep-goal nights", caps == null || visible(caps, "sleep")],
    ["worn", "days worn", true],
  ].filter(([k, , ok]) => ok && (streaks?.[k] || 0) > 0);

  return (
    <Grid className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card>
        <SectionTitle>Insights</SectionTitle>
        {auto.length === 0 ? <NoData label="Building insights as data grows…" /> : (
          <div className="space-y-2">
            {auto.slice(0, 3).map((i, k) => (
              <motion.div key={k} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                transition={{ delay: k * 0.05 }}
                className={"rounded-lg px-3 py-2 text-sm " +
                  (i.tone === "warn" ? "bg-amber-500/10 text-amber-300" : "bg-emerald-500/10 text-emerald-300")}>
                {i.text}
              </motion.div>
            ))}
          </div>
        )}
        {correlations[0] && (
          <div className="mt-3 rounded-lg bg-neutral-950/40 p-3 text-sm text-neutral-300">
            <div className="mb-0.5 text-[11px] uppercase tracking-wide text-neutral-500">Discovery</div>
            {correlations[0].text} <span className="text-neutral-500">({correlations[0].detail})</span>
          </div>
        )}
      </Card>

      <Card>
        <SectionTitle>This week vs last</SectionTitle>
        <div className="space-y-1.5">
          {RECAP_ROWS.map(([f, label]) => {
            const w = weekly?.[f];
            return (
              <div key={f} className="flex items-center justify-between text-sm">
                <span className="text-neutral-400">{label}</span>
                <span className="text-neutral-200">
                  {w?.this == null ? "—" : w.this}{" "}
                  {w?.delta != null && <span className="text-xs">({delta(w.delta)})</span>}
                </span>
              </div>
            );
          })}
          <div className="flex items-center justify-between text-sm pt-1 border-t border-line/5">
            <span className="text-neutral-400">Workouts</span>
            <span className="text-neutral-200">{weekly?.workouts?.this ?? "—"}</span>
          </div>
        </div>
        {streakItems.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {streakItems.map(([k, label]) => (
              <motion.span key={k} initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                className="rounded-full bg-line/5 px-2.5 py-1 text-xs text-neutral-300">
                🔥 {streaks[k]} {label}
              </motion.span>
            ))}
          </div>
        )}
      </Card>
    </Grid>
  );
}
