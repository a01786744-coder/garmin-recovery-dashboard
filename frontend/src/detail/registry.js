// Each metric: where its series lives and how to present it.
export const METRICS = {
  recovery:           { label: "Recovery", source: "daily", field: "recovery_score", band: true, custom: true, accent: "#22c55e", max: 100 },
  sleep:              { label: "Sleep", source: "daily", field: "sleep_score", accent: "#8b5cf6", max: 100 },
  strain:             { label: "Strain", source: "daily", field: "strain_score", custom: true, accent: "#f97316", max: 100 },
  body_battery:       { label: "Body Battery", source: "daily", field: "body_battery", accent: "#38bdf8", intraday: "body_battery", max: 100 },
  rhr:                { label: "Resting HR", source: "daily", field: "rhr", unit: "bpm", accent: "#f97316", intraday: "hr" },
  hrv:                { label: "HRV", source: "daily", field: "hrv_last_night", unit: "ms", accent: "#22c55e", intraday: "hrv" },
  training_readiness: { label: "Training Readiness", source: "daily", field: "training_readiness_score", accent: "#22c55e", max: 100 },
  stress:             { label: "Stress", source: "daily", field: "stress_avg", accent: "#eab308", intraday: "stress", max: 100 },
  steps:              { label: "Steps", source: "daily", field: "steps", accent: "#a3e635" },
  floors:             { label: "Floors", source: "daily", field: "floors_ascended", accent: "#38bdf8" },
  intensity:          { label: "Intensity (wk)", source: "daily", field: "intensity_weekly_total", accent: "#f97316" },
  vo2max:             { label: "VO₂max", source: "perf", field: "vo2max", accent: "#22c55e" },
  endurance:          { label: "Endurance", source: "perf", field: "endurance_score", accent: "#a78bfa" },
};

// Build a [{date, value}] series for a metric from the 90-day trends payload.
export function metricSeries(trends90, key) {
  const m = METRICS[key];
  if (!m || !trends90) return [];
  const rows = m.source === "perf" ? trends90.perf : trends90.days;
  return (rows || []).map((r) => ({ date: r.date, value: r[m.field] }));
}
