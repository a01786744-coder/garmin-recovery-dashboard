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
