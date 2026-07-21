import React, { useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  DndContext, PointerSensor, useSensor, useSensors, closestCenter,
} from "@dnd-kit/core";
import {
  SortableContext, horizontalListSortingStrategy, useSortable, arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

const ICONS = ["▦", "🌅", "🏃", "🏁", "💪", "😴", "❤️", "🔥", "📊", "🧘", "⛰️", "🚴"];

// Gentle Apple-style wobble; disabled under reduced-motion.
const wobble = {
  animate: { rotate: [-0.9, 0.9, -0.9] },
  transition: { repeat: Infinity, duration: 0.4, ease: "easeInOut" },
};

// Small round action badge on a chip's corner (hide / show / delete).
function Badge({ kind, onClick }) {
  const styles = {
    hide: "bg-neutral-800 text-neutral-200 hover:bg-red-600 hover:text-white",
    show: "bg-accent text-white hover:bg-accent/90",
    delete: "bg-red-600/90 text-white hover:bg-red-500",
  }[kind];
  const glyph = kind === "show" ? (
    <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>
  ) : kind === "delete" ? (
    <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" /></svg>
  ) : (
    <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
  );
  return (
    <motion.button
      initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}
      transition={{ type: "spring", stiffness: 500, damping: 26 }}
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      className={"absolute -right-1.5 -top-1.5 z-10 flex h-5 w-5 items-center justify-center rounded-full shadow-lg ring-2 ring-neutral-950 transition-colors " + styles}>
      {glyph}
    </motion.button>
  );
}

