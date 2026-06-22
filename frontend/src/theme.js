// Shared visual tokens.

export const BAND = { green: "#22c55e", yellow: "#eab308", red: "#ef4444" };

export function band(score) {
  if (score == null) return null;
  if (score >= 67) return "green";
  if (score >= 34) return "yellow";
  return "red";
}

export const ACCENT = {
  recovery: "#22c55e",
  sleep: "#8b5cf6",
  strain: "#f97316",
  hrv: "#22c55e",
  rhr: "#f97316",
  stress: "#eab308",
  body: "#38bdf8",
  resp: "#2dd4bf",
};

// HR zone colors (zone 1..5)
export const ZONE = ["#3b82f6", "#22c55e", "#eab308", "#f97316", "#ef4444"];

// Load-focus colors
export const LOAD = { aerobicLow: "#38bdf8", aerobicHigh: "#22c55e", anaerobic: "#f97316" };
