import React, { useState } from "react";
import Grid from "../components/ui/Grid.jsx";
import Card from "../components/ui/Card.jsx";
import AnimatedGauge from "../components/ui/AnimatedGauge.jsx";
import StatTile from "../components/ui/StatTile.jsx";
import Ring from "../components/ui/Ring.jsx";
import ZoneBar from "../components/ui/ZoneBar.jsx";
import SectionTitle from "../components/ui/SectionTitle.jsx";
import NoData from "../components/ui/NoData.jsx";
import { BAND, band, ACCENT } from "../theme.js";
import { round, secsToHm, titleCase } from "../format.js";
import { getIntraday } from "../api.js";
import { useAsync } from "../useApi.js";
import { visible } from "../caps.js";

const STAGES = [
  ["deep_sleep_s", "Deep", "#1d4ed8"],
  ["light_sleep_s", "Light", "#3b82f6"],
  ["rem_sleep_s", "REM", "#8b5cf6"],
  ["awake_sleep_s", "Awake", "#52525b"],
];

// Body Battery intraday rows are [ts, status, level] (shape varies); the level
// is the numeric element in 0..100. Returns the day's levels, or null.
function bbLevels(series) {
  if (!Array.isArray(series)) return null;
  const out = series
    .map((row) => {
      if (!Array.isArray(row)) return null;
      const nums = row.filter((v) => typeof v === "number" && v >= 0 && v <= 100);
      return nums.length ? nums[nums.length - 1] : null;
    })
    .filter((v) => v != null);
  return out.length ? out : null;
}

function Banner({ kind, text }) {
  return (
    <Card className="border-emerald-500/20 bg-emerald-500/[0.06]">
      <div className="text-[11px] uppercase tracking-wide text-emerald-400/80">
        {kind === "morning" ? "Morning report" : "Afternoon recap"}
      </div>
      <div className="mt-1 text-[15px] leading-snug text-neutral-200">
        {text || "Not enough data yet today — this fills in as your watch syncs."}
      </div>
    </Card>
  );
}

function MorningView({ m, show, onOpen }) {
  const rec = m.recovery_score;
  const recColor = band(rec) ? BAND[band(rec)] : "#3b82f6";
  const sleepTotal = (m.deep_sleep_s || 0) + (m.light_sleep_s || 0) + (m.rem_sleep_s || 0);
  return (
    <div className="space-y-4">
      <Grid className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="flex items-center justify-center py-6">
          <AnimatedGauge value={rec} label="Recovery" color={recColor}
            nullText="Building baseline" sublabel="Estimated · not a Garmin/Whoop score"
            onClick={() => onOpen("recovery")} />
        </Card>
        {show("sleep") && (
          <Card className="flex items-center justify-center py-6">
            <AnimatedGauge value={m.sleep_score} label="Sleep" color={ACCENT.sleep}
              onClick={() => onOpen("sleep")} />
          </Card>
        )}
        {show("training_readiness") && (
          <Card className="flex items-center justify-center py-6">
            <AnimatedGauge value={m.training_readiness_score} label="Training Readiness"
              color="#22c55e" onClick={() => onOpen("training_readiness")} />
          </Card>
        )}
      </Grid>

      {show("sleep") && (
        <Card>
          <SectionTitle sub="How you slept last night">Last night</SectionTitle>
          {sleepTotal > 0 ? (
            <>
              <div className="mb-3 flex items-end gap-6">
                <div>
                  <div className="text-3xl font-bold text-neutral-50">{secsToHm(sleepTotal)}</div>
                  <div className="text-xs text-neutral-500">time asleep</div>
                </div>
                {m.awake_count != null && (
                  <div>
                    <div className="text-xl font-semibold text-neutral-300">{round(m.awake_count)}</div>
                    <div className="text-xs text-neutral-500">awakenings</div>
                  </div>
                )}
              </div>
              <ZoneBar segments={STAGES.map(([k, label, color]) => ({ label, value: m[k], color }))}
                formatValue={(v) => secsToHm(v)} />
            </>
          ) : <NoData />}
        </Card>
      )}

      <Grid className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {show("hrv") && <StatTile label="Overnight HRV" value={m.hrv_last_night} unit="ms" accent={ACCENT.hrv} onClick={() => onOpen("hrv")} />}
        {show("rhr") && <StatTile label="Resting HR" value={m.rhr} unit="bpm" accent={ACCENT.rhr} onClick={() => onOpen("rhr")} />}
        {show("body_battery") && <StatTile label="Body Battery" value={m.body_battery} accent={ACCENT.body} onClick={() => onOpen("body_battery")} />}
        {show("respiration") && <StatTile label="Sleep respiration" value={m.resp_sleep} unit="br/min" accent={ACCENT.resp} />}
      </Grid>
    </div>
  );
}

