// Garmin personal-record types: label, value kind, and trophy-room category.
// Types not listed are hidden rather than shown as a raw "record N".
import { secsToHms, round, num } from "./format.js";

export const PR_TYPES = {
  1:  { label: "1 km",                    kind: "time",  cat: "running" },
  2:  { label: "1 mile",                  kind: "time",  cat: "running" },
  3:  { label: "5 km",                    kind: "time",  cat: "running" },
  4:  { label: "10 km",                   kind: "time",  cat: "running" },
  5:  { label: "Half marathon",           kind: "time",  cat: "running" },
  6:  { label: "Marathon",                kind: "time",  cat: "running" },
  7:  { label: "Longest run",             kind: "dist",  cat: "distance" },
  8:  { label: "Longest ride",            kind: "dist",  cat: "distance" },
  9:  { label: "Total ascent (ride)",     kind: "dist",  cat: "distance" },
  12: { label: "Most steps in a day",     kind: "steps", cat: "steps" },
  13: { label: "Most steps in a week",    kind: "steps", cat: "steps" },
  14: { label: "Most steps in a month",   kind: "steps", cat: "steps" },
  15: { label: "Step-goal streak (best)", kind: "days",  cat: "streaks" },
  16: { label: "Step-goal streak (now)",  kind: "days",  cat: "streaks" },
};

export const CATEGORIES = {
  running:  { title: "Running",     icon: "🏃", color: "#f5c542" },  // gold
  distance: { title: "Endurance",   icon: "⛰️", color: "#f97316" },
  steps:    { title: "Steps",       icon: "👟", color: "#38bdf8" },
  streaks:  { title: "Consistency", icon: "🔥", color: "#a78bfa" },
};

export function prLabel(t) {
  return PR_TYPES[t]?.label || `Record ${t}`;
}

// Format a (possibly mid-animation) value for its record kind.
export function prValue(t, v) {
  const kind = PR_TYPES[t]?.kind || "raw";
  if (v == null) return "—";
  if (kind === "time") return secsToHms(v);
  if (kind === "dist") return v >= 1000 ? `${(v / 1000).toFixed(2)} km` : `${round(v)} m`;
  if (kind === "steps") return Math.round(v).toLocaleString();
  if (kind === "days") return `${round(v)} ${Math.round(v) === 1 ? "day" : "days"}`;
  return num(v, 1);
}

// Derived pace for the running distances (adds depth to the medal cards).
const DIST_M = { 1: 1000, 2: 1609.34, 3: 5000, 4: 10000, 5: 21097.5, 6: 42195 };
export function prPace(t, v) {
  const d = DIST_M[t];
  if (!d || !v) return null;
  const per = v / (d / 1000);
  const m = Math.floor(per / 60), s = Math.round(per % 60);
  return `${m}:${String(s).padStart(2, "0")}/km`;
}
