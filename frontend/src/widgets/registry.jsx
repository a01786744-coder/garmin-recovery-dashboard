// The catalog of placeable dashboard widgets. Each widget is a small,
// self-contained component that reads everything it needs from the dashboard
// context — so it renders the same on its home tab or a custom tab.
//
// A widget entry: { id, name, icon, category, defaultW, defaultH, render }.
// defaultW/H are in react-grid-layout units (GRID_COLS=4 wide, row height ~=1
// card unit). Missing data renders "No data" (never fabricated).
import React from "react";
import Card from "../components/ui/Card.jsx";
import AnimatedGauge from "../components/ui/AnimatedGauge.jsx";
import StatTile from "../components/ui/StatTile.jsx";
import MiniArea from "../components/ui/MiniArea.jsx";
import SectionTitle from "../components/ui/SectionTitle.jsx";
import NoData from "../components/ui/NoData.jsx";
import { BAND, band, ACCENT } from "../theme.js";
import { round, num, fmtDay, minutesToHm } from "../format.js";
import { useDashboard } from "../DashboardContext.jsx";

import SleepDebt from "../components/SleepDebt.jsx";
import CompareChart from "../components/CompareChart.jsx";
import LongTrends from "../components/LongTrends.jsx";
import SportVolume from "../components/SportVolume.jsx";
import MonthHeatmap from "../components/MonthHeatmap.jsx";
import WeekReview from "../components/WeekReview.jsx";
import InsightsSection from "../components/Insights.jsx";
import Journal from "../components/Journal.jsx";
import CoachText, { Highlights } from "../components/CoachText.jsx";
import { getCoachBrief } from "../api.js";
import { useAsync } from "../useApi.js";

// --- small helpers reused by several widgets ---

function GaugeCard({ value, label, color, sublabel, nullText, metricKey }) {
  const { onOpen } = useDashboard();
  return (
    <Card hover={false} className="flex h-full items-center justify-center py-4">
      <AnimatedGauge value={value} label={label} color={color} sublabel={sublabel}
        nullText={nullText} onClick={metricKey ? () => onOpen?.(metricKey) : undefined} />
    </Card>
  );
}

function Tile({ label, value, unit, accent, metricKey, digits, sub }) {
  const { onOpen } = useDashboard();
  return (
    <StatTile label={label} value={value} unit={unit} accent={accent} digits={digits}
      sub={sub} onClick={metricKey ? () => onOpen?.(metricKey) : undefined} />
  );
}

function TrendCard({ title, sub, series, color, metricKey }) {
  const { onOpen } = useDashboard();
  const data = (series || []).map((d) => ({ x: d.date, y: d.value }));
  return (
    <Card hover={!!metricKey} onClick={metricKey ? () => onOpen?.(metricKey) : undefined}
      className={metricKey ? "cursor-pointer" : ""}>
      <SectionTitle sub={sub}>{title}</SectionTitle>
      <MiniArea data={data} color={color} height={150} area={false}
        xTickFormatter={(d) => (typeof d === "string" ? fmtDay(d) : "")} />
    </Card>
  );
}

// --- widget components ---

const RecoveryGauge = () => {
  const { metrics: m = {}, today } = useDashboard();
  const rec = m.recovery_score;
  const b = today?.baseline;
  const nullText = b && b.have < b.need ? `Baseline ${b.have}/${b.need} days` : "No HRV/RHR yet";
  return <GaugeCard value={rec} label="Recovery" nullText={nullText} metricKey="recovery"
    color={band(rec) ? BAND[band(rec)] : "#3b82f6"} sublabel="Estimated · not a Garmin/Whoop score" />;
};
const SleepGauge = () => {
  const { metrics: m = {} } = useDashboard();
  return <GaugeCard value={m.sleep_score} label="Sleep" color={ACCENT.sleep} metricKey="sleep" />;
};
const StrainGauge = () => {
  const { metrics: m = {} } = useDashboard();
  return <GaugeCard value={m.strain_score} label="Strain" color={ACCENT.strain}
    metricKey="strain" sublabel="Estimated · custom metric" />;
};

