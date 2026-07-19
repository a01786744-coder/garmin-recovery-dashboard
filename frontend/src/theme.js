// Shared visual tokens. Recovery-green and the primary "accent" are themeable
// at runtime (applyAppearance, driven by settings); the semantic sleep/strain
// hues stay fixed so those metrics always read the same.

export const BAND = { green: "#22c55e", yellow: "#eab308", red: "#ef4444" };

// Band cutoffs are user-tunable (Settings → Recovery). Defaults match Whoop's.
let _bands = { green: 67, amber: 34 };
export function setBands(green, amber) {
  if (Number.isFinite(green) && Number.isFinite(amber) && green > amber) {
    _bands = { green, amber };
  }
}

export function band(score) {
  if (score == null) return null;
  if (score >= _bands.green) return "green";
  if (score >= _bands.amber) return "yellow";
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

const THEMES = new Set(["dark", "light", "midnight", "slate", "contrast"]);

function hexToRgb(hex) {
  const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || "");
  return m ? [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)] : null;
}

// Apply theme (named palette), accent color, and band cutoffs from settings.
// Called by App on settings load/change. The recovery-green accent recolors the
// gauges/rings that read BAND.green / ACCENT.recovery at render time.
export function applyAppearance(settings) {
  const s = settings || {};
  const root = document.documentElement;
  root.dataset.theme = THEMES.has(s.theme) ? s.theme : "dark";
  root.dataset.density = s.density === "compact" ? "compact" : "comfortable";

  const accent = /^#[0-9a-f]{6}$/i.test(s.accent_color || "") ? s.accent_color : "#22c55e";
  const rgb = hexToRgb(accent);
  if (rgb) root.style.setProperty("--accent-rgb", rgb.join(" "));
  root.style.setProperty("--accent", accent);
  // Recovery is the app's headline metric — tie its green to the chosen accent.
  BAND.green = accent;
  ACCENT.recovery = accent;
  ACCENT.hrv = accent;
  LOAD.aerobicHigh = accent;

  setBands(Number(s.recovery_green), Number(s.recovery_amber));
}

// Recovery-reactive background: tint the top glow with today's band color
// (green follows the accent, amber/red stay semantic). No score -> theme glow.
export function applyReactiveGlow(score) {
  const root = document.documentElement;
  const b = band(score);
  const rgb = b ? hexToRgb(BAND[b]) : null;
  if (rgb) root.style.setProperty("--glow-top", `rgba(${rgb.join(",")}, 0.15)`);
  else root.style.removeProperty("--glow-top");
}
