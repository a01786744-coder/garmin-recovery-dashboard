import React, { useState } from "react";
import { motion } from "framer-motion";
import Card from "../components/ui/Card.jsx";
import ZoneBar from "../components/ui/ZoneBar.jsx";
import StatTile from "../components/ui/StatTile.jsx";
import SectionTitle from "../components/ui/SectionTitle.jsx";
import NoData from "../components/ui/NoData.jsx";
import MiniArea from "../components/ui/MiniArea.jsx";
import { ZONE } from "../theme.js";
import { secsToHm, secsToHms, speedToPace, meters, round, titleCase } from "../format.js";
import RouteMap from "../components/RouteMap.jsx";
import { getActivity } from "../api.js";
import { useAsync } from "../useApi.js";

function elev(m, units) {
  if (m == null) return "—";
  return units === "imperial" ? `${round(m * 3.28084)} ft` : `${round(m)} m`;
}

function SplitsTable({ splits, units }) {
  if (!splits || !splits.length) return <NoData />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wide text-neutral-500">
            <th className="py-1 pr-3">#</th><th className="pr-3">Dist</th>
            <th className="pr-3">Time</th><th className="pr-3">Pace</th>
            <th className="pr-3">Avg HR</th><th className="pr-3">Elev</th>
          </tr>
        </thead>
        <tbody className="text-neutral-300">
          {splits.map((s, i) => (
            <tr key={i} className="border-t border-line/5">
              <td className="py-1.5 pr-3 text-neutral-500">{i + 1}</td>
              <td className="pr-3">{meters(s.distance, units)}</td>
              <td className="pr-3">{secsToHms(s.duration)}</td>
              <td className="pr-3">{speedToPace(s.averageSpeed, units)}</td>
              <td className="pr-3">{s.averageHR ? round(s.averageHR) : "—"}</td>
              <td className="pr-3">{elev(s.elevationGain, units)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Detail({ activity, units }) {
  const { data, loading } = useAsync(() => getActivity(activity.activity_id), [activity.activity_id]);
  const zones = data?.hr_zones;
  return (
    <Card hover={false}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-lg font-semibold text-neutral-100">{titleCase(activity.type || "Activity")}</div>
          <div className="text-xs text-neutral-500">{activity.date}</div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <StatTile label="Duration" value={secsToHm(activity.duration_s)} />
        <StatTile label="Avg HR" value={activity.avg_hr ? round(activity.avg_hr) : null} unit="bpm" />
        <StatTile label="Training load" value={activity.training_load != null ? round(activity.training_load) : null} />
      </div>

      {/* Route map */}
      <div className="mb-4">
        {loading ? (
          <div className="h-[320px] animate-pulse rounded-xl bg-neutral-950/40" />
        ) : (
          <RouteMap polyline={data?.polyline} />
        )}
      </div>

      <SectionTitle>HR zones</SectionTitle>
      <div className="mb-4">
        <ZoneBar
          segments={(zones || []).map((z) => ({
            label: `Z${z.zoneNumber}`, value: z.secsInZone, color: ZONE[(z.zoneNumber || 1) - 1],
          }))}
          formatValue={(v) => secsToHm(v)}
        />
      </div>

      <SectionTitle>Splits</SectionTitle>
      <SplitsTable splits={data?.splits} units={units} />

      {data?.splits?.length > 1 && (
        <>
          <SectionTitle>HR by split</SectionTitle>
          <MiniArea height={140} color="#ef4444" area={false}
            data={data.splits.map((s, i) => ({ x: i + 1, y: s.averageHR ?? null }))} />
          <SectionTitle>Pace by split</SectionTitle>
          <MiniArea height={140} color="#22c55e" area={false}
            data={data.splits.map((s, i) => ({ x: i + 1, y: s.averageSpeed ? (units === "imperial" ? 1609.34 : 1000) / s.averageSpeed : null }))} />
          <p className="text-[11px] text-neutral-600">Pace shown as seconds per {units === "imperial" ? "mile" : "km"} (lower is faster).</p>
        </>
      )}
    </Card>
  );
}

export default function Activities({ today, units }) {
  const acts = today?.activities || [];
  const [sel, setSel] = useState(null);
  const selected = sel || acts[0] || null;

  if (!acts.length) {
    return <Card><NoData label="No recent activities" /></Card>;
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4">
      <Card hover={false} className="p-2">
        <ul className="max-h-[70vh] overflow-y-auto">
          {acts.map((a) => {
            const active = selected && a.activity_id === selected.activity_id;
            return (
              <li key={a.activity_id}>
                <motion.button
                  whileTap={{ scale: 0.99 }}
                  onClick={() => setSel(a)}
                  className={
                    "w-full rounded-xl px-3 py-2.5 text-left transition-colors " +
                    (active ? "bg-line/10" : "hover:bg-line/5")
                  }
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-neutral-100">{titleCase(a.type || "activity")}</span>
                    <span className="text-xs text-neutral-500">{secsToHm(a.duration_s)}</span>
                  </div>
                  <div className="text-[11px] text-neutral-500">
                    {a.date} · {a.avg_hr ? `${round(a.avg_hr)} bpm` : "— bpm"}
                    {a.training_load != null ? ` · load ${round(a.training_load)}` : ""}
                  </div>
                </motion.button>
              </li>
            );
          })}
        </ul>
      </Card>
      {selected && <Detail activity={selected} units={units} />}
    </div>
  );
}
