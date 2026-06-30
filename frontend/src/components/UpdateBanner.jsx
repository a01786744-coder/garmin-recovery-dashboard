import React, { useEffect, useState } from "react";

/* eslint-disable no-undef */
const CUR = typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "0.0.0";
const REPO = typeof __REPO__ !== "undefined" ? __REPO__ : "";
/* eslint-enable no-undef */

// Compare dotted numeric versions (e.g. "3.2.1" vs "3.2.0"). Pre-release/suffix
// parts are ignored; only the numeric core matters for the notice.
export function isNewer(remote, current) {
  const norm = (v) => String(v).replace(/^v/, "").split(".").map((n) => parseInt(n, 10) || 0);
  const r = norm(remote), c = norm(current);
  for (let i = 0; i < Math.max(r.length, c.length); i++) {
    const a = r[i] || 0, b = c[i] || 0;
    if (a !== b) return a > b;
  }
  return false;
}

// One external call (to GitHub) — disclosed in the README; opt out via the
// "check_updates" setting. Shows a dismissible banner when a newer release exists.
export default function UpdateBanner({ enabled }) {
  const [rel, setRel] = useState(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (enabled === false || !REPO) return;
    let alive = true;
    fetch(`https://api.github.com/repos/${REPO}/releases/latest`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!alive || !d || !d.tag_name) return;
        const remote = String(d.tag_name).replace(/^v/, "");
        if (isNewer(remote, CUR) && localStorage.getItem("dismissedUpdate") !== remote) {
          setRel({ version: remote, url: d.html_url });
        }
      })
      .catch(() => {});
    return () => { alive = false; };
  }, [enabled]);

  if (!rel || dismissed) return null;
  const dismiss = () => {
    localStorage.setItem("dismissedUpdate", rel.version);
    setDismissed(true);
  };

  return (
    <div className="mb-4 flex items-center gap-3 rounded-xl border border-sky-500/20 bg-sky-500/10 px-4 py-2.5 text-sm text-sky-200">
      <span>A newer version (v{rel.version}) is available — you have v{CUR}.</span>
      <a href={rel.url} target="_blank" rel="noreferrer"
        className="rounded-md bg-sky-600 px-2.5 py-1 text-xs font-semibold text-neutral-50 hover:bg-sky-500">
        Download
      </a>
      <button onClick={dismiss} className="ml-auto text-sky-300/70 hover:text-sky-100" aria-label="Dismiss">
        ✕
      </button>
    </div>
  );
}
