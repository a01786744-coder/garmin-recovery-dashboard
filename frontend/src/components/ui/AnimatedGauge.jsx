import React from "react";
import { motion, useReducedMotion } from "framer-motion";
import AnimatedNumber from "./AnimatedNumber.jsx";

// Circular gauge. value 0..max (null -> nullText). `color` is the arc color.
export default function AnimatedGauge({
  value,
  max = 100,
  label,
  sublabel,
  unit,
  digits = 0,
  color = "#3b82f6",
  nullText = "No data",
  size = 150,
  onClick,
}) {
  const reduce = useReducedMotion();
  const R = size / 2 - 14;
  const C = 2 * Math.PI * R;
  const pct = value == null ? 0 : Math.max(0, Math.min(1, value / max));
  const cx = size / 2;

  const Root = onClick ? "button" : "div";
  return (
    <Root type={onClick ? "button" : undefined} onClick={onClick}
      className={"flex flex-col items-center " + (onClick ? "cursor-pointer hover:opacity-90 transition-opacity" : "")}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <circle cx={cx} cy={cx} r={R} fill="none" stroke="#27272a" strokeWidth="11" />
          {value != null && (
            <motion.circle
              cx={cx}
              cy={cx}
              r={R}
              fill="none"
              stroke={color}
              strokeWidth="11"
              strokeLinecap="round"
              transform={`rotate(-90 ${cx} ${cx})`}
              strokeDasharray={C}
              initial={{ strokeDashoffset: reduce ? C * (1 - pct) : C }}
              animate={{ strokeDashoffset: C * (1 - pct) }}
              transition={{ duration: 1.1, ease: "easeOut" }}
              style={{ filter: `drop-shadow(0 0 6px ${color}66)` }}
            />
          )}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {value == null ? (
            <span className="text-[13px] text-neutral-500 px-3 text-center">{nullText}</span>
          ) : (
            <div className="flex items-baseline gap-0.5">
              <AnimatedNumber value={value} digits={digits} className="text-3xl font-bold text-neutral-50" />
              {unit && <span className="text-sm text-neutral-400">{unit}</span>}
            </div>
          )}
        </div>
      </div>
      <div className="mt-2 text-neutral-200 font-medium">{label}</div>
      {sublabel && (
        <div className="text-[11px] text-neutral-500 text-center max-w-[190px] leading-tight">
          {sublabel}
        </div>
      )}
    </Root>
  );
}
