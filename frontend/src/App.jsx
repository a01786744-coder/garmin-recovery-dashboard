import React, { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  getToday, getTrends, postSync, getAuthStatus, postLogout, getCapabilities,
  getSettings, postSettings, postSwitchAccount, getInsights, getDays, getDay,
} from "./api.js";

// Tabs whose content is a single day's metrics (so the day browser applies).
// "today" is excluded: it's the live time-aware recap, always the current day.
const DAY_TABS = new Set(["overview", "sleep", "training"]);
import { localToday, fmtDay, setDateStyle } from "./format.js";
import { applyAppearance } from "./theme.js";
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
import Coach from "./tabs/Coach.jsx";
import CustomTab from "./tabs/CustomTab.jsx";
import TabBar from "./components/TabBar.jsx";
import { DashboardProvider } from "./DashboardContext.jsx";

const TABS = [
  ["overview", "Overview"],
  ["today", "Today"],
  ["sleep", "Sleep"],
  ["training", "Strain & Training"],
  ["activities", "Activities"],
  ["trends", "Trends"],
  ["coach", "Coach"],
];

const VIEWS = { overview: Overview, today: Today, sleep: Sleep, training: Training, activities: Activities, trends: Trends, coach: Coach };

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
  const [days, setDays] = useState([]);            // all dates with data (asc)
  const [selectedDate, setSelectedDate] = useState(null);  // null = live/latest
  const [dayPayload, setDayPayload] = useState(null);      // fetched past day
  const [pinRequired, setPinRequired] = useState(false);   // 401 from a phone
  const [detailKey, setDetailKey] = useState(null);
  const [editTabs, setEditTabs] = useState(false);   // v4.2 jiggle/edit mode

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

  // The detail panel fetches its own range-selectable history.
  const openDetail = useCallback((key) => setDetailKey(key), []);

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

  // Apply appearance (theme + density + accent + recovery band cutoffs) from
  // settings once loaded (source of truth), mirroring theme to localStorage so
  // the next boot paints the right theme before settings arrive.
  useEffect(() => {
    if (!settings) return;
    applyAppearance(settings);
    if (settings.theme) {
      setTheme(settings.theme);
      localStorage.setItem("theme", settings.theme);
    }
  }, [settings?.theme, settings?.density, settings?.accent_color,
      settings?.recovery_green, settings?.recovery_amber]);

  // Chart/date display style ("Jul 4" vs "07-04") follows the setting.
  useEffect(() => { setDateStyle(settings?.date_style); }, [settings?.date_style]);

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
              className="rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-neutral-50 hover:bg-accent/90">
              Try again
            </button>
          </>
        ) : (
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-700 border-t-accent" />
        )}
      </div>
    );
  }

  const units = settings?.units || "metric";
  const hiddenTabs = settings?.hidden_tabs || [];
  const customTabs = settings?.custom_tabs || [];
  const order = settings?.tab_order || [];

  // Merge built-in tabs (capability-gated) with user custom tabs, apply the
  // saved order, then append anything not yet ordered (new tabs / newly
  // unlocked capabilities). de-dup preserving order.
  const builtin = TABS.filter(([key]) => tabVisible(caps, key))
    .map(([key, label]) => ({ key, label, custom: false }));
  const custom = customTabs.map((t) => ({ key: t.id, id: t.id, label: t.name, icon: t.icon,
    custom: true, layout: t.layout || [] }));
  const universe = [...builtin, ...custom];
  const byKey = new Map(universe.map((t) => [t.key, t]));
  const seenT = new Set();
  const allTabs = [
    ...order.map((k) => byKey.get(k)).filter(Boolean),
    ...universe.filter((t) => !order.includes(t.key)),
  ].filter((t) => !seenT.has(t.key) && seenT.add(t.key));
  const visibleTabs = allTabs.filter((t) => !hiddenTabs.includes(t.key));
  const shownTabs = visibleTabs.length ? visibleTabs : allTabs.slice(0, 1);
  const barTabs = editTabs ? allTabs : shownTabs;    // edit mode reveals hidden tabs
  const activeKey = shownTabs.some((t) => t.key === tab) ? tab : (shownTabs[0]?.key || "overview");
  const activeTab = allTabs.find((t) => t.key === activeKey);
  const Active = activeTab && !activeTab.custom ? VIEWS[activeKey] : null;

  // Tab customization handlers (all persist through settings.json).
  const reorderTabs = (keys) => saveSettings({ tab_order: keys });
  const toggleHide = (key) => saveSettings({ hidden_tabs:
    hiddenTabs.includes(key) ? hiddenTabs.filter((k) => k !== key) : [...hiddenTabs, key] });
  const addCustomTab = (name, icon) => {
    const id = "custom-" + Date.now().toString(36);
    saveSettings({ custom_tabs: [...customTabs, { id, name, icon, layout: [] }],
      tab_order: [...allTabs.map((t) => t.key), id] });
    setTab(id);
  };
  const deleteCustomTab = (id) => {
    saveSettings({ custom_tabs: customTabs.filter((t) => t.id !== id) });
    if (tab === id) setTab("overview");
  };
  const mutateCustom = (id, fn) => saveSettings({
    custom_tabs: customTabs.map((t) => (t.id === id ? { ...t, layout: fn(t.layout || []) } : t)) });
  const changeCustomLayout = (id, layout) => mutateCustom(id, () => layout);
  const addWidget = (id, item) => mutateCustom(id, (l) => [...l, item]);
  const removeWidget = (id, widgetId) => mutateCustom(id, (l) => l.filter((w) => w.i !== widgetId));
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
              {staleDay && !browsing && <span className="ml-1 text-amber-500/80">· showing {fmtDay(dataDate)} (today not synced yet)</span>}
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
          <Settings settings={settings} onChange={saveSettings} tabs={allTabs}
            onSwitchAccount={switchAccount} onClose={() => setSettingsOpen(false)} />
        )}

        <UpdateBanner enabled={settings?.check_updates !== false} />

        {showStale && (
          <div className="mb-4 flex items-center gap-3 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-200">
            <span>
              No new data since <b>{fmtDay(dataDate)}</b> ({staleDays} days) — check that your
              watch is syncing to Garmin Connect, or try a manual sync.
            </span>
            <button onClick={dismissStale} aria-label="Dismiss"
              className="ml-auto shrink-0 text-amber-300/70 hover:text-amber-100">✕</button>
          </div>
        )}

        <TabBar tabs={barTabs} hidden={hiddenTabs} activeKey={activeKey}
          editMode={editTabs} setEditMode={setEditTabs}
          onSelect={setTab} onReorder={reorderTabs} onToggleHide={toggleHide}
          onAddCustomTab={addCustomTab} onDeleteCustom={deleteCustomTab} />

        {onDayView && days.length > 1 && (
          <div className="mb-5 flex items-center justify-center gap-2 text-sm">
            <button disabled={!canPrev} onClick={() => canPrev && setSelectedDate(days[idx - 1])}
              className="rounded-md px-2.5 py-1 text-neutral-400 enabled:hover:text-neutral-100 disabled:opacity-30">
              ‹ Prev
            </button>
            <span className="min-w-[9rem] text-center text-neutral-300">
              {viewingDate ? fmtDay(viewingDate) : "—"}{!selectedDate && <span className="text-neutral-600"> · latest</span>}
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
            <span className="h-3 w-3 shrink-0 animate-spin rounded-full border-2 border-emerald-300/40 border-t-accent" />
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
          <DashboardProvider value={{
            today: viewData, metrics: viewData?.metrics, trends, caps, units,
            insights, perf: viewData?.perf, records: viewData?.records,
            activities: viewData?.activities, onOpen: openDetail,
          }}>
            <AnimatePresence mode="wait">
              <motion.div
                key={activeKey}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.22, ease: "easeOut" }}
              >
                {activeTab?.custom ? (
                  <CustomTab tab={activeTab} editMode={editTabs}
                    onChangeLayout={changeCustomLayout}
                    onAddWidget={addWidget} onRemoveWidget={removeWidget} />
                ) : (
                  <Active today={viewData} trends={trends} caps={caps} units={units} onOpen={openDetail} insights={insights} />
                )}
              </motion.div>
            </AnimatePresence>
          </DashboardProvider>
        )}

        <footer className="mt-10 text-center text-[10px] text-neutral-600">
          Unofficial Garmin Connect client — for personal insight only, not medical advice.
        </footer>
      </div>
      <DetailPanel metricKey={detailKey} today={today}
        insights={insights} onClose={() => setDetailKey(null)} />
    </div>
  );
}
