import React, { useEffect, useState, useCallback } from "react";
import { getToday, getTrends, postSync } from "./api.js";
import Gauge from "./components/Gauge.jsx";
import TrendChart from "./components/TrendChart.jsx";
import SleepStages from "./components/SleepStages.jsx";
import ActivityList from "./components/ActivityList.jsx";
import SyncHeader from "./components/SyncHeader.jsx";

function band(score) {
  if (score == null) return null;
  if (score >= 67) return "green";
  if (score >= 34) return "yellow";
  return "red";
}

export default function App() {
  const [today, setToday] = useState(null);
  const [trends, setTrends] = useState(null);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [t, tr] = await Promise.all([getToday(), getTrends(14)]);
      setToday(t); setTrends(tr);
    } catch (e) { /* keep last good UI; never crash */ }
  }, []);

  useEffect(() => { load(); const id = setInterval(load, 60000); return () => clearInterval(id); }, [load]);

  const retry = async () => {
    setSyncing(true);
    try { await postSync(); } catch (e) { /* surfaced via sync status */ }
    await load(); setSyncing(false);
  };

  const m = today?.metrics;
  const rec = m?.recovery_score;
  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 p-6 max-w-5xl mx-auto">
      <SyncHeader sync={today?.sync} onRetry={retry} syncing={syncing} />
      <div className="grid grid-cols-3 gap-4 mb-2">
        <Gauge label="Recovery" value={rec} band={band(rec)}
          sublabel="Estimated · not a Garmin/Whoop score"
          nullText="Building baseline" />
        <Gauge label="Sleep" value={m?.sleep_score} band={null} />
        <Gauge label="Strain" value={m?.strain_score} band={null}
          sublabel="Estimated · custom metric" />
      </div>
      <p className="text-center text-xs text-neutral-600 mb-6">
        Recovery &amp; Strain are custom estimates derived from your Garmin data — not official Garmin or Whoop metrics.
      </p>
      <div className="grid grid-cols-2 gap-4 mb-4">
        <TrendChart title="HRV (14-day)" data={trends?.hrv} color="#22c55e" />
        <TrendChart title="Resting HR (14-day)" data={trends?.rhr} color="#f97316" />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <SleepStages metrics={m} />
        <ActivityList activities={today?.activities} />
      </div>
    </div>
  );
}
