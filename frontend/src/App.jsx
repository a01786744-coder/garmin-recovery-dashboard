import React, { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  getToday, getTrends, postSync, getAuthStatus, postLogout, getCapabilities,
  getSettings, postSettings, postSwitchAccount, getInsights, getDays, getDay,
} from "./api.js";

// Tabs whose content is a single day's metrics (so the day browser applies).
// "today" is excluded: it's the live time-aware recap, always the current day.
const DAY_TABS = new Set(["overview", "sleep", "training"]);
import { localToday } from "./format.js";
import DetailPanel from "./detail/DetailPanel.jsx";
import { tabVisible } from "./caps.js";
import SyncHeader from "./components/SyncHeader.jsx";
import UpdateBanner from "./components/UpdateBanner.jsx";
import Login from "./Login.jsx";
import PinGate from "./PinGate.jsx";
import Settings from "./Settings.jsx";
import Overview from "./tabs/Overview.jsx";
import Today from "./tabs/Today.jsx";
import Sleep from "./tabs/Sleep.jsx";
import Training from "./tabs/Training.jsx";
import Activities from "./tabs/Activities.jsx";
import Trends from "./tabs/Trends.jsx";

const TABS = [
  ["overview", "Overview"],
  ["today", "Today"],
  ["sleep", "Sleep"],
  ["training", "Strain & Training"],
  ["activities", "Activities"],
  ["trends", "Trends"],
];

const VIEWS = { overview: Overview, today: Today, sleep: Sleep, training: Training, activities: Activities, trends: Trends };

