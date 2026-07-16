import React from "react";

// Renders coach replies: short paragraphs, "- " bullet lists, **bold** — the
// only markdown the coach is allowed to produce. No dependency, no raw HTML.

const TONE = {
  good:    { color: "#34d399", bg: "rgba(52,211,153,.10)", ring: "rgba(52,211,153,.35)" },
  warn:    { color: "#fbbf24", bg: "rgba(251,191,36,.10)", ring: "rgba(251,191,36,.35)" },
  bad:     { color: "#f87171", bg: "rgba(248,113,113,.10)", ring: "rgba(248,113,113,.35)" },
  neutral: { color: "#a1a1aa", bg: "rgba(161,161,170,.10)", ring: "rgba(161,161,170,.30)" },
};

export function Highlights({ items }) {
  if (!items || !items.length) return null;
  return (
    <div className="mb-3 flex flex-wrap gap-2">
      {items.map((h, i) => {
        const t = TONE[h.tone] || TONE.neutral;
        return (
          <span key={i}
            className="inline-flex items-baseline gap-1.5 rounded-lg px-2.5 py-1.5 text-xs"
            style={{ background: t.bg, border: `1px solid ${t.ring}` }}>
            <span className="uppercase tracking-wide text-neutral-400">{h.label}</span>
            <span className="text-sm font-bold" style={{ color: t.color }}>{h.value}</span>
          </span>
        );
      })}
    </div>
  );
}

// **bold** spans within a line.
function Line({ text }) {
  const parts = String(text).split(/\*\*(.+?)\*\*/g);
  return parts.map((p, i) =>
    i % 2 ? <b key={i} className="font-semibold text-neutral-50">{p}</b> : p);
}

export default function CoachText({ text }) {
  if (!text) return null;
  const blocks = String(text).replace(/\r/g, "").split(/\n{2,}/);
  return (
    <div className="space-y-2.5 text-sm leading-relaxed text-neutral-200">
      {blocks.map((block, bi) => {
        const lines = block.split("\n").filter((l) => l.trim() !== "");
        const isList = lines.length > 0 && lines.every((l) => /^\s*[-•]\s+/.test(l));
        if (isList) {
          return (
            <ul key={bi} className="space-y-1.5 pl-1">
              {lines.map((l, li) => (
                <li key={li} className="flex gap-2">
                  <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500/70" />
                  <span><Line text={l.replace(/^\s*[-•]\s+/, "")} /></span>
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={bi}>
            {lines.map((l, li) => (
              <React.Fragment key={li}>
                {li > 0 && <br />}
                {/^\s*[-•]\s+/.test(l)
                  ? <span className="block pl-3">• <Line text={l.replace(/^\s*[-•]\s+/, "")} /></span>
                  : <Line text={l} />}
              </React.Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}
