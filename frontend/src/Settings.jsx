import React, { useState } from "react";
import { motion } from "framer-motion";
import { exportUrl } from "./api.js";

const TABS = [
  ["overview", "Overview"],
  ["sleep", "Sleep"],
  ["training", "Strain & Training"],
  ["activities", "Activities"],
  ["trends", "Trends"],
];

// settings: current settings object. onChange(partial) persists + updates.
// onSwitchAccount(): wipes data + signs out. onClose(): dismiss.
export default function Settings({ settings, onChange, onSwitchAccount, onClose }) {
  const [confirmSwitch, setConfirmSwitch] = useState(false);
  const s = settings || {};
  const hidden = s.hidden_tabs || [];

  const toggleTab = (key) => {
    const next = hidden.includes(key) ? hidden.filter((t) => t !== key) : [...hidden, key];
    onChange({ hidden_tabs: next });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4 backdrop-blur-sm"
      onClick={onClose}>
      <motion.div
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.25, ease: "easeOut" }}
        onClick={(e) => e.stopPropagation()}
        className="mt-10 w-full max-w-md rounded-2xl border border-line/10 bg-neutral-900 p-5 shadow-2xl"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold text-neutral-50">Settings</h2>
          <button onClick={onClose} className="text-neutral-500 hover:text-neutral-200">✕</button>
        </div>

        <div className="space-y-5">
          {/* Units */}
          <Row label="Units">
            <div className="flex gap-1 rounded-lg border border-line/10 bg-neutral-950/60 p-0.5">
              {["metric", "imperial"].map((u) => (
                <button key={u} onClick={() => onChange({ units: u })}
                  className={"rounded-md px-3 py-1 text-sm capitalize transition-colors " +
                    (s.units === u ? "bg-emerald-600 text-neutral-50" : "text-neutral-400 hover:text-neutral-200")}>
                  {u}
                </button>
              ))}
            </div>
          </Row>

          {/* Sync interval */}
          <Row label="Sync interval" hint="minutes (5–240)">
            <NumberInput value={s.sync_interval_minutes} min={5} max={240}
              onCommit={(v) => onChange({ sync_interval_minutes: v })} />
          </Row>

          {/* Baseline window */}
          <Row label="Recovery baseline" hint="days (7–60)">
            <NumberInput value={s.baseline_window_days} min={7} max={60}
              onCommit={(v) => onChange({ baseline_window_days: v })} />
          </Row>

          {/* Tab visibility */}
          <div>
            <div className="mb-2 text-sm text-neutral-300">Visible tabs</div>
            <div className="space-y-1.5">
              {TABS.map(([key, label]) => (
                <label key={key} className="flex items-center gap-2 text-sm text-neutral-300">
                  <input type="checkbox" checked={!hidden.includes(key)} onChange={() => toggleTab(key)}
                    className="h-4 w-4 accent-emerald-600" />
                  {label}
                </label>
              ))}
            </div>
            <p className="mt-1 text-[11px] text-neutral-600">
              Tabs your watch doesn't report are hidden automatically; this is an extra manual filter.
            </p>
          </div>

          {/* Export */}
          <div className="border-t border-line/10 pt-4">
            <div className="mb-2 text-sm text-neutral-300">Export your data</div>
            <div className="flex gap-2">
              <a href={exportUrl("json")} download
                className="rounded-lg border border-line/10 bg-neutral-800/80 px-3 py-1.5 text-sm text-neutral-200 hover:bg-neutral-700">
                JSON
              </a>
              <a href={exportUrl("csv")} download
                className="rounded-lg border border-line/10 bg-neutral-800/80 px-3 py-1.5 text-sm text-neutral-200 hover:bg-neutral-700">
                CSV (daily)
              </a>
            </div>
          </div>

          {/* Phone access */}
          <div className="border-t border-line/10 pt-4">
            <label className="flex items-center gap-2 text-sm text-neutral-300">
              <input type="checkbox" checked={!!s.phone_access}
                onChange={(e) => onChange({ phone_access: e.target.checked })}
                className="h-4 w-4 accent-emerald-600" />
              Enable phone access (LAN + Tailscale)
            </label>
            <div className="mt-2 flex items-center justify-between gap-4">
              <div>
                <div className="text-sm text-neutral-300">Access PIN</div>
                <div className="text-[11px] text-neutral-600">required for any phone/network access</div>
              </div>
              <PinInput value={s.access_pin} onCommit={(v) => onChange({ access_pin: v })} />
            </div>
            <p className="mt-1 text-[11px] text-neutral-600">
              Relaunch to apply, then open <span className="text-neutral-400">http://&lt;your-pc&gt;:5057</span> on
              your phone (Safari → Add to Home Screen).
            </p>
          </div>

          {/* Account */}
          <div className="border-t border-line/10 pt-4">
            {!confirmSwitch ? (
              <button onClick={() => setConfirmSwitch(true)}
                className="text-sm text-red-400 hover:text-red-300">
                Switch Garmin account…
              </button>
            ) : (
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3">
                <p className="text-sm text-neutral-200">
                  Switch account? This signs you out and <b>erases this account's local data</b> so the
                  next account starts clean.
                </p>
                <div className="mt-2 flex gap-2">
                  <button onClick={onSwitchAccount}
                    className="rounded-md bg-red-600 px-3 py-1 text-sm font-semibold text-neutral-50 hover:bg-red-500">
                    Switch &amp; erase
                  </button>
                  <button onClick={() => setConfirmSwitch(false)}
                    className="rounded-md bg-neutral-800 px-3 py-1 text-sm text-neutral-300 hover:bg-neutral-700">
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
}

function Row({ label, hint, children }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <div className="text-sm text-neutral-300">{label}</div>
        {hint && <div className="text-[11px] text-neutral-600">{hint}</div>}
      </div>
      {children}
    </div>
  );
}

function PinInput({ value, onCommit }) {
  const [v, setV] = useState(value || "");
  return (
    <input
      type="text" inputMode="numeric" value={v} placeholder="set a PIN"
      onChange={(e) => setV(e.target.value)}
      onBlur={() => onCommit(v.trim())}
      onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
      className="w-28 rounded-lg border border-line/10 bg-neutral-950/60 px-2 py-1 text-right text-sm text-neutral-100 outline-none focus:border-emerald-500/60"
    />
  );
}

function NumberInput({ value, min, max, onCommit }) {
  const [v, setV] = useState(value);
  const commit = () => {
    const n = Math.max(min, Math.min(max, parseInt(v, 10) || min));
    setV(n);
    onCommit(n);
  };
  return (
    <input
      type="number" min={min} max={max} value={v}
      onChange={(e) => setV(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
      className="w-20 rounded-lg border border-line/10 bg-neutral-950/60 px-2 py-1 text-right text-sm text-neutral-100 outline-none focus:border-emerald-500/60"
    />
  );
}
