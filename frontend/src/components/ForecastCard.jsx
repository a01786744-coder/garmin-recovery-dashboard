import React from "react";
import { motion } from "framer-motion";
import Card from "./ui/Card.jsx";
import { BAND } from "../theme.js";

const BAND_LABEL = { green: "Recovered", yellow: "Moderate", red: "Strained" };

// Tomorrow-morning recovery forecast (Overview). Shows the projected band +
// score, a poor↔full-sleep range bar, and the drivers moving it.
export default function ForecastCard({ forecast }) {
  if (!forecast || forecast.point == null) return null;
  const { point, low, high, band, drivers = [] } = forecast;
  const color = BAND[band] || "#a1a1aa";
  // Position the point + the low/high ticks on a 0–100 track.
  const pos = (v) => `${Math.max(2, Math.min(98, v))}%`;

  return (
    <Card hover={false} tint={color}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-neutral-500">
            Tomorrow's forecast
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <motion.span
              initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className="text-4xl font-bold tracking-tight tabular-nums" style={{ color }}>
              {point}
            </motion.span>
            <span className="rounded-full px-2 py-0.5 text-xs font-semibold"
              style={{ background: `${color}22`, color }}>
              {BAND_LABEL[band] || band}
            </span>
          </div>
        </div>
        <div className="text-right text-[11px] text-neutral-500">
          projected on<br />an average night
        </div>
      </div>

      {/* poor ↔ full sleep range */}
      <div className="mt-4">
        <div className="relative h-2 rounded-full bg-neutral-800">
          <div className="absolute inset-y-0 rounded-full"
            style={{ left: pos(low), width: `${Math.max(0, high - low)}%`,
                     background: `${color}55` }} />
          <motion.div className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-neutral-950"
            style={{ background: color }}
            initial={{ left: pos(point), scale: 0 }}
            animate={{ left: pos(point), scale: 1 }}
            transition={{ type: "spring", stiffness: 300, damping: 20, delay: 0.15 }} />
        </div>
        <div className="mt-1 flex justify-between text-[11px] text-neutral-600">
          <span>poor sleep · {low}</span>
          <span>full sleep · {high}</span>
        </div>
      </div>

      {drivers.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {drivers.map((d, i) => {
            const up = d.effect > 0;
            return (
              <motion.span key={d.label}
                initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 + i * 0.06 }}
                className="flex items-center gap-1.5 rounded-lg border border-line/10 bg-neutral-950/40 px-2.5 py-1.5 text-xs"
                title={d.detail}>
                <span className={up ? "text-emerald-400" : "text-red-400"}>{up ? "▲" : "▼"}</span>
                <span className="text-neutral-300">{d.label}</span>
                <span className="font-semibold tabular-nums" style={{ color: up ? "#34d399" : "#f87171" }}>
                  {up ? "+" : ""}{d.effect}
                </span>
              </motion.span>
            );
          })}
        </div>
      )}
      <p className="mt-2.5 text-[11px] text-neutral-600">
        An estimate from today's strain, sleep debt, load, and HRV trend — tonight's
        sleep still decides where you land in the band.
      </p>
    </Card>
  );
}
