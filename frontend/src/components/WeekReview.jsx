import React from "react";
import Card from "./ui/Card.jsx";
import SectionTitle from "./ui/SectionTitle.jsx";
import { round, DASH, fmtDay } from "../format.js";

const ROWS = [
  ["recovery_score", "Recovery", true],
  ["sleep_score", "Sleep", true],
  ["hrv_last_night", "HRV", true],
  ["strain_score", "Strain", false],   // strain: neither direction is "good"
];

function Delta({ d, goodUp }) {
  if (d == null) return <span className="text-neutral-600">{DASH}</span>;
  const up = d > 0;
  const color = goodUp == null || d === 0 ? "text-neutral-400"
    : (up === goodUp ? "text-emerald-400" : "text-red-400");
  return <span className={color}>{up ? "▲" : "▼"} {Math.abs(d)}</span>;
}

// Monday-morning "week in review": last week vs the week before, best/worst
// day, and how many journal patterns the correlations engine has found.
// (window.__forceWeekReview lets it render for testing/screenshots.)
export default function WeekReview({ insights }) {
  const monday = new Date().getDay() === 1 || window.__forceWeekReview === true;
  const w = insights?.weekly;
  if (!monday || !w) return null;
  const ex = insights?.week_extremes;
  const found = (insights?.correlations || []).length;

  return (
    <Card className="border-sky-500/20 bg-sky-500/[0.06]">
      <SectionTitle sub="Last 7 days vs the 7 before">Your week in review</SectionTitle>
      <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm sm:grid-cols-4">
        {ROWS.map(([k, label, goodUp]) => (
          <div key={k} className="flex items-baseline justify-between gap-2">
            <span className="text-neutral-400">{label}</span>
            <span className="text-neutral-100">
              {w[k]?.this != null ? round(w[k].this) : DASH}{" "}
              <Delta d={w[k]?.delta} goodUp={goodUp ? true : null} />
            </span>
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-neutral-400">
        {ex?.best && <span>Best day: <b className="text-emerald-400">{fmtDay(ex.best.date)}</b> (recovery {ex.best.recovery})</span>}
        {ex?.worst && <span>Toughest: <b className="text-red-400">{fmtDay(ex.worst.date)}</b> (recovery {ex.worst.recovery})</span>}
        <span>{found > 0 ? `${found} pattern${found > 1 ? "s" : ""} found in your journal & data` : "No journal patterns yet — keep tagging days"}</span>
      </div>
    </Card>
  );
}
