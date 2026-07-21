import React, { useState } from "react";
import { Responsive, WidthProvider } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import Card from "../components/ui/Card.jsx";
import NoData from "../components/ui/NoData.jsx";
import InventoryPalette from "../components/InventoryPalette.jsx";
import { WIDGET_BY_ID } from "../widgets/registry.jsx";

const RGL = WidthProvider(Responsive);
const GRID = 4;
const COLS = { lg: GRID, md: GRID, sm: 2, xs: 1, xxs: 1 };
const BREAKPOINTS = { lg: 900, md: 700, sm: 500, xs: 360, xxs: 0 };

function nextSlot(layout, w) {
  // Flow new widgets left-to-right, wrapping to a new row when the current one
  // is full — so a fresh tab fills the width instead of stacking one column.
  if (!layout.length) return { x: 0, y: 0 };
  const maxY = Math.max(...layout.map((i) => i.y));
  const row = layout.filter((i) => i.y === maxY);
  const usedX = row.reduce((s, i) => s + i.w, 0);
  if (usedX + w <= GRID) return { x: usedX, y: maxY };
  const rowH = Math.max(...row.map((i) => i.h));
  return { x: 0, y: maxY + rowH };
}

// A user-composed tab: a resizable/draggable grid of widgets. Edit mode
// (shared with the tab bar's jiggle mode) enables drag+resize and reveals the
// remove buttons and the "Add widget" inventory.
export default function CustomTab({ tab, editMode, onChangeLayout, onAddWidget, onRemoveWidget }) {
  const [showPalette, setShowPalette] = useState(false);
  const layout = (tab.layout || []).filter((w) => WIDGET_BY_ID[w.i]);

  // Persist only when a drag/resize finishes (not on every intermediate tick),
  // so we make one settings write per gesture instead of dozens.
  const persist = (current) => {
    if (current) onChangeLayout(tab.id, current.map(({ i, x, y, w, h }) => ({ i, x, y, w, h })));
  };

  return (
    <div>
      {editMode && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <button onClick={() => setShowPalette(true)}
            className="flex items-center gap-1.5 rounded-lg border border-dashed border-accent/40 px-3 py-1.5 text-sm font-medium text-accent transition-colors hover:bg-accent/10">
            ＋ Add widget
          </button>
          <span className="rounded-lg bg-neutral-900/50 px-2.5 py-1 text-[11px] text-neutral-500">
            Drag to move · pull a corner to resize · ✕ to remove
          </span>
        </div>
      )}

      {layout.length === 0 ? (
        <Card hover={false} className="flex flex-col items-center justify-center gap-3 py-14 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/10 text-3xl text-accent ring-1 ring-accent/20">▦</span>
          <div>
            <div className="text-sm font-semibold text-neutral-200">This board is empty</div>
            <div className="mt-1 text-xs text-neutral-500">
              {editMode ? "Add widgets from the library to build your view."
                : "Tap ✎ Edit, then ＋ Add widget to start building."}
            </div>
          </div>
          {editMode && (
            <button onClick={() => setShowPalette(true)}
              className="mt-1 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-accent/90">
              ＋ Add your first widget
            </button>
          )}
        </Card>
      ) : (
        <RGL className="layout" layouts={{ lg: layout }} cols={COLS} breakpoints={BREAKPOINTS}
          rowHeight={64} margin={[16, 16]} isDraggable={editMode} isResizable={editMode}
          draggableCancel=".widget-remove" onDragStop={persist} onResizeStop={persist}
          compactType="vertical">
          {layout.map((w) => {
            const def = WIDGET_BY_ID[w.i];
            return (
              <div key={w.i} className={"relative overflow-hidden rounded-2xl " + (editMode ? "cursor-grab active:cursor-grabbing" : "")}>
                {editMode && (
                  <>
                    <div className="edit-frame pointer-events-none absolute inset-0 z-[1] rounded-2xl ring-2 ring-dashed ring-accent/40" />
                    <div className="pointer-events-none absolute left-1.5 top-1.5 z-10 flex h-5 w-5 items-center justify-center rounded-md bg-neutral-950/70 text-neutral-400 opacity-70">
                      <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><circle cx="8" cy="6" r="1.6" /><circle cx="8" cy="12" r="1.6" /><circle cx="8" cy="18" r="1.6" /><circle cx="16" cy="6" r="1.6" /><circle cx="16" cy="12" r="1.6" /><circle cx="16" cy="18" r="1.6" /></svg>
                    </div>
                    <button onClick={() => onRemoveWidget(tab.id, w.i)} title="Remove widget"
                      className="widget-remove absolute right-1.5 top-1.5 z-10 flex h-6 w-6 items-center justify-center rounded-full bg-neutral-950/80 text-neutral-300 shadow-lg ring-1 ring-line/10 transition-colors hover:bg-red-600 hover:text-white">
                      <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
                    </button>
                  </>
                )}
                <div className="h-full overflow-auto">{def.render()}</div>
              </div>
            );
          })}
        </RGL>
      )}

      {showPalette && (
        <InventoryPalette present={layout.map((w) => w.i)}
          onAdd={(widgetId) => {
            const def = WIDGET_BY_ID[widgetId];
            const w = def?.defaultW || 2, h = def?.defaultH || 3;
            const { x, y } = nextSlot(layout, w);
            onAddWidget(tab.id, { i: widgetId, x, y, w, h });
          }}
          onClose={() => setShowPalette(false)} />
      )}
    </div>
  );
}
