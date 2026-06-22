import React from "react";
import { motion } from "framer-motion";
import NoData from "./NoData.jsx";

// Horizontal stacked/segmented bar. segments: [{label, value, color}]
export default function ZoneBar({ segments, formatValue = (v) => v }) {
  const segs = (segments || []).filter((s) => s.value != null);
  const total = segs.reduce((s, x) => s + (x.value || 0), 0);
  if (!segs.length || !total) return <NoData />;
  return (
    <div>
      <div className="flex h-5 w-full overflow-hidden rounded-md">
        {segs.map((s, i) => (
          <motion.div
            key={i}
            initial={{ width: 0 }}
            animate={{ width: `${((s.value || 0) / total) * 100}%` }}
            transition={{ duration: 0.8, ease: "easeOut", delay: i * 0.05 }}
            style={{ background: s.color }}
            title={`${s.label}: ${formatValue(s.value)}`}
          />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-neutral-400">
        {segs.map((s, i) => (
          <span key={i} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-sm" style={{ background: s.color }} />
            {s.label} <span className="text-neutral-500">{formatValue(s.value)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
