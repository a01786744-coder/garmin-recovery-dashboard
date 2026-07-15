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
import { minutesToHm, secsToHm, round, num, gmtToLocalClock, fmtDay } from "../format.js";
import { getIntraday } from "../api.js";
import { useAsync } from "../useApi.js";
import { visible } from "../caps.js";
import SleepDebt from "../components/SleepDebt.jsx";

const STAGES = [
  ["deep_sleep_s", "Deep", "#1d4ed8"],
  ["light_sleep_s", "Light", "#3b82f6"],
  ["rem_sleep_s", "REM", "#8b5cf6"],
  ["awake_sleep_s", "Awake", "#52525b"],
];

// Stage quality: percent of sleep per stage + Garmin's quality qualifier.
const STAGE_QUALITY = [
  ["sleep_deep_score", "sleep_deep_qual", "Deep"],
  ["sleep_rem_score", "sleep_rem_qual", "REM"],
  ["sleep_light_score", "sleep_light_qual", "Light"],
];

const QUAL_COLORS = {
  EXCELLENT: "#22c55e", GOOD: "#38bdf8", FAIR: "#eab308", POOR: "#ef4444",
};

const qualWord = (q) => (q ? q.charAt(0) + q.slice(1).toLowerCase() : null);

export default function Sleep({ today, trends, caps, onOpen, insights }) {
  const m = today?.metrics || {};
  const date = m.date;
  const show = (cat) => visible(caps, cat);
  const hrv = useAsync(() => (date ? getIntraday(date, "hrv") : null), [date]);

  const hrvSeries =
    hrv.data?.series?.map((r) => ({ x: r.readingTimeGMT, y: r.hrvValue })) || null;
  const sleepHistory = (trends?.days || []).map((d) => ({ x: d.date, y: d.sleep_score }));

  return (
    <div className="space-y-4">
      <Grid className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="flex items-center justify-center py-6">
          <AnimatedGauge value={m.sleep_score} label="Sleep Score" color={ACCENT.sleep}
            onClick={() => onOpen("sleep")} />
        </Card>
        {show("sleep_detail") && (
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
        )}
      </Grid>

      <Card onClick={() => onOpen("sleep")} className="cursor-pointer">
        <SectionTitle sub="Tap for the full 90-day view">Sleep score — history</SectionTitle>
        <MiniArea data={sleepHistory} color={ACCENT.sleep} height={170} area
          xTickFormatter={(d) => (typeof d === "string" ? fmtDay(d) : "")} />
      </Card>

      <SleepDebt debt={insights?.sleep_debt} />

      <Grid className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <SectionTitle>Stages — last night</SectionTitle>
          <ZoneBar
            segments={STAGES.map(([k, label, color]) => ({ label, value: m[k], color }))}
            formatValue={(v) => secsToHm(v)}
          />
        </Card>
        {show("sleep_detail") && (
        <Card>
          <SectionTitle sub="Share of the night per stage · Garmin quality rating">
            Stage quality
          </SectionTitle>
          {STAGE_QUALITY.every(([k]) => m[k] == null) && !m.sleep_restlessness_qual ? (
            <NoData />
          ) : (
            <>
              <div className="flex justify-around">
                {STAGE_QUALITY.map(([k, qk, label]) => (
                  <div key={k} className="flex flex-col items-center gap-0.5">
                    <Ring value={m[k]} goal={100} color={QUAL_COLORS[m[qk]] || "#3b82f6"}
                      size={72} center={m[k] != null ? `${round(m[k])}%` : "—"} label={label} />
                    {m[qk] && (
                      <span className="text-[10px] font-medium"
                        style={{ color: QUAL_COLORS[m[qk]] || "inherit" }}>
                        {qualWord(m[qk])}
                      </span>
                    )}
                  </div>
                ))}
              </div>
              {m.sleep_restlessness_qual && (
                <div className="mt-3 text-center text-xs text-neutral-400">
                  Restlessness:{" "}
                  <span className="font-medium"
                    style={{ color: QUAL_COLORS[m.sleep_restlessness_qual] || "inherit" }}>
                    {qualWord(m.sleep_restlessness_qual)}
                  </span>
                </div>
              )}
            </>
          )}
        </Card>
        )}
      </Grid>

      {show("hrv") && (
      <Card>
        <SectionTitle sub="Overnight HRV readings (ms)">Overnight HRV</SectionTitle>
        <MiniArea
          data={hrvSeries?.map((d) => ({ x: d.x, y: d.y })) || null}
          color={ACCENT.hrv}
          height={180}
          xTickFormatter={(t) => (typeof t === "string" ? gmtToLocalClock(t) : "")}
        />
      </Card>
      )}

      <Grid className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {show("hrv") && <StatTile label="Overnight HRV avg" value={m.hrv_last_night} unit="ms" accent={ACCENT.hrv} onClick={() => onOpen("hrv")} />}
        {show("respiration") && <StatTile label="Sleep respiration" value={m.resp_sleep} unit="br/min" accent={ACCENT.resp} />}
        <StatTile label="Total sleep" value={secsToHm(
          (m.deep_sleep_s || 0) + (m.light_sleep_s || 0) + (m.rem_sleep_s || 0)
        )} />
        <StatTile label="Resting HR" value={m.rhr} unit="bpm" accent={ACCENT.rhr} onClick={() => onOpen("rhr")} />
        {show("spo2") && <StatTile label="Blood oxygen (sleep)" value={m.spo2_avg_sleep} unit="%" accent="#38bdf8" sub={m.spo2_lowest != null ? `low ${round(m.spo2_lowest)}%` : undefined} />}
        {show("skin_temp") && m.skin_temp_dev_c != null &&
          <StatTile label="Skin temp" value={`${m.skin_temp_dev_c > 0 ? "+" : ""}${num(m.skin_temp_dev_c, 1)}`} unit="°C" accent="#fb7185" sub="vs baseline" />}
        {m.nap_time_s > 0 && <StatTile label="Naps" value={secsToHm(m.nap_time_s)} accent="#a78bfa" />}
      </Grid>
    </div>
  );
}
