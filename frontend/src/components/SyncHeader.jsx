import React from "react";
function ago(ts) {
  if (!ts) return "never";
  const d = (Date.now() - new Date(ts + "Z").getTime()) / 60000;
  if (d < 1) return "just now";
  if (d < 60) return `${Math.round(d)} min ago`;
  return `${Math.round(d / 60)} h ago`;
}
export default function SyncHeader({ sync, onRetry, syncing }) {
  const err = sync && sync.status === "error";
  return (
    <div className="flex items-center justify-between mb-6">
      <h1 className="text-xl font-semibold text-neutral-100">Recovery Dashboard</h1>
      <div className="flex items-center gap-3 text-sm">
        <span className={err ? "text-red-400" : "text-neutral-400"}>
          {err ? "Sync failed · " : ""}Last synced {ago(sync && sync.timestamp)}
        </span>
        <button onClick={onRetry} disabled={syncing}
          className="px-3 py-1 rounded bg-neutral-800 text-neutral-200 hover:bg-neutral-700 disabled:opacity-50">
          {syncing ? "Syncing…" : "Retry"}
        </button>
      </div>
    </div>
  );
}
