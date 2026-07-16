"""User settings, persisted as JSON in the user-data directory.

No SQLite involvement. Values are validated/clamped on every read and write so
a hand-edited or stale file can never put the app into a bad state.
"""
import json
from pathlib import Path

TAB_KEYS = ["overview", "sleep", "training", "activities", "trends", "coach"]

DEFAULTS = {
    "units": "metric",            # "metric" | "imperial"
    "sync_interval_minutes": 30,  # clamped 5..240
    "baseline_window_days": 30,   # Recovery baseline window, clamped 7..60
    "hidden_tabs": [],            # subset of TAB_KEYS the user chose to hide
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
}


def _clamp(v, lo, hi, default):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def _validate(raw):
    s = dict(DEFAULTS)
    s.update({k: v for k, v in (raw or {}).items() if k in DEFAULTS})
    s["units"] = s["units"] if s["units"] in ("metric", "imperial") else "metric"
    s["sync_interval_minutes"] = _clamp(s["sync_interval_minutes"], 5, 240, 30)
    s["baseline_window_days"] = _clamp(s["baseline_window_days"], 7, 60, 30)
    tabs = s["hidden_tabs"] if isinstance(s["hidden_tabs"], list) else []
    s["hidden_tabs"] = [t for t in tabs if t in TAB_KEYS]
    s["theme"] = s["theme"] if s["theme"] in ("dark", "light") else "dark"
    s["check_updates"] = bool(s["check_updates"])
    s["phone_access"] = bool(s["phone_access"])
    s["access_pin"] = str(s.get("access_pin") or "")
    s["start_at_login"] = bool(s["start_at_login"])
    s["date_style"] = s["date_style"] if s["date_style"] in ("month", "number") else "month"
    s["coach_enabled"] = bool(s["coach_enabled"])
    s["anthropic_api_key"] = str(s.get("anthropic_api_key") or "")
    s["coach_model"] = str(s.get("coach_model") or "claude-opus-4-8")
    return s


def load_settings(path):
    p = Path(path)
    raw = {}
    if p.is_file():
        try:
            raw = json.loads(p.read_text())
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
