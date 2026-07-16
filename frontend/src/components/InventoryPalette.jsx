import React, { useState } from "react";
import { WIDGETS, WIDGET_CATEGORIES } from "../widgets/registry.jsx";

// A Minecraft creative-inventory styled picker. A grid of beveled item-slots,
// one per available widget; category chips + search filter it; click a slot to
// add it to the current custom tab. Slots already on the tab are dimmed.
export default function InventoryPalette({ present, onAdd, onClose }) {
  const [cat, setCat] = useState("All");
  const [q, setQ] = useState("");
  const has = new Set(present || []);
  const shown = WIDGETS.filter((w) =>
    (cat === "All" || w.category === cat) &&
    (!q || w.name.toLowerCase().includes(q.toLowerCase())));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className="w-full max-w-2xl rounded-2xl border-2 border-[#1b1b1f] bg-[#c6c6c6] p-3 shadow-2xl dark:bg-[#2b2b30]"
        style={{ imageRendering: "pixelated" }}>
        <div className="mb-2 flex items-center justify-between">
          <div className="font-bold tracking-wide text-neutral-800 dark:text-neutral-100"
            style={{ fontFamily: "monospace" }}>Widget Inventory</div>
          <button onClick={onClose}
            className="rounded-md px-2 py-0.5 text-sm text-neutral-700 hover:bg-black/10 dark:text-neutral-300">✕</button>
        </div>

        <div className="mb-2 flex flex-wrap items-center gap-1.5">
          {["All", ...WIDGET_CATEGORIES].map((c) => (
            <button key={c} onClick={() => setCat(c)}
              className={"rounded-md px-2.5 py-1 text-xs font-medium " +
                (cat === c ? "bg-emerald-600 text-white"
                  : "bg-black/10 text-neutral-700 hover:bg-black/20 dark:bg-white/10 dark:text-neutral-200")}>
              {c}
            </button>
          ))}
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…"
            className="ml-auto w-32 rounded-md border border-black/10 bg-white/70 px-2 py-1 text-xs text-neutral-800 outline-none dark:bg-black/30 dark:text-neutral-100" />
        </div>

        {/* Inventory slot grid */}
        <div className="grid max-h-[55vh] grid-cols-4 gap-1.5 overflow-y-auto rounded-lg bg-[#8b8b8b] p-2 dark:bg-[#1c1c20] sm:grid-cols-6">
          {shown.map((w) => {
            const added = has.has(w.id);
            return (
              <button key={w.id} disabled={added} onClick={() => onAdd(w.id)}
                title={added ? `${w.name} (already added)` : `Add ${w.name}`}
                className={"group relative flex aspect-square flex-col items-center justify-center gap-1 border-2 p-1 text-center transition " +
                  "border-t-[#ffffff88] border-l-[#ffffff88] border-b-[#00000066] border-r-[#00000066] " +
                  (added ? "cursor-default bg-[#5a5a5a] opacity-50"
                    : "bg-[#8f8f8f] hover:bg-[#a6a6a6] dark:bg-[#3a3a40] dark:hover:bg-[#4a4a52]")}>
                <span className="text-xl leading-none">{w.icon}</span>
                <span className="line-clamp-2 text-[9px] font-medium leading-tight text-neutral-900 dark:text-neutral-100">
                  {w.name}
                </span>
                {added && <span className="absolute right-0.5 top-0.5 text-[9px] text-emerald-300">✓</span>}
              </button>
            );
          })}
          {shown.length === 0 && (
            <div className="col-span-full py-6 text-center text-xs text-neutral-700 dark:text-neutral-400">
              No widgets match.
            </div>
          )}
        </div>
        <p className="mt-2 text-center text-[10px] text-neutral-700 dark:text-neutral-400">
          Click a slot to drop it into your tab. Resize &amp; drag widgets once they're placed.
        </p>
      </div>
    </div>
  );
}