export default function App() {
  const [today, setToday] = useState(null);
  const [trends, setTrends] = useState(null);
  const [caps, setCaps] = useState(null);
  const [settings, setSettings] = useState(null);
  const [theme, setTheme] = useState(
    () => (document.documentElement.dataset.theme === "light" ? "light" : "dark")
  );
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [tab, setTab] = useState("overview");
  const [syncing, setSyncing] = useState(false);
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(null); // null = unknown, false = show login
  const [authError, setAuthError] = useState(false);
  const [insights, setInsights] = useState(null);
  const [trends90, setTrends90] = useState(null);
  const [days, setDays] = useState([]);            // all dates with data (asc)
  const [selectedDate, setSelectedDate] = useState(null);  // null = live/latest
  const [dayPayload, setDayPayload] = useState(null);      // fetched past day
  const [pinRequired, setPinRequired] = useState(false);   // 401 from a phone
  const [detailKey, setDetailKey] = useState(null);

  const [loginNotice, setLoginNotice] = useState(null);

  // Resolve auth status, retrying while the backend is still starting up.
  const checkAuth = useCallback(async (attempt = 0) => {
    try {
      const { authenticated, needs_relogin } = await getAuthStatus();
      if (needs_relogin) {
        // The stored token is dead (repeated auth failures) — ask for a fresh
        // sign-in instead of failing silently in the background.
        setLoginNotice("Your Garmin session expired — please sign in again.");
        setAuthed(false);
      } else {
        setAuthed(authenticated);
      }
      setAuthError(false);
    } catch (e) {
      // The bundled backend can take a few seconds to cold-start; retry for
      // ~30s before giving up so a normal startup never shows the error.
      if (attempt < 30) setTimeout(() => checkAuth(attempt + 1), 1000);
      else setAuthError(true);   // stop spinning; show an actionable message
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const [t, tr, cp, ins, dy] = await Promise.all([
        getToday(), getTrends(14), getCapabilities(), getInsights(), getDays(),
      ]);
      setToday(t);
      setTrends(tr);
      setCaps(cp);
      setInsights(ins);
      // Refresh the browsable-day list every cycle: on a fresh install the
      // backfill lands AFTER login, and a once-only fetch left Prev/Next dead.
      setDays(dy.dates || []);
      // A sync may report an auth error transiently (e.g. a token refresh
      // racing a Garmin rate-limit). Do NOT loop the user back to login on that
      // alone — only show login if there is genuinely no saved token. This keeps
      // a hiccup as "sync failed · Retry" on the dashboard instead of a loop.
      if (t?.sync?.status === "error" && t.sync.message === "GarminAuthError") {
        try {
          const { authenticated, needs_relogin } = await getAuthStatus();
          if (needs_relogin) {
            setLoginNotice("Your Garmin session expired — please sign in again.");
            setAuthed(false);
          } else if (!authenticated) {
            setAuthed(false);
          }
        } catch (e) {
          /* backend unreachable — keep current view, don't bounce */
        }
      }
    } catch (e) {
      /* keep last good data; never crash */
    } finally {
      setReady(true);
    }
  }, []);

  const openDetail = useCallback(async (key) => {
    setDetailKey(key);
    if (!trends90) {
      try { setTrends90(await getTrends(90)); } catch (e) { /* panel still shows today + insights */ }
    }
  }, [trends90]);

  useEffect(() => { checkAuth(); }, [checkAuth]);

  // The API fires "pin-required" on a 401 (a phone with no/invalid PIN).
  useEffect(() => {
    const h = () => setPinRequired(true);
    window.addEventListener("pin-required", h);
    return () => window.removeEventListener("pin-required", h);
  }, []);

  useEffect(() => {
    if (authed !== true) return;
    load();
    getSettings().then(setSettings).catch(() => {});
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, [authed, load]);

  // Load a specific past day when one is selected (null = live/latest day).
  useEffect(() => {
    if (!selectedDate) { setDayPayload(null); return; }
    let alive = true;
    getDay(selectedDate).then((d) => alive && setDayPayload(d)).catch(() => {});
    return () => { alive = false; };
  }, [selectedDate]);

  // Apply the theme from settings once loaded (source of truth), mirroring it to
  // localStorage so the next boot paints the right theme before settings arrive.
  useEffect(() => {
    if (!settings?.theme) return;
    setTheme(settings.theme);
    document.documentElement.dataset.theme = settings.theme;
    localStorage.setItem("theme", settings.theme);
  }, [settings?.theme]);

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);                                   // snappy UI feedback
    document.documentElement.dataset.theme = next;
    localStorage.setItem("theme", next);
    setSettings((s) => ({ ...(s || {}), theme: next }));
    postSettings({ theme: next }).catch(() => {});    // persist to settings.json
  };

  const saveSettings = async (partial) => {
    try { setSettings(await postSettings(partial)); } catch (e) { /* ignore */ }
  };

  const switchAccount = async () => {
    try { await postSwitchAccount(); } catch (e) { /* ignore */ }
    setToday(null); setTrends(null); setCaps(null);
    setSettingsOpen(false);
    setAuthed(false);
  };

  const onLoggedIn = async () => {
    setAuthed(true);
    setReady(false);
    try { await postSync(); } catch (e) { /* surfaced via sync status */ }
    load();
  };

  const logout = async () => {
    try { await postLogout(); } catch (e) { /* ignore */ }
    setToday(null);
    setTrends(null);
    setAuthed(false);
  };

  const retry = async () => {
    setSyncing(true);
    try { await postSync(); } catch (e) { /* surfaced via sync status */ }
    await load();
    setSyncing(false);
  };

  if (pinRequired) return <PinGate />;
  if (authed === false) return <Login notice={loginNotice} onSuccess={onLoggedIn} />;
  if (authed === null) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
        {authError ? (
          <>
            <p className="max-w-xs text-sm text-neutral-400">
              Can't reach the local service. It may still be starting, or the backend stopped —
              try reopening the app.
            </p>
            <button onClick={() => { setAuthError(false); checkAuth(); }}
              className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-neutral-50 hover:bg-emerald-500">
              Try again
            </button>
          </>
        ) : (
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-700 border-t-emerald-500" />
        )}
      </div>
    );
  }

  const hiddenTabs = settings?.hidden_tabs || [];
  const units = settings?.units || "metric";
  const filtered = TABS.filter(([key]) => tabVisible(caps, key) && !hiddenTabs.includes(key));
  // Never leave the user with zero tabs.
  const shownTabs = filtered.length ? filtered : TABS.filter(([k]) => k === "overview");
  // If the active tab got hidden (capability or user toggle), fall back to the first visible tab.
  const activeKey = shownTabs.some(([k]) => k === tab) ? tab : shownTabs[0][0];
  const Active = VIEWS[activeKey];
  // When today's data hasn't synced yet we show the most recent day with data.
  const dataDate = today?.metrics?.date;
  const realToday = localToday();
  const staleDay = dataDate && dataDate !== realToday;
  // Stale-data warning: no new data for >2 days. Dismissal lasts for the rest
  // of the current day (reappears daily while the problem persists).
  const staleDays = dataDate
    ? Math.floor((new Date(realToday) - new Date(dataDate)) / 86400000) : 0;
  const showStale = dataDate && staleDays > 2
    && localStorage.getItem("staleDismissed") !== realToday;
  const dismissStale = () => {
    localStorage.setItem("staleDismissed", realToday);
    setToday((t) => ({ ...t }));   // re-render to hide the banner
  };

  // Day browser: which day's payload the day-views render. selectedDate=null
  // means the live/latest day; a set date swaps in that past day's metrics.
  const onDayView = DAY_TABS.has(activeKey);
  const liveDate = today?.metrics?.date;
  const viewingDate = selectedDate || liveDate;
  const browsing = onDayView && selectedDate && dayPayload;
  const viewData = browsing
    ? { ...today, metrics: dayPayload.metrics, activities: dayPayload.activities }
    : today;
  const idx = days.indexOf(viewingDate);
  const canPrev = idx > 0;
  const canNext = idx >= 0 && idx < days.length - 1;

  return (
    <div className="min-h-screen text-neutral-100">
      <div className="mx-auto max-w-6xl px-4 pb-16 pt-5">
        <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Recovery Dashboard</h1>
            <p className="text-[11px] text-neutral-600">
              {caps?.device_name ? `Garmin ${caps.device_name}` : "Garmin"} · local &amp; private
              {staleDay && !browsing && <span className="ml-1 text-amber-500/80">· showing {dataDate} (today not synced yet)</span>}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <SyncHeader sync={today?.sync} onRetry={retry} syncing={syncing} />
            <button onClick={toggleTheme} aria-label="Toggle light/dark theme"
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              className="text-neutral-500 hover:text-neutral-200">
              {theme === "dark" ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="4" />
                  <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
              )}
            </button>
            <button onClick={() => setSettingsOpen(true)} title="Settings"
              className="text-neutral-500 hover:text-neutral-200" aria-label="Settings">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
            </button>
            <button onClick={logout}
              className="whitespace-nowrap text-xs text-neutral-500 hover:text-neutral-300">
              Sign out
            </button>
          </div>
        </header>
        {settingsOpen && (
          <Settings settings={settings} onChange={saveSettings}
            onSwitchAccount={switchAccount} onClose={() => setSettingsOpen(false)} />
        )}

        <UpdateBanner enabled={settings?.check_updates !== false} />

        {showStale && (
          <div className="mb-4 flex items-center gap-3 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-200">
            <span>
              No new data since <b>{dataDate}</b> ({staleDays} days) — check that your
              watch is syncing to Garmin Connect, or try a manual sync.
            </span>
            <button onClick={dismissStale} aria-label="Dismiss"
              className="ml-auto shrink-0 text-amber-300/70 hover:text-amber-100">✕</button>
          </div>
        )}

        <nav className="mb-6 flex gap-1 overflow-x-auto rounded-xl border border-line/5 bg-neutral-900/50 p-1">
          {shownTabs.map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={
                "relative whitespace-nowrap rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors " +
                (activeKey === key ? "text-neutral-50" : "text-neutral-400 hover:text-neutral-200")
              }
            >
              {activeKey === key && (
                <motion.span
                  layoutId="tabpill"
                  className="absolute inset-0 rounded-lg bg-line/10"
                  transition={{ type: "spring", stiffness: 400, damping: 32 }}
                />
              )}
              <span className="relative">{label}</span>
            </button>
          ))}
        </nav>

        {onDayView && days.length > 1 && (
          <div className="mb-5 flex items-center justify-center gap-2 text-sm">
            <button disabled={!canPrev} onClick={() => canPrev && setSelectedDate(days[idx - 1])}
              className="rounded-md px-2.5 py-1 text-neutral-400 enabled:hover:text-neutral-100 disabled:opacity-30">
              ‹ Prev
            </button>
            <span className="min-w-[9rem] text-center text-neutral-300">
              {viewingDate || "—"}{!selectedDate && <span className="text-neutral-600"> · latest</span>}
            </span>
            <button disabled={!canNext} onClick={() => canNext && setSelectedDate(days[idx + 1])}
              className="rounded-md px-2.5 py-1 text-neutral-400 enabled:hover:text-neutral-100 disabled:opacity-30">
              Next ›
            </button>
            {selectedDate && (
              <button onClick={() => setSelectedDate(null)}
                className="ml-1 rounded-md bg-line/10 px-2.5 py-1 text-neutral-200 hover:text-neutral-50">
                Latest
              </button>
            )}
          </div>
        )}

        {today?.progress && !today.progress.complete && (
          <div className="mb-4 flex items-center gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-2.5 text-sm text-emerald-200">
            <span className="h-3 w-3 shrink-0 animate-spin rounded-full border-2 border-emerald-300/40 border-t-emerald-300" />
            Syncing your Garmin history… {today.progress.days_synced} of {today.progress.target_days} days.
            This can take a few minutes on first run, and resumes automatically if Garmin rate-limits.
          </div>
        )}

        {!ready ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-48 animate-pulse rounded-2xl bg-neutral-900/60" />
            ))}
          </div>
        ) : (
          <AnimatePresence mode="wait">
            <motion.div
              key={activeKey}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.22, ease: "easeOut" }}
            >
              <Active today={viewData} trends={trends} caps={caps} units={units} onOpen={openDetail} insights={insights} />
            </motion.div>
          </AnimatePresence>
        )}

        <footer className="mt-10 text-center text-[10px] text-neutral-600">
          Unofficial Garmin Connect client — for personal insight only, not medical advice.
        </footer>
      </div>
      <DetailPanel metricKey={detailKey} trends90={trends90} today={today}
        insights={insights} onClose={() => setDetailKey(null)} />
    </div>
  );
}
