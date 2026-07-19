import React, { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import Card from "../components/ui/Card.jsx";
import NoData from "../components/ui/NoData.jsx";
import { PR_TYPES, CATEGORIES, prLabel, prValue, prPace } from "../records.js";
import { fmtDay, localToday } from "../format.js";

// ---------- helpers ----------

const DAY_MS = 86400000;
const dateOf = (r) => (r.start_time || "").slice(0, 10);
const daysAgo = (iso) => Math.max(0, Math.floor((new Date(localToday()) - new Date(iso)) / DAY_MS));

function standing(iso) {
  const d = daysAgo(iso);
  if (d === 0) return "set today";
  if (d === 1) return "set yesterday";
  if (d < 31) return `${d} days standing`;
  if (d < 365) return `${Math.round(d / 30.4)} months standing`;
  return `${(d / 365).toFixed(1)} years standing`;
}

// Count-up: tween 0 -> target with easeOutCubic, formatted by the caller.
function useCountUp(target, { duration = 1400, enabled = true } = {}) {
  const [v, setV] = useState(enabled ? 0 : target);
  useEffect(() => {
    if (!enabled || target == null) { setV(target); return; }
    let raf, start;
    const tick = (t) => {
      if (start == null) start = t;
      const p = Math.min(1, (t - start) / duration);
      setV(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, enabled, duration]);
  return v;
}

// ---------- medal ----------

// SVG medal: two ribbon straps + a metallic disc with an inner ring. Tinted
// per category; the metallic feel comes from layered radial gradients.
function Medal({ color, icon, size = 58 }) {
  const uid = React.useId().replace(/:/g, "");
  return (
    <svg width={size} height={size * 1.28} viewBox="0 0 58 74" aria-hidden="true">
      <defs>
        <radialGradient id={`m${uid}`} cx="35%" cy="30%" r="80%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.85" />
          <stop offset="28%" stopColor={color} />
          <stop offset="100%" stopColor={color} stopOpacity="0.55" />
        </radialGradient>
        <linearGradient id={`r${uid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.9" />
          <stop offset="100%" stopColor={color} stopOpacity="0.45" />
        </linearGradient>
      </defs>
      {/* ribbon straps */}
      <path d="M20 0 L29 26 L15 30 L9 6 Z" fill={`url(#r${uid})`} opacity="0.8" />
      <path d="M38 0 L29 26 L43 30 L49 6 Z" fill={`url(#r${uid})`} />
      {/* disc */}
      <circle cx="29" cy="48" r="24" fill={`url(#m${uid})`} />
      <circle cx="29" cy="48" r="24" fill="none" stroke="rgba(255,255,255,0.35)" strokeWidth="1.5" />
      <circle cx="29" cy="48" r="18.5" fill="none" stroke="rgba(0,0,0,0.28)" strokeWidth="1.2" />
      <text x="29" y="55" textAnchor="middle" fontSize="17">{icon}</text>
    </svg>
  );
}

// ---------- medal card ----------

const cardVariants = {
  hidden: { opacity: 0, y: 26, scale: 0.94 },
  show: (i) => ({
    opacity: 1, y: 0, scale: 1,
    transition: { delay: i * 0.07, type: "spring", stiffness: 260, damping: 22 },
  }),
};

function MedalCard({ record, index }) {
  const reduce = useReducedMotion();
  const meta = PR_TYPES[record.type_id];
  const cat = CATEGORIES[meta.cat];
  const iso = dateOf(record);
  const isNew = daysAgo(iso) <= 30;
  const [seen, setSeen] = useState(false);
  const shown = useCountUp(record.value, { enabled: seen && !reduce });
  const pace = prPace(record.type_id, record.value);

  return (
    <motion.div custom={index} variants={cardVariants} initial="hidden"
      whileInView="show" viewport={{ once: true, margin: "-30px" }}
      onViewportEnter={() => setSeen(true)}
      whileHover={reduce ? undefined : { y: -4, rotate: -0.4 }}
      className="pr-sheen relative overflow-hidden rounded-2xl border border-line/5 glass-card p-4"
      style={{ "--sheen-delay": `${(index % 6) * 0.55}s` }}>
      {/* soft category halo behind the medal */}
      <div className="pointer-events-none absolute -left-6 -top-8 h-32 w-32 rounded-full"
        style={{ background: `radial-gradient(circle, ${cat.color}2e, transparent 65%)` }} />
      {isNew && (
        <span className="pr-pulse absolute right-3 top-3 rounded-full px-2 py-0.5 text-[10px] font-bold tracking-wider"
          style={{ background: `${cat.color}26`, color: cat.color }}>
          NEW
        </span>
      )}
      <div className="flex items-center gap-3.5">
        <Medal color={cat.color} icon={cat.icon} />
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-neutral-500">
            {meta.label}
          </div>
          <div className="mt-0.5 text-[26px] font-bold leading-none tracking-tight text-neutral-50 tabular-nums">
            {prValue(record.type_id, reduce || !seen ? record.value : shown)}
          </div>
          {pace && <div className="mt-1 text-xs text-neutral-400 tabular-nums">{pace}</div>}
          <div className="mt-1.5 truncate text-[11px] text-neutral-500">
            {fmtDay(iso)} · {standing(iso)}
            {record.activity_name ? <span className="text-neutral-600"> · {record.activity_name}</span> : null}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

// ---------- hero stats ----------

function HeroStat({ label, value, sub, delay = 0 }) {
  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.45, ease: "easeOut" }}
      className="rounded-2xl border border-line/5 glass-card px-4 py-3.5">
      <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-neutral-500">{label}</div>
      <div className="mt-1 text-2xl font-bold tracking-tight text-neutral-50">{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-neutral-500">{sub}</div>}
    </motion.div>
  );
}

// ---------- timeline ----------

function Timeline({ groups }) {
  const reduce = useReducedMotion();
  return (
    <div className="relative pl-7">
      {/* the line draws itself as the section scrolls into view */}
      <motion.div className="absolute left-[9px] top-1 w-[2px] rounded-full"
        style={{ background: "linear-gradient(rgb(var(--accent-rgb)/0.7), rgb(var(--accent-rgb)/0.06))" }}
        initial={reduce ? { height: "100%" } : { height: 0 }}
        whileInView={{ height: "100%" }} viewport={{ once: true }}
        transition={{ duration: 1.4, ease: "easeInOut" }} />
      <div className="space-y-5">
        {groups.map(([iso, recs], gi) => (
          <motion.div key={iso}
            initial={reduce ? undefined : { opacity: 0, x: -18 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ delay: gi * 0.06, type: "spring", stiffness: 240, damping: 24 }}
            className="relative">
            {/* node dot */}
            <span className="absolute -left-7 top-1 flex h-5 w-5 items-center justify-center">
              <span className="absolute h-5 w-5 rounded-full bg-accent/15" />
              <span className="h-2.5 w-2.5 rounded-full bg-accent ring-2 ring-neutral-950" />
            </span>
            <div className="text-xs font-semibold text-neutral-300">
              {fmtDay(iso)}
              <span className="ml-2 font-normal text-neutral-600">{standing(iso)}</span>
              {recs.length > 1 && (
                <span className="ml-2 rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-bold text-accent">
                  {recs.length} records in one day
                </span>
              )}
            </div>
            <div className="mt-1.5 flex flex-wrap gap-2">
              {recs.map((r) => {
                const cat = CATEGORIES[PR_TYPES[r.type_id].cat];
                return (
                  <span key={r.id}
                    className="flex items-center gap-1.5 rounded-lg border border-line/10 bg-neutral-950/40 px-2.5 py-1.5 text-xs"
                    style={{ borderColor: `${cat.color}33` }}>
                    <span>{cat.icon}</span>
                    <span className="text-neutral-300">{prLabel(r.type_id)}</span>
                    <span className="font-semibold text-neutral-100 tabular-nums">
                      {prValue(r.type_id, r.value)}
                    </span>
                  </span>
                );
              })}
            </div>
            {recs[0]?.activity_name && (
              <div className="mt-1 text-[11px] text-neutral-600">{recs[0].activity_name}</div>
            )}
          </motion.div>
        ))}
      </div>
    </div>
  );
}

// ---------- the tab ----------

export default function Records({ today }) {
  const records = (today?.records || []).filter((r) => PR_TYPES[r.type_id] && r.value != null);

  if (!records.length) {
    return (
      <Card>
        <NoData label="No personal records yet — go break something 🏅" />
      </Card>
    );
  }

  // Hero stats
  const sorted = [...records].sort((a, b) => dateOf(b).localeCompare(dateOf(a)));
  const newest = sorted[0];
  const groupsMap = new Map();
  for (const r of [...records].sort((a, b) => dateOf(a).localeCompare(dateOf(b)))) {
    const iso = dateOf(r);
    if (!groupsMap.has(iso)) groupsMap.set(iso, []);
    groupsMap.get(iso).push(r);
  }
  const groupsAsc = [...groupsMap.entries()];
  const bigDay = groupsAsc.reduce((best, g) => (g[1].length > best[1].length ? g : best), groupsAsc[0]);
  const recent30 = records.filter((r) => daysAgo(dateOf(r)) <= 30).length;

  const byCat = {};
  for (const r of records) {
    const c = PR_TYPES[r.type_id].cat;
    (byCat[c] = byCat[c] || []).push(r);
  }
  let cardIndex = 0;

  return (
    <div className="space-y-6">
      <div>
        <motion.h2 initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="text-lg font-bold tracking-tight text-neutral-50">
          🏅 Trophy room
        </motion.h2>
        <p className="text-xs text-neutral-500">Every all-time best your watch has witnessed.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <HeroStat label="Records held" value={records.length} delay={0.05} />
        <HeroStat label="Latest" value={prLabel(newest.type_id)}
          sub={`${fmtDay(dateOf(newest))} · ${prValue(newest.type_id, newest.value)}`} delay={0.12} />
        <HeroStat label="Biggest day" value={`${bigDay[1].length} records`}
          sub={`${fmtDay(bigDay[0])}${bigDay[1][0]?.activity_name ? ` · ${bigDay[1][0].activity_name}` : ""}`}
          delay={0.19} />
        <HeroStat label="Last 30 days" value={recent30}
          sub={recent30 ? "keep it rolling" : "hungry for the next one?"} delay={0.26} />
      </div>

      {Object.entries(CATEGORIES).map(([key, cat]) =>
        byCat[key]?.length ? (
          <section key={key}>
            <div className="mb-2.5 flex items-center gap-2">
              <span className="text-base">{cat.icon}</span>
              <h3 className="text-sm font-semibold tracking-wide text-neutral-200">{cat.title}</h3>
              <span className="h-px flex-1" style={{ background: `linear-gradient(90deg, ${cat.color}55, transparent)` }} />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {byCat[key]
                .sort((a, b) => (PR_TYPES[a.type_id].label > PR_TYPES[b.type_id].label ? 1 : -1))
                .map((r) => <MedalCard key={r.id} record={r} index={cardIndex++} />)}
            </div>
          </section>
        ) : null
      )}

      <Card hover={false}>
        <div className="mb-3">
          <h3 className="text-sm font-semibold tracking-wide text-neutral-200">The road to now</h3>
          <p className="text-[11px] text-neutral-500">When each record fell, oldest first.</p>
        </div>
        <Timeline groups={groupsAsc} />
      </Card>
    </div>
  );
}
