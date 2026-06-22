const BASE = "http://127.0.0.1:5057";
async function j(path, opts) {
  const r = await fetch(BASE + path, opts);
  if (!r.ok) throw new Error("api " + r.status);
  return r.json();
}
export const getToday = () => j("/api/today");
export const getTrends = (days) => j(`/api/trends?days=${days}`);
export const getSyncStatus = () => j("/api/sync-status");
export const postSync = () => j("/api/sync", { method: "POST" });
export const getIntraday = (date, metric) =>
  j(`/api/intraday?date=${encodeURIComponent(date)}&metric=${encodeURIComponent(metric)}`);
export const getPerformance = () => j("/api/performance");
export const getActivity = (id) => j(`/api/activity/${id}`);
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
