import React from "react";
import { motion } from "framer-motion";
import Grid from "../components/ui/Grid.jsx";
import Card from "../components/ui/Card.jsx";
import StatTile from "../components/ui/StatTile.jsx";
import ZoneBar from "../components/ui/ZoneBar.jsx";
import MiniArea from "../components/ui/MiniArea.jsx";
import Badge from "../components/ui/Badge.jsx";
import SectionTitle from "../components/ui/SectionTitle.jsx";
import AnimatedGauge from "../components/ui/AnimatedGauge.jsx";
import NoData from "../components/ui/NoData.jsx";
import { ACCENT, LOAD } from "../theme.js";
import { phrase, round } from "../format.js";
import { getIntraday } from "../api.js";
import { useAsync, pairsToXY } from "../useApi.js";
import { visible } from "../caps.js";

const FACTORS = [
  ["tr_sleep_factor", "Sleep"],
  ["tr_recovery_factor", "Recovery time"],
  ["tr_acwr_factor", "Acute load"],
  ["tr_hrv_factor", "HRV"],
  ["tr_stress_factor", "Stress history"],
];

function FactorBar({ label, value }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 shrink-0 text-xs text-neutral-400">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-neutral-800">
        <motion.div
          className="h-full rounded-full bg-emerald-500"
          initial={{ width: 0 }}
          animate={{ width: `${value == null ? 0 : Math.min(100, value)}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </div>
      <span className="w-9 text-right text-xs text-neutral-300">{value == null ? "—" : round(value)}</span>
    </div>
  );
}

export default function Training({ today, caps }) {
  const m = today?.metrics || {};
  const date = m.date;
  const show = (cat) => visible(caps, cat);
  const stress = useAsync(() => (date ? getIntraday(date, "stress") : null), [date]);
  const stressXY = pairsToXY(stress.data?.series);

  // ACWR: ratio relative to a 0–2 gauge; optimal ~0.8–1.3.
  const acwr = m.acwr_ratio;

  return (
    <div className="space-y-4">
      <Grid className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="flex items-center justify-center py-6">
          <AnimatedGauge value={m.strain_score} label="Strain" color={ACCENT.strain}
            sublabel="Estimated · custom metric" />
        </Card>
        {show("training_load_acwr") && (
        <Card className="flex flex-col items-center justify-center py-6 gap-2">
          <AnimatedGauge value={acwr == null ? null : acwr} max={2} digits={1} label="Load ratio (ACWR)"
            color="#38bdf8" sublabel="acute ÷ chronic · optimal 0.8–1.3" />
        </Card>
        )}
        {show("training_load_acwr") && (
        <Card className="flex flex-col justify-center gap-2">
          <SectionTitle>Training status</SectionTitle>
          <div>
            <Badge color="#22c55e">{phrase(m.training_status_label)}</Badge>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
            <div><div className="text-neutral-500 text-xs">Acute load</div><div className="text-neutral-100 font-semibold">{round(m.acute_load)}</div></div>
            <div><div className="text-neutral-500 text-xs">Chronic load</div><div className="text-neutral-100 font-semibold">{round(m.chronic_load)}</div></div>
          </div>
        </Card>
        )}
      </Grid>

      <Grid className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {show("training_load_acwr") && (
        <Card>
          <SectionTitle sub="Monthly training load by intensity">Load focus</SectionTitle>
          <ZoneBar
            segments={[
              { label: "Aerobic low", value: m.load_aerobic_low, color: LOAD.aerobicLow },
              { label: "Aerobic high", value: m.load_aerobic_high, color: LOAD.aerobicHigh },
              { label: "Anaerobic", value: m.load_anaerobic, color: LOAD.anaerobic },
            ]}
            formatValue={(v) => round(v)}
          />
        </Card>
        )}
        {show("training_readiness") && (
        <Card>
          <SectionTitle sub="Garmin Training Readiness contributors">Readiness factors</SectionTitle>
          {FACTORS.every(([k]) => m[k] == null) ? (
            <NoData />
          ) : (
            <div className="space-y-2.5">
              {FACTORS.map(([k, label]) => <FactorBar key={k} label={label} value={m[k]} />)}
            </div>
          )}
        </Card>
        )}
      </Grid>

      {show("stress") && (
      <Card>
        <SectionTitle sub="0–100 throughout today">All-day stress</SectionTitle>
        <MiniArea data={stressXY} color={ACCENT.stress} height={170}
          xTickFormatter={(ms) => { const d = new Date(ms); return `${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`; }} />
      </Card>
      )}

      <Grid className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {show("intensity_minutes") && <StatTile label="Intensity (wk)" value={m.intensity_weekly_total} unit={`/ ${m.intensity_weekly_goal ?? "—"}`} accent="#f97316" />}
        {show("intensity_minutes") && <StatTile label="Moderate min" value={m.intensity_moderate} accent="#60a5fa" />}
        {show("intensity_minutes") && <StatTile label="Vigorous min" value={m.intensity_vigorous} accent="#f97316" />}
        {show("training_readiness") && <StatTile label="Readiness" value={m.training_readiness_score} accent="#22c55e" />}
      </Grid>
    </div>
  );
}
