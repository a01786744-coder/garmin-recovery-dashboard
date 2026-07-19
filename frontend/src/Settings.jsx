import React, { useRef, useState } from "react";
import { motion } from "framer-motion";
import { exportUrl, configBackupUrl, postConfigRestore, getSettings } from "./api.js";

const APP_VERSION = typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "";

const SECTIONS = [
  ["general", "General", "⚙"],
  ["dashboard", "Dashboard & Tabs", "▦"],
  ["recovery", "Recovery & Metrics", "❤"],
  ["data", "Sync & Data", "⟳"],
  ["coach", "AI Coach", "🤖"],
  ["phone", "Phone & Sharing", "📱"],
  ["about", "About", "ℹ"],
];

const ACCENTS = ["#22c55e", "#38bdf8", "#8b5cf6", "#f97316", "#ef4444",
                 "#eab308", "#ec4899", "#14b8a6", "#f59e0b", "#6366f1"];
const THEMES = [["dark", "Dark"], ["light", "Light"], ["midnight", "Midnight"],
                ["slate", "Slate"], ["contrast", "Contrast"]];
const TONES = [["balanced", "Balanced"], ["concise", "Concise"],
               ["detailed", "Detailed"], ["tough", "Tough love"],
               ["encouraging", "Encouraging"]];

// settings: current settings object. onChange(partial) persists + updates.
// tabs: [{key,label,custom}] merged tab list. onSwitchAccount/onClose.
export default function Settings({ settings, onChange, tabs, onSwitchAccount, onClose }) {
  const [section, setSection] = useState("general");
  const s = settings || {};

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onClick={onClose}>
      <motion.div
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.22, ease: "easeOut" }}
        onClick={(e) => e.stopPropagation()}
        className="flex h-[85vh] max-h-[720px] w-full max-w-3xl overflow-hidden rounded-2xl border border-line/10 bg-neutral-900 shadow-2xl">

        {/* Left rail (desktop) */}
        <nav className="hidden w-52 shrink-0 flex-col gap-0.5 border-r border-line/10 bg-neutral-950/40 p-3 sm:flex">
          <div className="px-2 pb-2 text-sm font-bold text-neutral-50">Settings</div>
          {SECTIONS.map(([id, label, icon]) => (
            <button key={id} onClick={() => setSection(id)}
              className={"flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors " +
                (section === id ? "bg-accent/15 text-neutral-50"
                                : "text-neutral-400 hover:bg-line/5 hover:text-neutral-200")}>
              <span className="w-4 text-center">{icon}</span>{label}
            </button>
          ))}
        </nav>

        <div className="flex min-w-0 flex-1 flex-col">
          {/* Mobile section chips + close */}
          <div className="flex items-center justify-between gap-2 border-b border-line/10 p-3">
            <div className="flex gap-1 overflow-x-auto sm:hidden">
              {SECTIONS.map(([id, , icon]) => (
                <button key={id} onClick={() => setSection(id)} title={id}
                  className={"shrink-0 rounded-lg px-2.5 py-1.5 text-sm " +
                    (section === id ? "bg-accent/15 text-neutral-50" : "text-neutral-400")}>
                  {icon}
                </button>
              ))}
            </div>
            <div className="hidden text-sm font-semibold text-neutral-200 sm:block">
              {SECTIONS.find(([id]) => id === section)?.[1]}
            </div>
            <button onClick={onClose} className="text-neutral-500 hover:text-neutral-200">✕</button>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {section === "general" && <General s={s} onChange={onChange} tabs={tabs} />}
            {section === "dashboard" && <Dashboard s={s} onChange={onChange} tabs={tabs} />}
            {section === "recovery" && <Recovery s={s} onChange={onChange} />}
            {section === "data" && <Data s={s} onChange={onChange} onSwitchAccount={onSwitchAccount} />}
            {section === "coach" && <Coach s={s} onChange={onChange} />}
            {section === "phone" && <Phone s={s} onChange={onChange} />}
            {section === "about" && <About />}
          </div>
        </div>
      </motion.div>
    </div>
  );
}

// ---------- sections ----------

