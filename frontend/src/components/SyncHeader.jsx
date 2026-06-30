import React from "react";
import { motion } from "framer-motion";

function ago(ts) {
  if (!ts) return "never";
  // sync_log timestamps are UTC ("YYYY-MM-DD HH:MM:SS")
  const d = (Date.now() - new Date(ts.replace(" ", "T") + "Z").getTime()) / 60000;
  if (d < 1) return "just now";
  if (d < 60) return `${Math.round(d)} min ago`;
  return `${Math.round(d / 60)} h ago`;
}

export default function SyncHeader({ sync, onRetry, syncing }) {
  const status = sync && sync.status;
  const err = status === "error";
  const partial = status === "partial";
  const dot = err ? "#ef4444" : partial ? "#eab308" : "#22c55e";
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="flex items-center gap-2 text-neutral-400">
        <span className="relative flex h-2 w-2">
          {!err && (
            <span className="absolute inline-flex h-full w-full rounded-full opacity-60 animate-ping"
              style={{ background: dot }} />
          )}
          <span className="relative inline-flex h-2 w-2 rounded-full" style={{ background: dot }} />
        </span>
        {err ? "Sync failed · " : partial ? "Partial · " : ""}
        Synced {ago(sync && sync.timestamp)}
      </span>
      <motion.button
        whileTap={{ scale: 0.95 }}
        onClick={onRetry}
        disabled={syncing}
        className="rounded-lg border border-line/10 bg-neutral-800/80 px-3 py-1.5 text-neutral-200
                   hover:bg-neutral-700 disabled:opacity-50 transition-colors"
      >
        {syncing ? "Syncing…" : "Retry"}
      </motion.button>
    </div>
  );
}
