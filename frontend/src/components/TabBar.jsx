import React, { useRef, useState } from "react";
import { motion } from "framer-motion";
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
  animate: { rotate: [-1.1, 1.1, -1.1] },
  transition: { repeat: Infinity, duration: 0.35, ease: "easeInOut" },
};

function TabChip({ tab, active, editMode, hidden, onSelect, onToggleHide, onDelete }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: tab.key, disabled: !editMode });
  const reduce = typeof window !== "undefined"
    && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const style = { transform: CSS.Transform.toString(transform), transition,
    opacity: isDragging ? 0.4 : hidden ? 0.4 : 1, zIndex: isDragging ? 20 : undefined };

  const label = (
    <span className="relative flex items-center gap-1.5">
      {tab.icon && <span>{tab.icon}</span>}{tab.label}
    </span>
  );

  return (
    <motion.div ref={setNodeRef} style={style}
      {...(editMode && !reduce ? wobble : {})}
      className="relative shrink-0">
      <button
        {...(editMode ? { ...attributes, ...listeners } : {})}
        onClick={() => (editMode ? null : onSelect(tab.key))}
        className={"relative whitespace-nowrap rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors " +
          (editMode ? "cursor-grab active:cursor-grabbing " : "") +
          (active && !editMode ? "text-neutral-50" : "text-neutral-400 hover:text-neutral-200")}>
        {active && !editMode && (
          <motion.span layoutId="tabpill" className="absolute inset-0 rounded-lg bg-line/10"
            transition={{ type: "spring", stiffness: 400, damping: 32 }} />
        )}
        {label}
      </button>
      {editMode && (
        <button
          onClick={() => (tab.custom ? onDelete(tab.key) : onToggleHide(tab.key))}
          title={tab.custom ? "Delete tab" : hidden ? "Show tab" : "Hide tab"}
          className={"absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold shadow " +
            (hidden ? "bg-emerald-600 text-white" : "bg-neutral-700 text-neutral-100 hover:bg-red-600")}>
          {hidden ? "+" : tab.custom ? "🗑" : "✕"}
        </button>
      )}
    </motion.div>
  );
}

function NewTabPopover({ onCreate, onClose }) {
  const [name, setName] = useState("");
  const [icon, setIcon] = useState(ICONS[0]);
  return (
    <div className="absolute right-0 top-9 z-30 w-64 rounded-xl border border-line/10 bg-neutral-900 p-3 shadow-xl">
      <div className="mb-2 text-xs font-medium text-neutral-300">New custom tab</div>
      <input autoFocus value={name} onChange={(e) => setName(e.target.value)}
        placeholder="Tab name" maxLength={40}
        onKeyDown={(e) => e.key === "Enter" && name.trim() && (onCreate(name.trim(), icon), onClose())}
        className="mb-2 w-full rounded-lg border border-line/10 bg-neutral-950/60 px-2.5 py-1.5 text-sm text-neutral-100 focus:border-emerald-500/50 focus:outline-none" />
      <div className="mb-3 flex flex-wrap gap-1">
        {ICONS.map((ic) => (
          <button key={ic} onClick={() => setIcon(ic)}
            className={"flex h-7 w-7 items-center justify-center rounded-md text-base " +
              (icon === ic ? "bg-emerald-600/30 ring-1 ring-emerald-500" : "hover:bg-line/10")}>
            {ic}
          </button>
        ))}
      </div>
      <div className="flex justify-end gap-2">
        <button onClick={onClose} className="rounded-md px-2.5 py-1 text-xs text-neutral-400 hover:text-neutral-200">Cancel</button>
        <button disabled={!name.trim()} onClick={() => { onCreate(name.trim(), icon); onClose(); }}
          className="rounded-md bg-emerald-600 px-2.5 py-1 text-xs font-medium text-white disabled:opacity-40">Create</button>
      </div>
    </div>
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
        <nav className="flex flex-1 gap-1 overflow-x-auto rounded-xl border border-line/5 bg-neutral-900/50 p-1"
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
              className="shrink-0 rounded-lg px-2.5 py-1.5 text-sm font-medium text-emerald-400 hover:bg-emerald-500/10">
              ＋ Tab
            </button>
          )}
        </nav>
        <button onClick={() => { setEditMode((v) => !v); setShowNew(false); }}
          title={editMode ? "Done editing" : "Edit tabs"}
          className={"shrink-0 rounded-lg px-2.5 py-1.5 text-xs font-medium " +
            (editMode ? "bg-emerald-600 text-white" : "text-neutral-500 hover:text-neutral-200")}>
          {editMode ? "Done" : "✎ Edit"}
        </button>
      </div>
      {showNew && <NewTabPopover onCreate={onAddCustomTab} onClose={() => setShowNew(false)} />}
      {editMode && (
        <p className="mt-1.5 text-center text-[11px] text-neutral-600">
          Drag to reorder · ✕ hide · ＋ new tab · open a custom tab to add widgets
        </p>
      )}
    </div>
  );
}
