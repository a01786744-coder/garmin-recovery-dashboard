// Sport classification from Garmin activity typeKeys.

// Coarse groups for filtering + the weekly volume chart.
export const SPORT_COLORS = {
  Run: "#22c55e",
  Ride: "#38bdf8",
  Gym: "#f97316",
  Other: "#a78bfa",
};

export function sportGroup(type) {
  const t = (type || "").toLowerCase();
  if (t.includes("strength") || t.includes("fitness_equipment")) return "Gym";
  if (t.includes("run")) return "Run";
  if (t.includes("cycl") || t.includes("bik") || t.includes("ride")) return "Ride";
  return "Other";
}

// Which detail layout an activity gets:
//   gps      - outdoor cardio with a route (map + splits)
//   indoor   - cardio without GPS (treadmill, trainer): splits, no map
//   strength - gym: exercise sets table
//   generic  - everything else (team sports etc.): effort-focused view
export function activityKind(type, detail) {
  const t = (type || "").toLowerCase();
  if (t.includes("strength") || (detail?.exercise_sets || []).length > 0) return "strength";
  if (detail?.polyline) return "gps";
  const cardio = ["run", "cycl", "bik", "ride", "walk", "hik", "swim",
                  "row", "elliptical", "stair", "treadmill"];
  if (cardio.some((k) => t.includes(k))) return "indoor";
  return "generic";
}
