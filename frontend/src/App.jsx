import React, { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { getToday, getTrends, postSync } from "./api.js";
import SyncHeader from "./components/SyncHeader.jsx";
import Overview from "./tabs/Overview.jsx";
import Sleep from "./tabs/Sleep.jsx";
import Training from "./tabs/Training.jsx";
import Activities from "./tabs/Activities.jsx";
import Trends from "./tabs/Trends.jsx";

const TABS = [
  ["overview", "Overview"],
  ["sleep", "Sleep"],
  ["training", "Strain & Training"],
  ["activities", "Activities"],
  ["trends", "Trends"],
];

const VIEWS = { overview: Overview, sleep: Sleep, training: Training, activities: Activities, trends: Trends };

export default function App() {
  const [today, setToday] = useState(null);
  const [trends, setTrends] = useState(null);
  const [tab, setTab] = useState("overview");
  const [syncing, setSyncing] = useState(false);
  const [ready, setReady] = useState(false);

  const load = useCallback(async () => {
    try {
      const [t, tr] = await Promise.all([getToday(), getTrends(14)]);
      setToday(t);
      setTrends(tr);
    } catch (e) {
      /* keep last good data; never crash */
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, [load]);

  const retry = async () => {
    setSyncing(true);
    try {
      await postSync();
    } catch (e) {
      /* surfaced via sync status */
    }
    await load();
    setSyncing(false);
  };

  const Active = VIEWS[tab];

  return (
    <div className="min-h-screen text-neutral-100">
      <div className="mx-auto max-w-6xl px-4 pb-16 pt-5">
        <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Recovery Dashboard</h1>
            <p className="text-[11px] text-neutral-600">Garmin Forerunner 970 · local &amp; private</p>
          </div>
          <SyncHeader sync={today?.sync} onRetry={retry} syncing={syncing} />
        </header>

        <nav className="mb-6 flex gap-1 overflow-x-auto rounded-xl border border-white/5 bg-neutral-900/50 p-1">
          {TABS.map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={
                "relative whitespace-nowrap rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors " +
                (tab === key ? "text-neutral-50" : "text-neutral-400 hover:text-neutral-200")
              }
            >
              {tab === key && (
                <motion.span
                  layoutId="tabpill"
                  className="absolute inset-0 rounded-lg bg-white/10"
                  transition={{ type: "spring", stiffness: 400, damping: 32 }}
                />
              )}
              <span className="relative">{label}</span>
            </button>
          ))}
        </nav>

        {!ready ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-48 animate-pulse rounded-2xl bg-neutral-900/60" />
            ))}
          </div>
        ) : (
          <AnimatePresence mode="wait">
            <motion.div
              key={tab}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.22, ease: "easeOut" }}
            >
              <Active today={today} trends={trends} />
            </motion.div>
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