const BodyBatteryTile = () => { const { metrics: m = {} } = useDashboard();
  return <Tile label="Body Battery" value={m.body_battery} accent={ACCENT.body} metricKey="body_battery" />; };
const RhrTile = () => { const { metrics: m = {} } = useDashboard();
  return <Tile label="Resting HR" value={m.rhr} unit="bpm" accent={ACCENT.rhr} metricKey="rhr" />; };
const ReadinessTile = () => { const { metrics: m = {} } = useDashboard();
  return <Tile label="Training Readiness" value={m.training_readiness_score} accent="#22c55e" metricKey="training_readiness" />; };
const StressTile = () => { const { metrics: m = {} } = useDashboard();
  return <Tile label="Stress" value={m.stress_avg} accent={ACCENT.stress} metricKey="stress" />; };
const StepsTile = () => { const { metrics: m = {} } = useDashboard();
  return <Tile label="Steps" value={m.steps} accent="#a3e635" metricKey="steps" />; };
const RecoveryTimeTile = () => { const { metrics: m = {} } = useDashboard();
  return <Tile label="Recovery time" value={m.recovery_time_min != null ? minutesToHm(m.recovery_time_min) : null} accent="#f59e0b" />; };
const Spo2Tile = () => { const { metrics: m = {} } = useDashboard();
  return <Tile label="Blood oxygen" value={m.spo2_avg} unit="%" accent="#38bdf8" />; };
const Vo2Tile = () => { const { perf = {} } = useDashboard();
  return <Tile label="VO₂max" value={perf.vo2max} digits={0} accent="#22c55e" metricKey="vo2max" />; };

const HrvTrend = () => { const { trends } = useDashboard();
  return <TrendCard title="HRV trend" sub="Overnight average (ms)" color={ACCENT.hrv}
    series={trends?.hrv} metricKey="hrv" />; };
const RhrTrend = () => { const { trends } = useDashboard();
  return <TrendCard title="Resting HR trend" sub="14-day (bpm)" color={ACCENT.rhr}
    series={trends?.rhr} metricKey="rhr" />; };

const SleepDebtW = () => { const { insights } = useDashboard();
  return <SleepDebt debt={insights?.sleep_debt} />; };
const SportVolumeW = () => { const { activities } = useDashboard();
  return <SportVolume activities={activities} />; };
const WeekReviewW = () => { const { insights } = useDashboard();
  return <WeekReview insights={insights} />; };
const InsightsW = () => { const { insights, caps } = useDashboard();
  return <InsightsSection insights={insights} caps={caps} />; };
const JournalW = () => { const { metrics: m = {}, insights } = useDashboard();
  return <Journal date={m.date} insights={insights} />; };

const RunningTolerance = () => {
  const { perf = {} } = useDashboard();
  const load = perf.running_tolerance_load, ceil = perf.running_tolerance_ceiling;
  if (ceil == null) return <Card><NoData label="No running tolerance" /></Card>;
  const pct = Math.min(1, (load || 0) / ceil);
  return (
    <Card>
      <SectionTitle sub="This week's load vs your ceiling">Running tolerance</SectionTitle>
      <div className="mt-2 h-3 w-full overflow-hidden rounded-full bg-neutral-800">
        <div className="h-full rounded-full" style={{ width: `${Math.round(pct * 100)}%`,
          background: pct > 0.9 ? "#ef4444" : pct > 0.7 ? "#f59e0b" : "#22c55e" }} />
      </div>
      <div className="mt-2 flex justify-between text-xs text-neutral-400">
        <span>Load {Math.round(load).toLocaleString()}</span>
        <span>Ceiling {Math.round(ceil).toLocaleString()}</span>
      </div>
    </Card>
  );
};

const CoachBriefW = () => {
  const { data, loading } = useAsync(() => getCoachBrief(false), []);
  return (
    <Card>
      <SectionTitle sub="Your AI coach's read on today">Coach brief</SectionTitle>
      {loading ? <div className="mt-2 h-16 animate-pulse rounded bg-neutral-800" />
        : data?.error || !data?.text ? <NoData label="Enable the coach in Settings" />
        : <div className="mt-1"><Highlights items={data.highlights} /><CoachText text={data.text} /></div>}
    </Card>
  );
};