function General({ s, onChange, tabs }) {
  return (
    <div className="space-y-5">
      <Field label="Units">
        <Segmented value={s.units} onChange={(v) => onChange({ units: v })}
          options={[["metric", "Metric"], ["imperial", "Imperial"]]} />
      </Field>
      <Field label="Theme">
        <div className="flex flex-wrap gap-1.5">
          {THEMES.map(([v, label]) => (
            <button key={v} onClick={() => onChange({ theme: v })}
              className={"rounded-lg border px-3 py-1.5 text-sm transition-colors " +
                (s.theme === v ? "border-accent/60 bg-accent/15 text-neutral-50"
                               : "border-line/10 text-neutral-400 hover:text-neutral-200")}>
              {label}
            </button>
          ))}
        </div>
      </Field>
      <Field label="Accent color" hint="recolors buttons, active tab, and the recovery ring">
        <div className="flex flex-wrap items-center gap-2">
          {ACCENTS.map((c) => (
            <button key={c} onClick={() => onChange({ accent_color: c })}
              title={c} className={"h-7 w-7 rounded-full ring-2 ring-offset-2 ring-offset-neutral-900 transition-transform hover:scale-110 " +
                (s.accent_color === c ? "ring-white/70" : "ring-transparent")}
              style={{ background: c }} />
          ))}
          <label className="ml-1 cursor-pointer text-xs text-neutral-500 hover:text-neutral-300">
            custom
            <input type="color" value={s.accent_color || "#22c55e"}
              onChange={(e) => onChange({ accent_color: e.target.value })}
              className="ml-1 h-6 w-6 cursor-pointer rounded bg-transparent align-middle" />
          </label>
        </div>
      </Field>
      <Field label="Density">
        <Segmented value={s.density} onChange={(v) => onChange({ density: v })}
          options={[["comfortable", "Comfortable"], ["compact", "Compact"]]} />
      </Field>
      <Field label="Default tab" hint="which tab opens on launch">
        <select value={s.default_tab || ""} onChange={(e) => onChange({ default_tab: e.target.value })}
          className="rounded-lg border border-line/10 bg-neutral-950/60 px-2 py-1.5 text-sm text-neutral-100 outline-none">
          <option value="">First visible</option>
          {(tabs || []).map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
        </select>
      </Field>
      <Field label="Chart dates">
        <Segmented value={s.date_style} onChange={(v) => onChange({ date_style: v })}
          options={[["month", "Jul 4"], ["number", "07-04"]]} />
      </Field>
      <Field label="Week starts on">
        <Segmented value={s.week_start} onChange={(v) => onChange({ week_start: v })}
          options={[["mon", "Monday"], ["sun", "Sunday"]]} />
      </Field>
      <Field label="Weather units" hint="activity weather">
        <Segmented value={s.weather_units} onChange={(v) => onChange({ weather_units: v })}
          options={[["c", "°C"], ["f", "°F"]]} />
      </Field>
      <Field label="Clock">
        <Segmented value={String(s.clock)} onChange={(v) => onChange({ clock: v })}
          options={[["24", "24-hour"], ["12", "12-hour"]]} />
      </Field>
    </div>
  );
}

function Dashboard({ s, onChange, tabs }) {
  const hidden = s.hidden_tabs || [];
  const toggle = (key) => onChange({ hidden_tabs:
    hidden.includes(key) ? hidden.filter((t) => t !== key) : [...hidden, key] });
  return (
    <div className="space-y-5">
      <p className="text-sm text-neutral-400">
        Reorder tabs and build custom ones from the <b className="text-neutral-200">✎ Edit</b> button
        on the tab bar. Here you can hide/show tabs and reset your layout.
      </p>
      <div>
        <div className="mb-2 text-sm text-neutral-300">Visible tabs</div>
        <div className="space-y-1.5">
          {(tabs || []).map((t) => (
            <label key={t.key} className="flex items-center gap-2 text-sm text-neutral-300">
              <input type="checkbox" checked={!hidden.includes(t.key)} onChange={() => toggle(t.key)}
                className="h-4 w-4" style={{ accentColor: "var(--accent)" }} />
              {t.icon ? `${t.icon} ` : ""}{t.label}{t.custom ? " (custom)" : ""}
            </label>
          ))}
        </div>
        <p className="mt-1 text-[11px] text-neutral-600">
          Tabs your watch doesn't report are hidden automatically; this is an extra manual filter.
        </p>
      </div>
      <div className="border-t border-line/10 pt-4">
        <button onClick={() => { if (confirm("Reset tab order, hidden tabs, and custom tabs to default?"))
            onChange({ tab_order: [], hidden_tabs: [], custom_tabs: [] }); }}
          className="text-sm text-red-400 hover:text-red-300">Reset layout to default…</button>
      </div>
    </div>
  );
}

function Recovery({ s, onChange }) {
  const hrv = Math.round((s.hrv_weight ?? 0.7) * 100);
  return (
    <div className="space-y-6">
      <Field label="Recovery baseline" hint="days of history (7–60)">
        <NumberInput value={s.baseline_window_days} min={7} max={60}
          onCommit={(v) => onChange({ baseline_window_days: v })} />
      </Field>
      <div>
        <div className="flex items-center justify-between text-sm text-neutral-300">
          <span>HRV vs Resting HR weighting</span>
          <span className="tabular-nums text-neutral-100">{hrv}% HRV · {100 - hrv}% RHR</span>
        </div>
        <input type="range" min={0} max={100} value={hrv}
          onChange={(e) => onChange({ hrv_weight: Number(e.target.value) / 100 })}
          className="mt-2 w-full" style={{ accentColor: "var(--accent)" }} />
        <p className="mt-1 text-[11px] text-neutral-600">
          Splits the autonomic core of your recovery score (60% of the total)
          between overnight HRV and resting heart rate. The rest comes from
          sleep (25%), respiration (7%), skin temp (4%), and SpO2 (4%) when
          available. Changing this re-scores your history. Default 70/30.
        </p>
      </div>
      <div>
        <div className="mb-2 text-sm text-neutral-300">Recovery color bands</div>
        <div className="flex flex-wrap items-end gap-4">
          <label className="text-xs text-neutral-500">
            Green ≥
            <NumberInput value={s.recovery_green} min={2} max={99}
              onCommit={(v) => onChange({ recovery_green: v })} />
          </label>
          <label className="text-xs text-neutral-500">
            Amber ≥
            <NumberInput value={s.recovery_amber} min={1} max={98}
              onCommit={(v) => onChange({ recovery_amber: v })} />
          </label>
        </div>
        <p className="mt-1 text-[11px] text-neutral-600">
          Score at/above green is green; at/above amber is amber; below is red. (Whoop-style default 67 / 34.)
        </p>
      </div>
      <Field label="Sleep goal" hint="minutes/night (0 = use Garmin's need)">
        <NumberInput value={s.sleep_goal_min} min={0} max={720}
          onCommit={(v) => onChange({ sleep_goal_min: v })} />
      </Field>
      <Field label="Max heart rate" hint="for zone accuracy (0 = auto)">
        <NumberInput value={s.max_hr} min={0} max={230}
          onCommit={(v) => onChange({ max_hr: v })} />
      </Field>
    </div>
  );
}

function Data({ s, onChange, onSwitchAccount }) {
  const [confirmSwitch, setConfirmSwitch] = useState(false);
  const [restoreMsg, setRestoreMsg] = useState(null);
  const fileRef = useRef(null);

  const onRestoreFile = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    try {
      const data = JSON.parse(await f.text());
      const r = await postConfigRestore(data);
      setRestoreMsg(r.ok ? `Restored (${r.journal_restored} journal days). Reload to see changes.`
                          : `Restore failed: ${r.error || "bad file"}`);
    } catch {
      setRestoreMsg("That file isn't a valid backup.");
    }
    e.target.value = "";
  };

  return (
    <div className="space-y-5">
      <Field label="Sync interval" hint="minutes (5–240)">
        <NumberInput value={s.sync_interval_minutes} min={5} max={240}
          onCommit={(v) => onChange({ sync_interval_minutes: v })} />
      </Field>
      <Toggle label="Sync on launch" checked={s.sync_on_launch}
        onChange={(v) => onChange({ sync_on_launch: v })} />
      <Toggle label="Pause automatic syncing" checked={s.sync_paused}
        onChange={(v) => onChange({ sync_paused: v })}
        hint="stops background syncs; a manual sync still works" />
      <Toggle label="Morning notification" checked={s.morning_notification}
        onChange={(v) => onChange({ morning_notification: v })}
        hint="once a day after sync: recovery score + the coach's headline" />

      <div className="border-t border-line/10 pt-4">
        <div className="mb-2 text-sm text-neutral-300">Export your health data</div>
        <div className="flex gap-2">
          <a href={exportUrl("json")} download className="rounded-lg border border-line/10 bg-neutral-800/80 px-3 py-1.5 text-sm text-neutral-200 hover:bg-neutral-700">JSON</a>
          <a href={exportUrl("csv")} download className="rounded-lg border border-line/10 bg-neutral-800/80 px-3 py-1.5 text-sm text-neutral-200 hover:bg-neutral-700">CSV (daily)</a>
        </div>
      </div>

      <div className="border-t border-line/10 pt-4">
        <div className="mb-1 text-sm text-neutral-300">Backup &amp; restore settings</div>
        <div className="text-[11px] text-neutral-600">your settings, custom tabs, and journal (not your API key)</div>
        <div className="mt-2 flex gap-2">
          <a href={configBackupUrl()} download className="rounded-lg border border-line/10 bg-neutral-800/80 px-3 py-1.5 text-sm text-neutral-200 hover:bg-neutral-700">Back up</a>
          <button onClick={() => fileRef.current?.click()} className="rounded-lg border border-line/10 bg-neutral-800/80 px-3 py-1.5 text-sm text-neutral-200 hover:bg-neutral-700">Restore…</button>
          <input ref={fileRef} type="file" accept="application/json,.json" onChange={onRestoreFile} className="hidden" />
        </div>
        {restoreMsg && <p className="mt-2 text-[11px] text-emerald-300">{restoreMsg}</p>}
      </div>

      <div className="border-t border-line/10 pt-4">
        {!confirmSwitch ? (
          <button onClick={() => setConfirmSwitch(true)} className="text-sm text-red-400 hover:text-red-300">Switch Garmin account…</button>
        ) : (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3">
            <p className="text-sm text-neutral-200">Switch account? This signs you out and <b>erases this account's local data</b>.</p>
            <div className="mt-2 flex gap-2">
              <button onClick={onSwitchAccount} className="rounded-md bg-red-600 px-3 py-1 text-sm font-semibold text-neutral-50 hover:bg-red-500">Switch &amp; erase</button>
              <button onClick={() => setConfirmSwitch(false)} className="rounded-md bg-neutral-800 px-3 py-1 text-sm text-neutral-300 hover:bg-neutral-700">Cancel</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Coach({ s, onChange }) {
  return (
    <div className="space-y-5">
      <Toggle label="Enable AI Coach (Claude)" checked={s.coach_enabled}
        onChange={(v) => onChange({ coach_enabled: v })} />
      <Field label="Anthropic API key" hint="from console.anthropic.com → API keys">
        <KeyInput value={s.anthropic_api_key} onCommit={(v) => onChange({ anthropic_api_key: v })} />
      </Field>
      <Field label="Model">
        <select value={s.coach_model || "claude-sonnet-5"} onChange={(e) => onChange({ coach_model: e.target.value })}
          className="rounded-lg border border-line/10 bg-neutral-950/60 px-2 py-1.5 text-sm text-neutral-100 outline-none">
          <option value="claude-sonnet-5">Sonnet 5 (recommended)</option>
          <option value="claude-opus-4-8">Opus 4.8 (best, pricier)</option>
          <option value="claude-haiku-4-5">Haiku 4.5 (cheapest)</option>
        </select>
      </Field>
      <Field label="Coaching tone">
        <select value={s.coach_tone || "balanced"} onChange={(e) => onChange({ coach_tone: e.target.value })}
          className="rounded-lg border border-line/10 bg-neutral-950/60 px-2 py-1.5 text-sm text-neutral-100 outline-none">
          {TONES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
        </select>
      </Field>
      <Toggle label="Auto-generate the morning brief" checked={s.coach_auto_brief}
        onChange={(v) => onChange({ coach_auto_brief: v })}
        hint="creates today's brief automatically on the first sync each day" />
      <Field label="Default warmup" hint="minutes for coach workouts">
        <NumberInput value={Math.round((s.coach_warmup_default_s ?? 600) / 60)} min={0} max={30}
          onCommit={(v) => onChange({ coach_warmup_default_s: v * 60 })} />
      </Field>
      <Field label="Interval targets">
        <Segmented value={s.coach_target_pref} onChange={(v) => onChange({ coach_target_pref: v })}
          options={[["auto", "Auto"], ["pace", "Pace"], ["hr", "Heart rate"]]} />
      </Field>
      <Field label="Monthly spend reminder" hint="USD, 0 = off">
        <NumberInput value={s.coach_budget_reminder} min={0} max={1000}
          onCommit={(v) => onChange({ coach_budget_reminder: v })} />
      </Field>
      <p className="text-[11px] text-neutral-600">
        Opt-in: when enabled, your recent metrics, activities and journal are sent to Anthropic's API
        to generate coaching — never your Garmin credentials. The key is stored only on this machine.
      </p>
    </div>
  );
}

function Phone({ s, onChange }) {
  return (
    <div className="space-y-5">
      <Toggle label="Enable phone access (LAN + Tailscale)" checked={s.phone_access}
        onChange={(v) => onChange({ phone_access: v })} />
      <Field label="Access PIN" hint="required for any phone/network access">
        <PinInput value={s.access_pin} onCommit={(v) => onChange({ access_pin: v })} />
      </Field>
      <p className="text-[11px] text-neutral-600">
        Relaunch to apply, then open <span className="text-neutral-400">http://&lt;your-pc&gt;:5057</span> on
        your phone (Safari → Add to Home Screen).
      </p>
      <Toggle label="Start at login (minimized to tray)" checked={s.start_at_login}
        onChange={(v) => onChange({ start_at_login: v })} />
      <Toggle label="Check for updates on launch" checked={s.check_updates}
        onChange={(v) => onChange({ check_updates: v })} />
    </div>
  );
}

function About() {
  return (
    <div className="space-y-3 text-sm text-neutral-300">
      <div className="flex justify-between"><span className="text-neutral-500">Version</span><span className="tabular-nums">{APP_VERSION || "—"}</span></div>
      <div className="flex justify-between"><span className="text-neutral-500">App</span><span>Garmin Recovery Dashboard</span></div>
      <a href="https://github.com/a01786744-coder/garmin-recovery-dashboard/blob/main/CHANGELOG.md"
        target="_blank" rel="noreferrer" className="block text-accent hover:underline">What's new (changelog) ↗</a>
      <a href="https://github.com/a01786744-coder/garmin-recovery-dashboard"
        target="_blank" rel="noreferrer" className="block text-accent hover:underline">Source on GitHub ↗</a>
      <p className="pt-2 text-[11px] text-neutral-600">
        Local-first: your health data and tokens never leave this machine. Unofficial Garmin
        Connect client — for personal insight only, not medical advice.
      </p>
    </div>
  );
}

// ---------- reusable controls ----------

function Field({ label, hint, children }) {
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

function Segmented({ value, onChange, options }) {
  return (
    <div className="flex gap-1 rounded-lg border border-line/10 bg-neutral-950/60 p-0.5">
      {options.map(([v, label]) => (
        <button key={v} onClick={() => onChange(v)}
          className={"rounded-md px-3 py-1 text-sm transition-colors " +
            (value === v ? "bg-accent text-neutral-950" : "text-neutral-400 hover:text-neutral-200")}>
          {label}
        </button>
      ))}
    </div>
  );
}

function Toggle({ label, hint, checked, onChange }) {
  return (
    <div>
      <label className="flex items-center gap-2 text-sm text-neutral-300">
        <input type="checkbox" checked={!!checked} onChange={(e) => onChange(e.target.checked)}
          className="h-4 w-4" style={{ accentColor: "var(--accent)" }} />
        {label}
      </label>
      {hint && <p className="ml-6 mt-0.5 text-[11px] text-neutral-600">{hint}</p>}
    </div>
  );
}

function PinInput({ value, onCommit }) {
  const [v, setV] = useState(value || "");
  return (
    <input type="text" inputMode="numeric" value={v} placeholder="set a PIN"
      onChange={(e) => setV(e.target.value)} onBlur={() => onCommit(v.trim())}
      onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
      className="w-28 rounded-lg border border-line/10 bg-neutral-950/60 px-2 py-1 text-right text-sm text-neutral-100 outline-none focus:border-accent/60" />
  );
}

function KeyInput({ value, onCommit }) {
  const [v, setV] = useState(value || "");
  return (
    <input type="password" value={v} placeholder="sk-ant-…" autoComplete="off"
      onChange={(e) => setV(e.target.value)} onBlur={() => onCommit(v.trim())}
      onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
      className="w-52 rounded-lg border border-line/10 bg-neutral-950/60 px-2 py-1 text-right text-sm text-neutral-100 outline-none focus:border-accent/60" />
  );
}

function NumberInput({ value, min, max, onCommit }) {
  const [v, setV] = useState(value);
  React.useEffect(() => { setV(value); }, [value]);
  const commit = () => {
    const n = Math.max(min, Math.min(max, parseInt(v, 10) || min));
    setV(n);
    onCommit(n);
  };
  return (
    <input type="number" min={min} max={max} value={v}
      onChange={(e) => setV(e.target.value)} onBlur={commit}
      onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
      className="ml-1 w-20 rounded-lg border border-line/10 bg-neutral-950/60 px-2 py-1 text-right text-sm text-neutral-100 outline-none focus:border-accent/60" />
  );
}
