"""User settings, persisted as JSON in the user-data directory.

No SQLite involvement. Values are validated/clamped on every read and write so
a hand-edited or stale file can never put the app into a bad state.
"""
import json
from pathlib import Path

TAB_KEYS = ["overview", "sleep", "training", "activities", "trends", "coach"]

# v4.2 customization caps (defensive: a hand-edited or malicious file can't
# balloon the layout).
MAX_CUSTOM_TABS = 10
MAX_WIDGETS_PER_TAB = 30
GRID_COLS = 4                 # react-grid-layout column count
_NAME_MAX = 40
_ICON_MAX = 8                 # an emoji can be several code points

DEFAULTS = {
    "units": "metric",            # "metric" | "imperial"
    "sync_interval_minutes": 30,  # clamped 5..240
    "baseline_window_days": 30,   # Recovery baseline window, clamped 7..60
    "hidden_tabs": [],            # tab keys the user chose to hide (built-in or custom)
    "theme": "dark",              # "dark" | "light"
    "check_updates": True,        # check GitHub for newer releases on launch
    "phone_access": False,        # bind to LAN/Tailscale so a phone can reach it
    "access_pin": "",             # required for any non-loopback API access
    "start_at_login": False,      # Electron login item (applied by the shell)
    "date_style": "month",        # chart dates: "month" (Jul 4) | "number" (07-04)
    # v4.0 AI coach. The API key is stored ONLY here (like the PIN): local
    # file, never logged (RedactingFilter also scrubs token-shaped strings),
    # never sent anywhere except to Anthropic's API over TLS.
    "coach_enabled": False,
    "anthropic_api_key": "",
    "coach_model": "claude-sonnet-5",
    # v4.2 customization. tab_order lists every tab (built-in keys + custom-tab
    # ids) in display order; custom_tabs holds user-composed grids. Widget-id
    # validity is enforced by the frontend catalog (backend keeps any string so
    # the two never fall out of sync).
    "tab_order": [],
    "custom_tabs": [],
}


def _clamp(v, lo, hi, default):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def _validate_custom_tabs(raw):
    """Sanitize the custom_tabs list: keep well-formed tabs with a non-empty id,
    cap counts, clamp grid coordinates, and trim names/icons. Returns the cleaned
    list plus the set of valid custom-tab ids (for tab_order/hidden_tabs)."""
    out, ids, seen = [], set(), set()
    for t in (raw if isinstance(raw, list) else [])[:MAX_CUSTOM_TABS]:
        if not isinstance(t, dict):
            continue
        tid = str(t.get("id") or "").strip()
        if not tid or tid in seen or tid in TAB_KEYS:
            continue
        seen.add(tid)
        layout = []
        for w in (t.get("layout") if isinstance(t.get("layout"), list) else [])[:MAX_WIDGETS_PER_TAB]:
            if not isinstance(w, dict) or not str(w.get("i") or "").strip():
                continue
            layout.append({
                "i": str(w["i"]).strip(),
                "x": _clamp(w.get("x", 0), 0, GRID_COLS - 1, 0),
                "y": _clamp(w.get("y", 0), 0, 9999, 0),
                "w": _clamp(w.get("w", 1), 1, GRID_COLS, 1),
                "h": _clamp(w.get("h", 2), 1, 20, 2),
            })
        out.append({
            "id": tid,
            "name": (str(t.get("name") or "Custom").strip() or "Custom")[:_NAME_MAX],
            "icon": str(t.get("icon") or "▦")[:_ICON_MAX],
            "layout": layout,
        })
        ids.add(tid)
    return out, ids


def _validate(raw):
    s = dict(DEFAULTS)
    s.update({k: v for k, v in (raw or {}).items() if k in DEFAULTS})
    s["units"] = s["units"] if s["units"] in ("metric", "imperial") else "metric"
    s["sync_interval_minutes"] = _clamp(s["sync_interval_minutes"], 5, 240, 30)
    s["baseline_window_days"] = _clamp(s["baseline_window_days"], 7, 60, 30)
    s["theme"] = s["theme"] if s["theme"] in ("dark", "light") else "dark"
    s["check_updates"] = bool(s["check_updates"])
    s["phone_access"] = bool(s["phone_access"])
    s["access_pin"] = str(s.get("access_pin") or "")
    s["start_at_login"] = bool(s["start_at_login"])
    s["date_style"] = s["date_style"] if s["date_style"] in ("month", "number") else "month"
    s["coach_enabled"] = bool(s["coach_enabled"])
    s["anthropic_api_key"] = str(s.get("anthropic_api_key") or "")
    s["coach_model"] = str(s.get("coach_model") or "claude-sonnet-5")
    # v4.2: custom tabs first so tab_order/hidden_tabs can reference their ids.
    s["custom_tabs"], custom_ids = _validate_custom_tabs(s["custom_tabs"])
    valid_tab_ids = set(TAB_KEYS) | custom_ids
    order = s["tab_order"] if isinstance(s["tab_order"], list) else []
    seen = set()
    s["tab_order"] = [t for t in map(str, order)
                      if t in valid_tab_ids and not (t in seen or seen.add(t))]
    tabs = s["hidden_tabs"] if isinstance(s["hidden_tabs"], list) else []
    s["hidden_tabs"] = [t for t in map(str, tabs) if t in valid_tab_ids]
    return s


def load_settings(path):
    p = Path(path)
    raw = {}
    if p.is_file():
        try:
            # utf-8-sig tolerates a leading BOM: a settings file hand-edited or
            # rewritten by an editor/PowerShell that adds one must never fail to
            # parse and fall back to defaults — that would wipe real values
            # (API key, PIN, phone access) on the next save.
            raw = json.loads(p.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            raw = {}
    return _validate(raw)


def save_settings(path, partial):
    """Merge `partial` over the current settings, validate, persist, return."""
    merged = load_settings(path)
    merged.update({k: v for k, v in (partial or {}).items() if k in DEFAULTS})
    merged = _validate(merged)
    Path(path).write_text(json.dumps(merged, indent=2))
    return merged
