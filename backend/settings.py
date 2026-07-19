"""User settings, persisted as JSON in the user-data directory.

No SQLite involvement. Values are validated/clamped on every read and write so
a hand-edited or stale file can never put the app into a bad state.
"""
import json
from pathlib import Path

# Every built-in tab key. Must match the frontend TABS list — a key missing
# here gets silently stripped from tab_order/hidden_tabs on save (the Today
# tab was absent until v4.2.1 and kept jumping to the end of the bar).
TAB_KEYS = ["overview", "today", "sleep", "training", "activities", "trends",
            "records", "coach"]

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
    # --- v4.3 settings redesign ---
    # General
    "accent_color": "#22c55e",    # hex; recolors the app's accent
    "density": "comfortable",     # "comfortable" | "compact"
    "default_tab": "",            # tab key to open on launch ("" = first visible)
    "week_start": "mon",          # "mon" | "sun"
    "weather_units": "c",         # activity weather display: "c" | "f"
    "clock": "24",                # "24" | "12"
    # Recovery & metrics
    "hrv_weight": 0.7,            # HRV share of the recovery blend (RHR = 1-this)
    "recovery_green": 67,         # score >= this -> green band
    "recovery_amber": 34,         # score >= this -> amber, else red
    "sleep_goal_min": 0,          # nightly sleep goal, minutes (0 = use Garmin need)
    "max_hr": 0,                  # for zone accuracy (0 = derive/none)
    # Sync
    "sync_on_launch": True,
    "morning_notification": True,
    "sync_paused": False,
    # Coach
    "coach_tone": "balanced",     # balanced|concise|detailed|tough|encouraging
    "coach_auto_brief": False,    # generate the morning brief automatically on sync
    "coach_warmup_default_s": 600,
    "coach_target_pref": "auto",  # "auto" | "pace" | "hr"
    "coach_budget_reminder": 0,   # USD/month soft reminder (0 = off)
}

_THEMES = ("dark", "light", "midnight", "slate", "contrast")


def _clamp(v, lo, hi, default):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def _clampf(v, lo, hi, default):
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return default


def _one_of(v, choices, default):
    return v if v in choices else default


import re as _re
_HEX = _re.compile(r"^#[0-9a-fA-F]{6}$")


def _hex_color(v, default):
    v = str(v or "")
    return v if _HEX.match(v) else default


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
    s["theme"] = _one_of(s["theme"], _THEMES, "dark")
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
    # --- v4.3 ---
    s["accent_color"] = _hex_color(s["accent_color"], "#22c55e")
    s["density"] = _one_of(s["density"], ("comfortable", "compact"), "comfortable")
    s["default_tab"] = str(s.get("default_tab") or "")   # frontend resolves validity
    s["week_start"] = _one_of(s["week_start"], ("mon", "sun"), "mon")
    s["weather_units"] = _one_of(s["weather_units"], ("c", "f"), "c")
    s["clock"] = _one_of(str(s["clock"]), ("24", "12"), "24")
    s["hrv_weight"] = round(_clampf(s["hrv_weight"], 0.0, 1.0, 0.7), 2)
    # Bands: green strictly above amber, both in 1..99.
    green = _clamp(s["recovery_green"], 2, 99, 67)
    amber = _clamp(s["recovery_amber"], 1, green - 1, min(34, green - 1))
    s["recovery_green"], s["recovery_amber"] = green, amber
    s["sleep_goal_min"] = _clamp(s["sleep_goal_min"], 0, 720, 0)
    s["max_hr"] = _clamp(s["max_hr"], 0, 230, 0)
    s["sync_on_launch"] = bool(s["sync_on_launch"])
    s["sync_paused"] = bool(s["sync_paused"])
    s["morning_notification"] = bool(s["morning_notification"])
    s["coach_tone"] = _one_of(s["coach_tone"],
                              ("balanced", "concise", "detailed", "tough", "encouraging"),
                              "balanced")
    s["coach_auto_brief"] = bool(s["coach_auto_brief"])
    s["coach_warmup_default_s"] = _clamp(s["coach_warmup_default_s"], 0, 1800, 600)
    s["coach_target_pref"] = _one_of(s["coach_target_pref"], ("auto", "pace", "hr"), "auto")
    s["coach_budget_reminder"] = _clamp(s["coach_budget_reminder"], 0, 1000, 0)
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
