import React, { useState } from "react";
import { motion } from "framer-motion";
import Card from "../components/ui/Card.jsx";
import ZoneBar from "../components/ui/ZoneBar.jsx";
import StatTile from "../components/ui/StatTile.jsx";
import SectionTitle from "../components/ui/SectionTitle.jsx";
import NoData from "../components/ui/NoData.jsx";
import MiniArea from "../components/ui/MiniArea.jsx";
import { ZONE } from "../theme.js";
import { secsToHm, secsToHms, speedToPace, meters, round, titleCase, fmtDay, num } from "../format.js";
import RouteMap from "../components/RouteMap.jsx";
import SportVolume from "../components/SportVolume.jsx";
import { getActivity, getActivities } from "../api.js";
import { useAsync } from "../useApi.js";
import { sportGroup, activityKind, SPORT_COLORS } from "../sports.js";

function elev(m, units) {
  if (m == null) return "—";
  return units === "imperial" ? `${round(m * 3.28084)} ft` : `${round(m)} m`;
}

function kg(grams, units) {
  if (grams == null || grams === 0) return "—";
  return units === "imperial"
    ? `${Math.round(grams * 0.00220462)} lb`
    : `${Math.round(grams / 100) / 10} kg`;
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

// Gym view: the recorded exercises with sets, reps and weight.
function ExerciseTable({ sets, units }) {
  const active = (sets || []).filter((s) => s.setType === "ACTIVE");
  if (!active.length) return <NoData label="No exercise sets recorded" />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wide text-neutral-500">
            <th className="py-1 pr-3">#</th><th className="pr-3">Exercise</th>
            <th className="pr-3">Reps</th><th className="pr-3">Weight</th>
            <th className="pr-3">Time</th>
          </tr>
        </thead>
        <tbody className="text-neutral-300">
          {active.map((s, i) => {
            const ex = (s.exercises || [])[0] || {};
            const name = titleCase((ex.name || ex.category || "exercise").toLowerCase());
            return (
              <tr key={i} className="border-t border-line/5">
                <td className="py-1.5 pr-3 text-neutral-500">{i + 1}</td>
                <td className="pr-3">{name}</td>
                <td className="pr-3">{s.repetitionCount ?? "—"}</td>
                <td className="pr-3">{kg(s.weight, units)}</td>
                <td className="pr-3">{s.duration != null ? secsToHms(s.duration) : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Zones({ zones }) {
  return (
    <ZoneBar
      segments={(zones || []).map((z) => ({
        label: `Z${z.zoneNumber}`, value: z.secsInZone, color: ZONE[(z.zoneNumber || 1) - 1],
      }))}
      formatValue={(v) => secsToHm(v)}
    />
  );
}

function Detail({ activity, units }) {
  const { data, loading } = useAsync(() => getActivity(activity.activity_id), [activity.activity_id]);
  const kind = activityKind(activity.type, data);
  const group = sportGroup(activity.type);

  return (
    <Card hover={false}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-lg font-semibold text-neutral-100">
            <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full"
              style={{ background: SPORT_COLORS[group] }} />
            {titleCase(activity.type || "Activity")}
          </div>
          <div className="text-xs text-neutral-500">{fmtDay(activity.date)}</div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <StatTile label="Duration" value={secsToHm(activity.duration_s)} />
        <StatTile label="Avg HR" value={activity.avg_hr ? round(activity.avg_hr) : null} unit="bpm" />
        <StatTile label="Training load" value={activity.training_load != null ? round(activity.training_load) : null} />
      </div>

      {kind === "generic" && (
        <div className="grid grid-cols-3 gap-3 mb-4">
          <StatTile label="Max HR" value={activity.max_hr ? round(activity.max_hr) : null} unit="bpm" />
          <StatTile label="Aerobic TE" value={activity.aerobic_te != null ? num(activity.aerobic_te, 1) : null} />
          <StatTile label="Anaerobic TE" value={activity.anaerobic_te != null ? num(activity.anaerobic_te, 1) : null} />
        </div>
      )}

      {/* Route map only for activities that actually have one */}
      {kind === "gps" && (
        <div className="mb-4">
          {loading ? (
            <div className="h-[320px] animate-pulse rounded-xl bg-neutral-950/40" />
          ) : (
            <RouteMap polyline={data?.polyline} />
          )}
        </div>
      )}

      {kind === "strength" && (
        <>
          <SectionTitle>Exercises</SectionTitle>
          <div className="mb-4">
            {loading ? <NoData label="Loading…" /> : <ExerciseTable sets={data?.exercise_sets} units={units} />}
          </div>
        </>
      )}

      <SectionTitle>HR zones</SectionTitle>
      <div className="mb-4">
        <Zones zones={data?.hr_zones} />
      </div>

      {(kind === "gps" || kind === "indoor") && (
        <>
          <SectionTitle>{kind === "indoor" ? "Splits (indoor — no GPS)" : "Splits"}</SectionTitle>
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
        </>
      )}
    </Card>
  );
}

const FILTERS = ["All", "Run", "Ride", "Gym", "Other"];

export default function Activities({ today, units }) {
  const full = useAsync(() => getActivities(200), []);
  const acts = full.data?.activities?.length ? full.data.activities : (today?.activities || []);
  const [filter, setFilter] = useState("All");
  const [sel, setSel] = useState(null);

  const present = new Set(acts.map((a) => sportGroup(a.type)));
  const filters = FILTERS.filter((f) => f === "All" || present.has(f));
  const shown = filter === "All" ? acts : acts.filter((a) => sportGroup(a.type) === filter);
  const selected = (sel && shown.some((a) => a.activity_id === sel.activity_id))
    ? sel : shown[0] || null;

  if (!acts.length) {
    return <Card><NoData label="No recent activities" /></Card>;
  }

  return (
    <div className="space-y-4">
      <SportVolume activities={acts} />

      <div className="flex gap-1 rounded-lg border border-line/10 bg-neutral-900/50 p-1 text-sm w-fit">
        {filters.map((f) => (
          <button key={f} onClick={() => setFilter(f)}
            className={"rounded-md px-3 py-1 transition-colors " +
              (filter === f ? "bg-line/10 text-neutral-50" : "text-neutral-400 hover:text-neutral-200")}>
            {f !== "All" && (
              <span className="mr-1.5 inline-block h-2 w-2 rounded-full"
                style={{ background: SPORT_COLORS[f] }} />
            )}
            {f}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4">
        <Card hover={false} className="p-2">
          <ul className="max-h-[70vh] overflow-y-auto">
            {shown.map((a) => {
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
                      <span className="text-sm text-neutral-100">
                        <span className="mr-1.5 inline-block h-2 w-2 rounded-full"
                          style={{ background: SPORT_COLORS[sportGroup(a.type)] }} />
                        {titleCase(a.type || "activity")}
                      </span>
                      <span className="text-xs text-neutral-500">{secsToHm(a.duration_s)}</span>
                    </div>
                    <div className="text-[11px] text-neutral-500">
                      {fmtDay(a.date)} · {a.avg_hr ? `${round(a.avg_hr)} bpm` : "— bpm"}
                      {a.training_load != null ? ` · load ${round(a.training_load)}` : ""}
                    </div>
                  </motion.button>
                </li>
              );
            })}
          </ul>
        </Card>
        {selected ? <Detail activity={selected} units={units} />
          : <Card><NoData label="No activities of this type yet" /></Card>}
      </div>
    </div>
  );
}
