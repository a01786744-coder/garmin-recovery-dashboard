// Formatting helpers (no fabrication: null/undefined -> "—").

export const DASH = "—";

export function secsToHms(s) {
  if (s == null) return DASH;
  s = Math.round(s);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

export function secsToHm(s) {
  if (s == null) return DASH;
  const h = Math.floor(s / 3600);
  const m = Math.round((s % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

// Garmin sleepNeed values are in minutes.
export function minutesToHm(m) {
  if (m == null) return DASH;
  const h = Math.floor(m / 60);
  const mm = Math.round(m % 60);
  return `${h}h ${mm}m`;
}

const MI = 1609.34;

// Running pace from speed (m/s). units: "metric" -> /km, "imperial" -> /mi.
export function speedToPace(mps, units = "metric") {
  if (!mps) return DASH;
  const per = units === "imperial" ? MI / mps : 1000 / mps;
  const m = Math.floor(per / 60);
  const s = Math.round(per % 60);
  return `${m}:${String(s).padStart(2, "0")} ${units === "imperial" ? "/mi" : "/km"}`;
}

export function meters(m, units = "metric") {
  if (m == null) return DASH;
  if (units === "imperial") {
    return m >= MI ? `${(m / MI).toFixed(2)} mi` : `${Math.round(m * 3.28084)} ft`;
  }
  return m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${Math.round(m)} m`;
}

export function num(v, digits = 0) {
  if (v == null) return DASH;
  return Number(v).toFixed(digits);
}

export function round(v) {
  return v == null ? DASH : Math.round(v);
}

// epoch-ms -> "HH:mm" local
export function msToClock(ms) {
  if (ms == null) return DASH;
  const d = new Date(ms);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

// Garmin "GMT" timestamp string (UTC, e.g. "2026-06-21T07:13:43.0") -> local
// "HH:mm". These carry no zone marker, so we treat them as UTC explicitly and
// let the Date render in the user's locale.
export function gmtToLocalClock(s) {
  if (!s) return DASH;
  const d = new Date(s.replace(" ", "T").replace(/\.\d+$/, "") + "Z");
  if (isNaN(d.getTime())) return DASH;
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

// Local calendar date as YYYY-MM-DD. (toISOString() is UTC and rolls over to
// "tomorrow" during the evening in timezones west of UTC.)
export function localToday() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function titleCase(s) {
  if (!s) return "";
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// Garmin feedback phrases like "PRODUCTIVE_1" / "NO_STATUS_2" -> "Productive"
export function phrase(s) {
  if (!s) return DASH;
  return titleCase(s.replace(/_\d+$/, "").replace(/_/g, " ").toLowerCase());
}
