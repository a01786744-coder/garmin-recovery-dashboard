const BASE = ""; // same-origin: Flask serves both the app and the API
async function j(path, opts) {
  const pin = localStorage.getItem("accessPin") || "";
  const headers = { ...(opts && opts.headers), ...(pin ? { "X-Access-Pin": pin } : {}) };
  const r = await fetch(BASE + path, { ...opts, headers });
  if (r.status === 401) {
    window.dispatchEvent(new Event("pin-required"));
    throw new Error("pin_required");
  }
  if (!r.ok) throw new Error("api " + r.status);
  return r.json();
}
export const getToday = () => j("/api/today");
export const getDays = () => j("/api/days");
export const getDay = (date) => j(`/api/day/${date}`);
export const getTrends = (days) => j(`/api/trends?days=${days}`);
export const getSyncStatus = () => j("/api/sync-status");
export const postSync = () => j("/api/sync", { method: "POST" });
export const getIntraday = (date, metric) =>
  j(`/api/intraday?date=${encodeURIComponent(date)}&metric=${encodeURIComponent(metric)}`);
export const getPerformance = () => j("/api/performance");
export const getActivity = (id) => j(`/api/activity/${id}`);
export const getActivities = (limit = 100) => j(`/api/activities?limit=${limit}`);
export const getCapabilities = () => j("/api/capabilities");

const jsonPost = (path, body) =>
  j(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });

export const getAuthStatus = () => j("/api/auth/status");
export const postLogin = (email, password) => jsonPost("/api/auth/login", { email, password });
export const postMfa = (code) => jsonPost("/api/auth/mfa", { code });
export const postLogout = () => jsonPost("/api/auth/logout", {});
export const postSwitchAccount = () => jsonPost("/api/auth/switch-account", {});

export const getJournal = (date) => j(`/api/journal/${date}`);
export const postJournal = (date, body) => jsonPost(`/api/journal/${date}`, body);

export const getSettings = () => j("/api/settings");
export const postSettings = (partial) => jsonPost("/api/settings", partial);
export const exportUrl = (fmt) => `${BASE}/api/export/${fmt}`;
export const getInsights = () => j("/api/insights");

// v4.0 AI coach
export const getCoachStatus = () => j("/api/coach/status");
export const getCoachBrief = (force = false) => j(`/api/coach/brief${force ? "?force=1" : ""}`);
export const getCoachChat = () => j("/api/coach/chat");
export const postCoachChat = (message) => jsonPost("/api/coach/chat", { message });
export const clearCoachChat = () => j("/api/coach/chat", { method: "DELETE" });
export const getCoachWorkouts = () => j("/api/coach/workouts");
export const sendCoachWorkout = (design, date) => jsonPost("/api/coach/workout/send", { design, date });
export const deleteCoachWorkout = (id) => j(`/api/coach/workout/${id}`, { method: "DELETE" });
