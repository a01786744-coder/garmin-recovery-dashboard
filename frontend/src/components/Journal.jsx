import React, { useEffect, useState } from "react";
import Card from "./ui/Card.jsx";
import SectionTitle from "./ui/SectionTitle.jsx";
import { getJournal, postJournal } from "../api.js";

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
// what changed; saves on every change. Tag effects show up under Insights
// once enough tagged/untagged days accumulate.
export default function Journal({ date }) {
  const [entry, setEntry] = useState(null);
  const [note, setNote] = useState("");

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

  return (
    <Card>
      <SectionTitle sub={entry.saved
        ? "Saved — tap to change"
        : "Prefilled from your last entry — tap what changed"}>
        Journal
      </SectionTitle>
      <div className="flex flex-wrap gap-1.5">
        {TAGS.map(([k, label]) => (
          <button key={k} onClick={() => toggle(k)}
            className={"rounded-full border px-3 py-1 text-xs transition-colors " +
              (entry.tags[k]
                ? "border-emerald-500/50 bg-emerald-500/15 text-emerald-300"
                : "border-line/10 bg-neutral-900/60 text-neutral-400 hover:text-neutral-200")}>
            {label}
          </button>
        ))}
      </div>
      <input value={note} placeholder="Note (optional)…"
        onChange={(e) => setNote(e.target.value)}
        onBlur={() => save(entry.tags, note)}
        onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
        className="mt-3 w-full rounded-lg border border-line/10 bg-neutral-950/60 px-3 py-1.5 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-emerald-500/60" />
    </Card>
  );
}
