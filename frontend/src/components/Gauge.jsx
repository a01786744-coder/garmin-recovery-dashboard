import React from "react";
const COLORS = { green: "#22c55e", yellow: "#eab308", red: "#ef4444" };
export default function Gauge({ label, value, band, sublabel, nullText = "No data" }) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, value));
  const color = band ? COLORS[band] : "#3b82f6";
  const R = 52, C = 2 * Math.PI * R;
  return (
    <div className="flex flex-col items-center">
      <svg width="140" height="140" viewBox="0 0 140 140">
        <circle cx="70" cy="70" r={R} fill="none" stroke="#27272a" strokeWidth="12" />
        {value != null && (
          <circle cx="70" cy="70" r={R} fill="none" stroke={color} strokeWidth="12"
            strokeDasharray={C} strokeDashoffset={C * (1 - pct / 100)}
            strokeLinecap="round" transform="rotate(-90 70 70)" />
        )}
        <text x="70" y="70" textAnchor="middle" dy="0.35em"
          fill="#fafafa" fontSize={value == null ? "13" : "30"} fontWeight="600">
          {value == null ? nullText : value}
        </text>
      </svg>
      <div className="mt-2 text-neutral-200 font-medium">{label}</div>
      {sublabel && <div className="text-xs text-neutral-500">{sublabel}</div>}
    </div>
  );
}