function TabChip({ tab, active, editMode, hidden, onSelect, onToggleHide, onDelete }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: tab.key, disabled: !editMode });
  const reduce = typeof window !== "undefined"
    && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const style = {
    transform: CSS.Transform.toString(transform), transition,
    opacity: isDragging ? 0.5 : hidden && editMode ? 0.5 : 1,
    zIndex: isDragging ? 30 : undefined,
    scale: isDragging ? 1.06 : 1,
  };

  return (
    <motion.div ref={setNodeRef} style={style}
      {...(editMode && !reduce ? wobble : {})}
      className="relative shrink-0">
      <button
        {...(editMode ? { ...attributes, ...listeners } : {})}
        onClick={() => (editMode ? null : onSelect(tab.key))}
        className={"relative whitespace-nowrap rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors " +
          (editMode
            ? "cursor-grab bg-neutral-800/60 text-neutral-200 ring-1 ring-line/10 shadow-sm active:cursor-grabbing "
            : (active ? "text-neutral-50" : "text-neutral-400 hover:text-neutral-200"))}>
        {active && !editMode && (
          <motion.span layoutId="tabpill" className="absolute inset-0 rounded-lg bg-accent/15 ring-1 ring-accent/25"
            transition={{ type: "spring", stiffness: 400, damping: 32 }} />
        )}
        <span className="relative flex items-center gap-1.5">
          {tab.icon && <span>{tab.icon}</span>}{tab.label}
        </span>
      </button>
      <AnimatePresence>
        {editMode && (
          <Badge key={hidden ? "show" : tab.custom ? "delete" : "hide"}
            kind={hidden ? "show" : tab.custom ? "delete" : "hide"}
            onClick={() => (tab.custom ? onDelete(tab.key) : onToggleHide(tab.key))} />
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function NewTabPopover({ onCreate, onClose }) {
  const [name, setName] = useState("");
  const [icon, setIcon] = useState(ICONS[0]);
  const submit = () => { if (name.trim()) { onCreate(name.trim(), icon); onClose(); } };
  return (
    <motion.div
      initial={{ opacity: 0, y: -8, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -8, scale: 0.97 }} transition={{ duration: 0.16, ease: "easeOut" }}
      className="absolute right-0 top-11 z-40 w-72 rounded-2xl border border-line/10 glass-card p-3.5 shadow-2xl">
      <div className="mb-3 flex items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/15 text-accent">＋</span>
        <div className="text-sm font-semibold text-neutral-100">New custom tab</div>
      </div>

      {/* live preview of the chip */}
      <div className="mb-3 flex items-center justify-center rounded-xl border border-line/10 bg-neutral-950/40 py-3">
        <span className="flex items-center gap-1.5 rounded-lg bg-accent/15 px-3.5 py-1.5 text-sm font-medium text-neutral-50 ring-1 ring-accent/25">
          <span>{icon}</span>{name.trim() || "Tab name"}
        </span>
      </div>

      <input autoFocus value={name} onChange={(e) => setName(e.target.value)}
        placeholder="Tab name" maxLength={40}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        className="mb-3 w-full rounded-lg border border-line/10 bg-neutral-950/60 px-3 py-2 text-sm text-neutral-100 placeholder:text-neutral-600 focus:border-accent/50 focus:outline-none" />

      <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-neutral-500">Icon</div>
      <div className="mb-3.5 grid grid-cols-6 gap-1.5">
        {ICONS.map((ic) => (
          <button key={ic} onClick={() => setIcon(ic)}
            className={"flex h-8 items-center justify-center rounded-lg text-base transition-all " +
              (icon === ic
                ? "bg-accent/20 ring-1 ring-accent/60 scale-105"
                : "bg-neutral-950/40 hover:bg-neutral-800/60")}>
            {ic}
          </button>
        ))}
      </div>

      <div className="flex justify-end gap-2">
        <button onClick={onClose} className="rounded-lg px-3 py-1.5 text-xs font-medium text-neutral-400 hover:text-neutral-200">Cancel</button>
        <button disabled={!name.trim()} onClick={submit}
          className="rounded-lg bg-accent px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm transition-opacity hover:bg-accent/90 disabled:opacity-40">
          Create tab
        </button>
      </div>
    </motion.div>
  );
}

// The top navigation. In edit mode tabs wobble and can be dragged to reorder,
// hidden/shown, or (custom tabs) deleted; a ＋ creates a new custom tab.
export default function TabBar({ tabs, hidden, activeKey, onSelect, onReorder,
                                onToggleHide, onAddCustomTab, onDeleteCustom,
                                editMode, setEditMode }) {
  const [showNew, setShowNew] = useState(false);
  const pressTimer = useRef(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const hiddenSet = new Set(hidden);
  const keys = tabs.map((t) => t.key);

  const startPress = () => { pressTimer.current = setTimeout(() => setEditMode(true), 550); };
  const cancelPress = () => { clearTimeout(pressTimer.current); };

  const onDragEnd = ({ active, over }) => {
    if (over && active.id !== over.id) {
      onReorder(arrayMove(keys, keys.indexOf(active.id), keys.indexOf(over.id)));
    }
  };

  return (
    <div className="relative mb-6">
      <div className="flex items-center gap-2">
        <motion.nav
          animate={{
            boxShadow: editMode ? "0 0 0 1px rgb(var(--accent-rgb) / 0.35)" : "0 0 0 1px rgb(var(--line) / 0.05)",
          }}
          className={"flex flex-1 gap-1.5 overflow-x-auto rounded-xl p-1.5 transition-colors " +
            (editMode ? "bg-accent/[0.05]" : "bg-neutral-900/50")}
          onPointerDown={startPress} onPointerUp={cancelPress} onPointerLeave={cancelPress}>
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
            <SortableContext items={keys} strategy={horizontalListSortingStrategy}>
              {tabs.map((t) => (
                <TabChip key={t.key} tab={t} active={activeKey === t.key} editMode={editMode}
                  hidden={hiddenSet.has(t.key)} onSelect={onSelect}
                  onToggleHide={onToggleHide} onDelete={onDeleteCustom} />
              ))}
            </SortableContext>
          </DndContext>
          {editMode && (
            <button onClick={() => setShowNew((v) => !v)} title="New custom tab"
              className={"shrink-0 rounded-lg border border-dashed px-3 py-1.5 text-sm font-medium transition-colors " +
                (showNew ? "border-accent/70 bg-accent/10 text-accent"
                  : "border-accent/40 text-accent hover:bg-accent/10")}>
              ＋ Tab
            </button>
          )}
        </motion.nav>
        <button onClick={() => { setEditMode((v) => !v); setShowNew(false); }}
          title={editMode ? "Done editing" : "Edit tabs"}
          className={"shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors " +
            (editMode ? "bg-accent text-white shadow-sm hover:bg-accent/90"
              : "text-neutral-500 hover:bg-neutral-800/60 hover:text-neutral-200")}>
          {editMode ? "✓ Done" : "✎ Edit"}
        </button>
      </div>

      <AnimatePresence>
        {showNew && <NewTabPopover onCreate={onAddCustomTab} onClose={() => setShowNew(false)} />}
      </AnimatePresence>

      <AnimatePresence>
        {editMode && (
          <motion.div
            initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
            <div className="mt-2 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-[11px] text-neutral-500">
              <span className="flex items-center gap-1"><Kbd>drag</Kbd> reorder</span>
              <span className="text-neutral-700">·</span>
              <span className="flex items-center gap-1"><Kbd>✕</Kbd> hide a tab</span>
              <span className="text-neutral-700">·</span>
              <span className="flex items-center gap-1"><Kbd>＋ Tab</Kbd> new board</span>
              <span className="text-neutral-700">·</span>
              <span>open a board to add widgets</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Kbd({ children }) {
  return (
    <span className="rounded border border-line/10 bg-neutral-800/70 px-1.5 py-0.5 font-medium text-neutral-300">
      {children}
    </span>
  );
}