function AfternoonView({ m, acts, show, onOpen, bbSeries }) {
  const levels = bbLevels(bbSeries);
  const now = m.body_battery;
  const atWake = levels ? Math.max(...levels) : null;
  const drained = atWake != null && now != null && atWake > now ? atWake - now : null;
  const todays = (acts || []).filter((a) => a.date === m.date);

  return (
    <div className="space-y-4">
      <Grid className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {show("body_battery") && (
          <Card className="flex items-center justify-center py-6">
            <AnimatedGauge value={now} max={100} label="Body Battery" color={ACCENT.body}
              sublabel={drained != null ? `down ${round(drained)} since this morning` : undefined}
              onClick={() => onOpen("body_battery")} />
          </Card>
        )}
        {show("stress") && (
          <Card className="flex items-center justify-center py-6">
            <AnimatedGauge value={m.stress_avg} max={100} label="Avg stress" color={ACCENT.stress}
              onClick={() => onOpen("stress")} />
          </Card>
        )}
        {show("intensity_minutes") && (
          <Card className="flex items-center justify-center py-6">
            <Ring value={m.intensity_weekly_total} goal={m.intensity_weekly_goal} color="#f97316"
              center={m.intensity_weekly_total != null ? round(m.intensity_weekly_total) : "—"}
              label="Intensity min / wk" />
          </Card>
        )}
      </Grid>

      <Grid className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {show("steps_floors") && <StatTile label="Steps" value={m.steps} accent="#a3e635" onClick={() => onOpen("steps")} />}
        {show("steps_floors") && <StatTile label="Active kcal" value={m.active_calories} unit="kcal" accent="#fb923c"
          sub={m.calories != null ? `${round(m.calories)} total` : null} />}
        {show("steps_floors") && <StatTile label="Floors" value={m.floors_ascended} accent="#38bdf8" onClick={() => onOpen("floors")} />}
        {show("intensity_minutes") && <StatTile label="Vigorous min" value={m.intensity_vigorous} accent="#f97316" />}
      </Grid>

      {show("activities") && (
        <Card>
          <SectionTitle>Today's workouts</SectionTitle>
          {todays.length === 0 ? (
            <NoData label="No workouts logged today" />
          ) : (
            <ul className="divide-y divide-line/5">
              {todays.map((a) => (
                <li key={a.activity_id} className="flex items-center justify-between py-2 text-sm">
                  <span className="text-neutral-200">{titleCase(a.type || "activity")}</span>
                  <span className="text-neutral-500">
                    {secsToHm(a.duration_s)} · {a.avg_hr ? `${round(a.avg_hr)} bpm` : "— bpm"}
                    {a.training_load ? ` · load ${round(a.training_load)}` : ""}
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

export default function Today({ today, caps, onOpen, insights }) {
  const m = today?.metrics || {};
  const date = m.date;
  const show = (cat) => visible(caps, cat);
  const recap = insights?.recap || {};
  const [part, setPart] = useState(() => (new Date().getHours() < 12 ? "morning" : "afternoon"));

  // Body Battery intraday (for "drained since this morning"); only needed in the
  // afternoon view but fetched once per date.
  const bb = useAsync(() => (date ? getIntraday(date, "body_battery") : null), [date]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="inline-flex rounded-lg border border-line/10 bg-neutral-900/50 p-1 text-sm">
          {[["morning", "Morning"], ["afternoon", "Afternoon"]].map(([k, label]) => (
            <button key={k} onClick={() => setPart(k)}
              className={"rounded-md px-3.5 py-1 font-medium transition-colors " +
                (part === k ? "bg-line/10 text-neutral-50" : "text-neutral-400 hover:text-neutral-200")}>
              {label}
            </button>
          ))}
        </div>
        <span className="text-[11px] text-neutral-600">{date || "—"}</span>
      </div>

      <Banner kind={part} text={part === "morning" ? recap.morning : recap.afternoon} />

      {part === "morning"
        ? <MorningView m={m} show={show} onOpen={onOpen} />
        : <AfternoonView m={m} acts={today?.activities} show={show} onOpen={onOpen} bbSeries={bb.data?.series} />}
    </div>
  );
}
