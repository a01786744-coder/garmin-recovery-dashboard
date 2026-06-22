import React from "react";
import Card from "./Card.jsx";
import AnimatedNumber from "./AnimatedNumber.jsx";

// Compact metric tile. `value` may be a number (animated) or a preformatted string.
export default function StatTile({ label, value, unit, digits = 0, sub, accent = "#a1a1aa", icon }) {
  const isNum = typeof value === "number";
  return (
    <Card className="flex flex-col justify-between min-h-[92px]">
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-neutral-500">
        {icon && <span style={{ color: accent }}>{icon}</span>}
        {label}
      </div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="text-2xl font-bold text-neutral-50">
          {isNum ? <AnimatedNumber value={value} digits={digits} /> : (value ?? "—")}
        </span>
        {unit && <span className="text-xs text-neutral-500">{unit}</span>}
      </div>
      {sub && <div className="mt-0.5 text-[11px] text-neutral-500">{sub}</div>}
    </Card>
  );
}
