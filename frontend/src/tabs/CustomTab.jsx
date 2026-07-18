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
        <div className="mb-3 flex items-center gap-2">
          <button onClick={() => setShowPalette(true)}
            className="rounded-lg border border-emerald-500/40 px-3 py-1.5 text-sm font-medium text-emerald-300 hover:bg-accent/90/10">
            ＋ Add widget
          </button>
          <span className="text-[11px] text-neutral-500">Drag to move · drag a corner to resize · ✕ to remove</span>
        </div>
      )}

      {layout.length === 0 ? (
        <Card>
          <NoData label={editMode ? "Empty tab — tap ＋ Add widget to fill it"
            : "This tab is empty. Tap ✎ Edit, then ＋ Add widget."} />
        </Card>
      ) : (
        <RGL className="layout" layouts={{ lg: layout }} cols={COLS} breakpoints={BREAKPOINTS}
          rowHeight={64} margin={[16, 16]} isDraggable={editMode} isResizable={editMode}
          draggableCancel=".widget-remove" onDragStop={persist} onResizeStop={persist}
          compactType="vertical">
          {layout.map((w) => {
            const def = WIDGET_BY_ID[w.i];
            return (
              <div key={w.i} className="relative overflow-hidden">
                {editMode && (
                  <button onClick={() => onRemoveWidget(tab.id, w.i)}
                    className="widget-remove absolute right-1 top-1 z-10 flex h-5 w-5 items-center justify-center rounded-full bg-neutral-800/90 text-xs text-red-300 hover:bg-red-600 hover:text-white">
                    ✕
                  </button>
                )}
                {editMode && (
                  <div className="pointer-events-none absolute inset-0 z-0 rounded-2xl ring-2 ring-dashed ring-accent/60/30" />
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
