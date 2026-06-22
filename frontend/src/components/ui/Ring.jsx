import React from "react";
import { motion, useReducedMotion } from "framer-motion";

// Small progress ring for goals (e.g. intensity minutes vs goal).
export default function Ring({ value, goal, color = "#22c55e", size = 84, label, center }) {
  const reduce = useReducedMotion();
  const R = size / 2 - 7;
  const C = 2 * Math.PI * R;
  const pct = goal ? Math.max(0, Math.min(1, (value || 0) / goal)) : 0;
  const cx = size / 2;
  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <circle cx={cx} cy={cx} r={R} fill="none" stroke="#27272a" strokeWidth="7" />
          <motion.circle
            cx={cx}
            cy={cx}
            r={R}
            fill="none"
            stroke={color}
            strokeWidth="7"
            strokeLinecap="round"
            transform={`rotate(-90 ${cx} ${cx})`}
            strokeDasharray={C}
            initial={{ strokeDashoffset: reduce ? C * (1 - pct) : C }}
            animate={{ strokeDashoffset: C * (1 - pct) }}
            transition={{ duration: 1, ease: "easeOut" }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center text-sm font-semibold text-neutral-100">
          {center}
        </div>
      </div>
      {label && <div className="mt-1 text-[11px] text-neutral-500">{label}</div>}
    </div>
  );
}