// --- the catalog ---

export const WIDGETS = [
  { id: "recovery_gauge", name: "Recovery", icon: "💚", category: "Recovery", defaultW: 2, defaultH: 4, render: () => <RecoveryGauge /> },
  { id: "sleep_gauge", name: "Sleep score", icon: "😴", category: "Sleep", defaultW: 1, defaultH: 4, render: () => <SleepGauge /> },
  { id: "strain_gauge", name: "Strain", icon: "🔥", category: "Training", defaultW: 1, defaultH: 4, render: () => <StrainGauge /> },
  { id: "body_battery_tile", name: "Body Battery", icon: "🔋", category: "Recovery", defaultW: 1, defaultH: 2, render: () => <BodyBatteryTile /> },
  { id: "rhr_tile", name: "Resting HR", icon: "❤️", category: "Recovery", defaultW: 1, defaultH: 2, render: () => <RhrTile /> },
  { id: "readiness_tile", name: "Training Readiness", icon: "⚡", category: "Training", defaultW: 1, defaultH: 2, render: () => <ReadinessTile /> },
  { id: "stress_tile", name: "Stress", icon: "😰", category: "Recovery", defaultW: 1, defaultH: 2, render: () => <StressTile /> },
  { id: "steps_tile", name: "Steps", icon: "👟", category: "Activities", defaultW: 1, defaultH: 2, render: () => <StepsTile /> },
  { id: "recovery_time_tile", name: "Recovery time", icon: "⏳", category: "Recovery", defaultW: 1, defaultH: 2, render: () => <RecoveryTimeTile /> },
  { id: "spo2_tile", name: "Blood oxygen", icon: "🩸", category: "Recovery", defaultW: 1, defaultH: 2, render: () => <Spo2Tile /> },
  { id: "vo2_tile", name: "VO₂max", icon: "🫁", category: "Training", defaultW: 1, defaultH: 2, render: () => <Vo2Tile /> },
  { id: "hrv_trend", name: "HRV trend", icon: "📈", category: "Recovery", defaultW: 2, defaultH: 3, render: () => <HrvTrend /> },
  { id: "rhr_trend", name: "Resting HR trend", icon: "📉", category: "Recovery", defaultW: 2, defaultH: 3, render: () => <RhrTrend /> },
  { id: "sleep_debt", name: "Sleep debt", icon: "🛌", category: "Sleep", defaultW: 2, defaultH: 4, render: () => <SleepDebtW /> },
  { id: "compare_chart", name: "Compare chart", icon: "📊", category: "Training", defaultW: 4, defaultH: 5, render: () => <CompareChart /> },
  { id: "long_trends", name: "Long-term trends", icon: "🗓️", category: "Training", defaultW: 4, defaultH: 5, render: () => <LongTrends /> },
  { id: "month_heatmap", name: "Month view", icon: "📅", category: "Training", defaultW: 4, defaultH: 5, render: () => <MonthHeatmap /> },
  { id: "weekly_volume", name: "Weekly volume", icon: "📆", category: "Activities", defaultW: 2, defaultH: 3, render: () => <SportVolumeW /> },
  { id: "running_tolerance", name: "Running tolerance", icon: "🏃", category: "Training", defaultW: 2, defaultH: 2, render: () => <RunningTolerance /> },
  { id: "week_review", name: "Weekly review", icon: "🔎", category: "Training", defaultW: 4, defaultH: 3, render: () => <WeekReviewW /> },
  { id: "insights", name: "Insights", icon: "💡", category: "Recovery", defaultW: 4, defaultH: 3, render: () => <InsightsW /> },
  { id: "journal", name: "Journal", icon: "📓", category: "Recovery", defaultW: 4, defaultH: 3, render: () => <JournalW /> },
  { id: "coach_brief", name: "Coach brief", icon: "🤖", category: "Coach", defaultW: 4, defaultH: 4, render: () => <CoachBriefW /> },
];

export const WIDGET_BY_ID = Object.fromEntries(WIDGETS.map((w) => [w.id, w]));
export const WIDGET_CATEGORIES = [...new Set(WIDGETS.map((w) => w.category))];
