import React from "react";
const fmt = (s) => (s == null ? "—" : `${Math.floor(s / 60)}m`);
export default function ActivityList({ activities }) {
  return (
    <div className="bg-neutral-900 rounded-xl p-4">
      <div className="text-neutral-300 text-sm mb-2">Recent activities</div>
      {!activities || activities.length === 0 ? (
        <div className="text-neutral-600 text-sm">No data</div>
      ) : (
        <ul className="divide-y divide-neutral-800">
          {activities.map((a) => (
            <li key={a.activity_id} className="py-2 flex justify-between text-sm">
              <span className="text-neutral-200 capitalize">{(a.type || "activity").replace(/_/g, " ")}</span>
              <span className="text-neutral-400">{fmt(a.duration_s)} · {a.avg_hr ? `${Math.round(a.avg_hr)} bpm` : "— bpm"}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
