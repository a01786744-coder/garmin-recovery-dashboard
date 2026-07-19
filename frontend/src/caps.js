// Capability-driven visibility.
//
// A category/card is shown unless the profile is "ready" (we've observed enough
// data to trust a negative) AND the category is explicitly unsupported. So a
// watch that simply has no data today still shows the card ("No data"); only a
// metric the watch never reports gets hidden.

export function visible(caps, cat) {
  if (!caps || !caps.ready) return true;
  return caps.supported?.[cat] !== false;
}

// Which categories keep each tab alive. A tab hides only when ALL its
// categories are unsupported. Overview is the core landing tab — never hidden.
const TAB_CATS = {
  overview: null,
  today: null,
  sleep: ["sleep", "sleep_detail", "respiration", "hrv"],
  training: ["training_readiness", "training_load_acwr", "intensity_minutes", "stress"],
  activities: ["activities"],
  trends: ["hrv", "rhr", "vo2max", "race_predictions", "endurance", "personal_records"],
  records: ["personal_records"],
};

export function tabVisible(caps, tab) {
  const cats = TAB_CATS[tab];
  if (!cats) return true;
  if (!caps || !caps.ready) return true;
  return cats.some((c) => visible(caps, c));
}
