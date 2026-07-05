import React, { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { METRICS, metricSeries } from "./registry.js";
import EvolutionChart from "./EvolutionChart.jsx";
import StatRow from "./StatRow.jsx";
import { RecoveryWhy, StrainWhy } from "./WhyScore.jsx";
import MiniArea from "../components/ui/MiniArea.jsx";
import NoData from "../components/ui/NoData.jsx";
import { getIntraday } from "../api.js";
import { useAsync, pairsToXY } from "../useApi.js";
import { gmtToLocalClock } from "../format.js";

export default function DetailPanel({ metricKey, trends90, today, insights, onClose }) {
  const m = metricKey ? METRICS[metricKey] : null;
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const date = today?.metrics?.date;
  const intraday = useAsync(
    () => (m?.intraday && date ? getIntraday(date, m.intraday) : null),
    [m?.intraday, date]
  );

  return (
    <AnimatePresence>
      {m && (
        <motion.div className="fixed inset-0 z-50 flex justify-end bg-black/60"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onClick={onClose}>
          <motion.aside
            className="h-full w-full max-w-xl overflow-y-auto border-l border-line/10 bg-neutral-950 p-5"
            initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 40, opacity: 0 }}
            transition={{ type: "spring", stiffness: 320, damping: 34 }}
            onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h2 className="text-xl font-bold text-neutral-50">{m.label}</h2>
                {m.custom && <p className="text-[11px] text-neutral-500">Estimated · custom metric (not Garmin/Whoop)</p>}
              </div>
              <button onClick={onClose} className="text-neutral-500 hover:text-neutral-200">✕</button>
            </div>

            <div className="mb-4 text-sm text-neutral-400">Up to 90-day evolution</div>
            <EvolutionChart series={metricSeries(trends90, metricKey)} color={m.accent} />

            <div className="my-5">
              <StatRow series={metricSeries(trends90, metricKey)} unit={m.unit} />
            </div>

            {metricKey === "recovery" && <RecoveryWhy explain={today?.recovery_explain} />}
            {metricKey === "strain" && <StrainWhy explain={today?.strain_explain} />}

            {m.intraday && (
              <div className="mb-5">
                <div className="mb-2 text-sm text-neutral-400">Today</div>
                {intraday.loading ? <NoData label="Loading…" height={150} />
                  : <MiniArea data={pairsToXY(intraday.data?.series)} color={m.accent} height={150}
                      xTickFormatter={(t) => (typeof t === "number" ? "" : gmtToLocalClock(t))} />}
              </div>
            )}

            {insights?.insights?.filter((i) => i.metric === metricKey).length > 0 && (
              <div className="space-y-2">
                <div className="text-sm text-neutral-400">Insights</div>
                {insights.insights.filter((i) => i.metric === metricKey).map((i, k) => (
                  <div key={k} className={"rounded-lg px-3 py-2 text-sm " +
                    (i.tone === "warn" ? "bg-amber-500/10 text-amber-300" : "bg-emerald-500/10 text-emerald-300")}>
                    {i.text}
                  </div>
                ))}
              </div>
            )}
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
