import React from "react";
import Grid from "../components/ui/Grid.jsx";
import Card from "../components/ui/Card.jsx";
import AnimatedGauge from "../components/ui/AnimatedGauge.jsx";
import StatTile from "../components/ui/StatTile.jsx";
import Ring from "../components/ui/Ring.jsx";
import NoData from "../components/ui/NoData.jsx";
import { BAND, band, ACCENT } from "../theme.js";
import { round, secsToHm, titleCase } from "../format.js";
import { visible } from "../caps.js";
import InsightsSection from "../components/Insights.jsx";

export default function Overview({ today, caps, onOpen, insights }) {
  const m = today?.metrics || {};
  const rec = m.recovery_score;
  const recColor = band(rec) ? BAND[band(rec)] : "#3b82f6";
  const acts = today?.activities || [];
  const show = (cat) => visible(caps, cat);

  return (
    <div className="space-y-4">
      <Grid className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="flex items-center justify-center py-6">
          <AnimatedGauge
            value={rec}
            label="Recovery"
            color={recColor}
            nullText="Building baseline"
            sublabel="Estimated · not a Garmin/Whoop score"
            onClick={() => onOpen("recovery")}
          />
        </Card>
        {show("sleep") && (
          <Card className="flex items-center justify-center py-6">
            <AnimatedGauge value={m.sleep_score} label="Sleep" color={ACCENT.sleep}
              onClick={() => onOpen("sleep")} />
          </Card>
        )}
        <Card className="flex items-center justify-center py-6">
          <AnimatedGauge
            value={m.strain_score}
            label="Strain"
            color={ACCENT.strain}
            sublabel="Estimated · custom metric"
            onClick={() => onOpen("strain")}
          />
        </Card>
      </Grid>

      <p className="text-center text-xs text-neutral-600">
        Recovery &amp; Strain are custom estimates from your Garmin data — not official Garmin or Whoop metrics.
      </p>

      <InsightsSection insights={insights} caps={caps} />

      <Grid className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {show("body_battery") && <StatTile label="Body Battery" value={m.body_battery} accent={ACCENT.body} onClick={() => onOpen("body_battery")} />}
        {show("rhr") && <StatTile label="Resting HR" value={m.rhr} unit="bpm" accent={ACCENT.rhr} onClick={() => onOpen("rhr")} />}
        {show("training_readiness") && <StatTile label="Training Readiness" value={m.training_readiness_score} accent="#22c55e" onClick={() => onOpen("training_readiness")} />}
        {show("stress") && <StatTile label="Stress" value={m.stress_avg} accent={ACCENT.stress} onClick={() => onOpen("stress")} />}
        {show("steps_floors") && <StatTile label="Steps" value={m.steps} accent="#a3e635" onClick={() => onOpen("steps")} />}
        {show("steps_floors") && (
          <StatTile label="Active kcal" value={m.active_calories} unit="kcal" accent="#fb923c"
            sub={m.calories != null ? `${round(m.calories)} total` : null} />
        )}
        {show("steps_floors") && <StatTile label="Floors" value={m.floors_ascended} digits={0} accent="#38bdf8" onClick={() => onOpen("floors")} />}
        {show("intensity_minutes") && (
          <Card className="flex items-center justify-center">
            <Ring
              value={m.intensity_weekly_total}
              goal={m.intensity_weekly_goal}
              color="#f97316"
              center={m.intensity_weekly_total != null ? round(m.intensity_weekly_total) : "—"}
              label="Intensity min / wk"
            />
          </Card>
        )}
      </Grid>

      {show("activities") && (
      <Card>
        <div className="text-neutral-300 text-sm mb-2">Recent activities</div>
        {acts.length === 0 ? (
          <NoData />
        ) : (
          <ul className="divide-y divide-white/5">
            {acts.slice(0, 5).map((a) => (
              <li key={a.activity_id} className="flex items-center justify-between py-2 text-sm">
                <span className="text-neutral-200">{titleCase(a.type || "activity")}</span>
                <span className="text-neutral-500">
                  {a.date} · {secsToHm(a.duration_s)} · {a.avg_hr ? `${round(a.avg_hr)} bpm` : "— bpm"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      )}
    </div>
  );
}
