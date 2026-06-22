import React from "react";
import Grid from "../components/ui/Grid.jsx";
import Card from "../components/ui/Card.jsx";
import AnimatedGauge from "../components/ui/AnimatedGauge.jsx";
import StatTile from "../components/ui/StatTile.jsx";
import Ring from "../components/ui/Ring.jsx";
import ZoneBar from "../components/ui/ZoneBar.jsx";
import MiniArea from "../components/ui/MiniArea.jsx";
import SectionTitle from "../components/ui/SectionTitle.jsx";
import NoData from "../components/ui/NoData.jsx";
import { ACCENT } from "../theme.js";
import { minutesToHm, secsToHm, round, msToClock } from "../format.js";
import { getIntraday } from "../api.js";
import { useAsync } from "../useApi.js";

const STAGES = [
  ["deep_sleep_s", "Deep", "#1d4ed8"],
  ["light_sleep_s", "Light", "#3b82f6"],
  ["rem_sleep_s", "REM", "#8b5cf6"],
  ["awake_sleep_s", "Awake", "#52525b"],
];

const COMPONENTS = [
  ["sleep_deep_score", "Deep", "#1d4ed8"],
  ["sleep_rem_score", "REM", "#8b5cf6"],
  ["sleep_light_score", "Light", "#3b82f6"],
  ["sleep_restlessness_score", "Restless", "#2dd4bf"],
];

export default function Sleep({ today }) {
  const m = today?.metrics || {};
  const date = m.date;
  const hrv = useAsync(() => (date ? getIntraday(date, "hrv") : null), [date]);
  const baseLow = null; // baseline band carried in summary; readings only here

  const hrvSeries =
    hrv.data?.series?.map((r) => ({ x: r.readingTimeGMT, y: r.hrvValue })) || null;

  return (
    <div className="space-y-4">
      <Grid className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="flex items-center justify-center py-6">
          <AnimatedGauge value={m.sleep_score} label="Sleep Score" color={ACCENT.sleep} />
        </Card>
        <Card className="md:col-span-2">
          <SectionTitle>Sleep Need</SectionTitle>
          {m.sleep_need_actual == null && m.sleep_need_baseline == null ? (
            <NoData />
          ) : (
            <div className="flex items-end gap-8">
              <div>
                <div className="text-3xl font-bold text-neutral-50">{minutesToHm(m.sleep_need_actual)}</div>
                <div className="text-xs text-neutral-500">slept (actual)</div>
              </div>
              <div>
                <div className="text-xl font-semibold text-neutral-300">{minutesToHm(m.sleep_need_baseline)}</div>
                <div className="text-xs text-neutral-500">baseline need</div>
              </div>
              <div className="ml-auto text-right">
                <div className="text-xl font-semibold text-neutral-300">{round(m.awake_count)}</div>
                <div className="text-xs text-neutral-500">awakenings</div>
              </div>
            </div>
          )}
        </Card>
      </Grid>

      <Grid className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <SectionTitle>Stages — last night</SectionTitle>
          <ZoneBar
            segments={STAGES.map(([k, label, color]) => ({ label, value: m[k], color }))}
            formatValue={(v) => secsToHm(v)}
          />
        </Card>
        <Card>
          <SectionTitle>Component scores</SectionTitle>
          <div className="flex justify-around">
            {COMPONENTS.map(([k, label, color]) => (
              <Ring key={k} value={m[k]} goal={100} color={color} size={72}
                center={m[k] != null ? round(m[k]) : "—"} label={label} />
            ))}
          </div>
        </Card>
      </Grid>

      <Card>
        <SectionTitle sub="Overnight HRV readings (ms)">Overnight HRV</SectionTitle>
        <MiniArea
          data={hrvSeries?.map((d) => ({ x: d.x, y: d.y })) || null}
          color={ACCENT.hrv}
          height={180}
          xTickFormatter={(t) => (typeof t === "string" ? t.slice(11, 16) : "")}
        />
      </Card>

      <Grid className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTile label="Overnight HRV avg" value={m.hrv_last_night} unit="ms" accent={ACCENT.hrv} />
        <StatTile label="Sleep respiration" value={m.resp_sleep} unit="br/min" accent={ACCENT.resp} />
        <StatTile label="Total sleep" value={secsToHm(
          (m.deep_sleep_s || 0) + (m.light_sleep_s || 0) + (m.rem_sleep_s || 0)
        )} />
        <StatTile label="Resting HR" value={m.rhr} unit="bpm" accent={ACCENT.rhr} />
      </Grid>
    </div>
  );
}
