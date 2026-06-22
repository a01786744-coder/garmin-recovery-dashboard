"""User settings, persisted as JSON in the user-data directory.

No SQLite involvement. Values are validated/clamped on every read and write so
a hand-edited or stale file can never put the app into a bad state.
"""
import json
from pathlib import Path

TAB_KEYS = ["overview", "sleep", "training", "activities", "trends"]

DEFAULTS = {
    "units": "metric",            # "metric" | "imperial"
    "sync_interval_minutes": 30,  # clamped 5..240
    "baseline_window_days": 30,   # Recovery baseline window, clamped 7..60
    "hidden_tabs": [],            # subset of TAB_KEYS the user chose to hide
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
