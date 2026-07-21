import React, { useState } from "react";
import { motion } from "framer-motion";
import { WIDGETS, WIDGET_CATEGORIES } from "../widgets/registry.jsx";

// A widget picker: a grid of slot-tiles, one per available widget; category
// chips + search filter it; click a tile to drop it onto the current board.
// Tiles already on the board are dimmed with a check. Styled to match the app
// (dark glass, accent) rather than a raw pixel skin.
export default function InventoryPalette({ present, onAdd, onClose }) {
  const [cat, setCat] = useState("All");
  const [q, setQ] = useState("");
  const has = new Set(present || []);
  const shown = WIDGETS.filter((w) =>
    (cat === "All" || w.category === cat) &&
    (!q || w.name.toLowerCase().includes(q.toLowerCase())));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={onClose}>
      <motion.div onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, scale: 0.96, y: 8 }} animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 300, damping: 26 }}
        className="flex max-h-[82vh] w-full max-w-2xl flex-col rounded-2xl border border-line/10 glass-card p-0 shadow-2xl">

        {/* header */}
        <div className="flex items-center gap-2.5 border-b border-line/10 px-4 py-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/15 text-accent text-lg">▦</span>
          <div>
            <div className="text-sm font-semibold text-neutral-100">Widget library</div>
            <div className="text-[11px] text-neutral-500">{shown.length} widget{shown.length === 1 ? "" : "s"} · click to place</div>
          </div>
          <button onClick={onClose} aria-label="Close"
            className="ml-auto flex h-8 w-8 items-center justify-center rounded-lg text-neutral-400 hover:bg-neutral-800/60 hover:text-neutral-100">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        </div>

        {/* filters */}
        <div className="flex flex-wrap items-center gap-1.5 px-4 py-3">
          {["All", ...WIDGET_CATEGORIES].map((c) => (
            <button key={c} onClick={() => setCat(c)}
              className={"rounded-lg px-3 py-1.5 text-xs font-medium transition-colors " +
                (cat === c
                  ? "bg-accent/15 text-neutral-50 ring-1 ring-accent/30"
                  : "text-neutral-400 hover:bg-neutral-800/60 hover:text-neutral-200")}>
              {c}
            </button>
          ))}
          <div className="relative ml-auto">
            <svg viewBox="0 0 24 24" width="14" height="14" className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-500"
              fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></svg>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…"
              className="w-36 rounded-lg border border-line/10 bg-neutral-950/60 py-1.5 pl-8 pr-2 text-xs text-neutral-100 placeholder:text-neutral-600 focus:border-accent/40 focus:outline-none" />
          </div>
        </div>

        {/* slot grid */}
        <div className="grid flex-1 grid-cols-3 gap-2 overflow-y-auto px-4 pb-3 sm:grid-cols-4">
          {shown.map((w, i) => {
            const added = has.has(w.id);
            return (
              <motion.button key={w.id} disabled={added} onClick={() => onAdd(w.id)}
                initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(i * 0.02, 0.3) }}
                whileHover={added ? undefined : { y: -3 }}
                title={added ? `${w.name} — already on this board` : `Add ${w.name}`}
                className={"group relative flex aspect-square flex-col items-center justify-center gap-2 rounded-xl border p-2 text-center transition-colors " +
                  (added
                    ? "cursor-default border-line/5 bg-neutral-950/50 opacity-45"
                    : "border-line/10 bg-neutral-800/40 hover:border-accent/40 hover:bg-accent/[0.07]")}>
                <span className={"flex h-11 w-11 items-center justify-center rounded-xl text-2xl transition-colors " +
                  (added ? "bg-neutral-800/60" : "bg-neutral-950/50 group-hover:bg-accent/15")}>
                  {w.icon}
                </span>
                <span className="line-clamp-2 text-[11px] font-medium leading-tight text-neutral-200">
                  {w.name}
                </span>
                {added
                  ? <span className="absolute right-1.5 top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500/20 text-[9px] text-emerald-300">✓</span>
                  : <span className="absolute right-1.5 top-1.5 text-neutral-600 opacity-0 transition-opacity group-hover:opacity-100">＋</span>}
              </motion.button>
            );
          })}
          {shown.length === 0 && (
            <div className="col-span-full py-10 text-center text-xs text-neutral-500">
              No widgets match “{q}”.
            </div>
          )}
        </div>

        <div className="border-t border-line/10 px-4 py-2.5 text-center text-[11px] text-neutral-500">
          Placed widgets can be dragged and resized while editing.
        </div>
      </motion.div>
    </div>
  );
}
