import React, { useEffect, useState } from "react";
import Card from "./ui/Card.jsx";
import SectionTitle from "./ui/SectionTitle.jsx";
import { getJournal, postJournal } from "../api.js";
import { localToday } from "../format.js";

// Display labels for the fixed backend tag set (insights.JOURNAL_TAGS).
const TAGS = [
  ["alcohol", "🍺 Alcohol"],
  ["caffeine_late", "☕ Late caffeine"],
  ["late_meal", "🍽️ Late meal"],
  ["high_stress", "😣 High stress"],
  ["sick", "🤒 Sick"],
  ["travel", "✈️ Travel"],
  ["screens_in_bed", "📱 Screens in bed"],
  ["nap", "😴 Nap"],
];

// Daily journal (Whoop-style). Prefills from your previous entry — flip only
// what changed; saves on every change. Works for any date (past days editable
// via the day browser). Tags with a discovered effect show a ▲/▼ badge.
export default function Journal({ date, insights }) {
  const [entry, setEntry] = useState(null);
  const [note, setNote] = useState("");

  // tag -> dominant effect direction from the correlations engine.
  const effects = {};
  for (const c of insights?.correlations || []) {
    if (!c.tag || c.delta == null) continue;
    if (!(c.tag in effects) || Math.abs(c.delta) > Math.abs(effects[c.tag])) {
      effects[c.tag] = c.delta;
    }
  }

  useEffect(() => {
    if (!date) return;
    let ok = true;
    getJournal(date).then((e) => { if (ok) { setEntry(e); setNote(e.note || ""); } })
      .catch(() => {});
    return () => { ok = false; };
  }, [date]);

  if (!date || !entry) return null;

  const save = (tags, n) => {
    setEntry({ ...entry, tags, note: n, saved: true });
    postJournal(date, { tags, note: n }).catch(() => {});
  };
  const toggle = (k) => save({ ...entry.tags, [k]: !entry.tags[k] }, note);

  const isToday = date === localToday();
  return (
    <Card>
      <SectionTitle sub={entry.saved
        ? "Saved — tap to change"
        : "Prefilled from your last entry — tap what changed"}>
        {isToday ? "Journal" : `Journal — ${date}`}
      </SectionTitle>
      <div className="flex flex-wrap gap-1.5">
        {TAGS.map(([k, label]) => (
          <button key={k} onClick={() => toggle(k)}
            className={"rounded-full border px-3 py-1 text-xs transition-colors " +
              (entry.tags[k]
                ? "border-emerald-500/50 bg-emerald-500/15 text-emerald-300"
                : "border-line/10 bg-neutral-900/60 text-neutral-400 hover:text-neutral-200")}>
            {label}
            {effects[k] != null && (
              <span className={effects[k] < 0 ? "ml-1 text-red-400" : "ml-1 text-emerald-400"}>
                {effects[k] < 0 ? "▼" : "▲"}
              </span>
            )}
          </button>
        ))}
      </div>
      <input value={note} placeholder="Note (optional)…"
        onChange={(e) => setNote(e.target.value)}
        onBlur={() => save(entry.tags, note)}
        onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
        className="mt-3 w-full rounded-lg border border-line/10 bg-neutral-950/60 px-3 py-1.5 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-accent/60" />
    </Card>
  );
}
