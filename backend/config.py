"""Central config: paths, constants, and credentials.

Per-user state (database, auth token store, capability profile, settings, log)
lives in the OS user-data directory in distribution: Electron passes its path
via the GARMIN_DASH_DATA_DIR environment variable when it spawns the backend.
For local development (no env var set) it falls back to the project's data/ dir.

Credential values are read from the environment and never logged.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# .env stays a development convenience for GARMIN_EMAIL/GARMIN_PASSWORD; the
# end-user credential source becomes the in-app login flow in Phase 2.
load_dotenv(PROJECT_ROOT / ".env")


def resolve_data_dir(environ=None, project_root=PROJECT_ROOT):
    """Where per-user state is written. Honors GARMIN_DASH_DATA_DIR (set by the
    Electron shell to the OS user-data dir); otherwise falls back to
    <project_root>/data for development."""
    environ = os.environ if environ is None else environ
    override = environ.get("GARMIN_DASH_DATA_DIR")
    return Path(override) if override else Path(project_root) / "data"


DATA_DIR = resolve_data_dir()
DB_PATH = DATA_DIR / "dashboard.db"
TOKENSTORE_DIR = DATA_DIR / ".garth"
CAPABILITY_PATH = DATA_DIR / "capabilities.json"
SETTINGS_PATH = DATA_DIR / "settings.json"
LOG_PATH = DATA_DIR / "dashboard.log"

GARMIN_EMAIL = os.environ.get("GARMIN_EMAIL")
GARMIN_PASSWORD = os.environ.get("GARMIN_PASSWORD")

SYNC_INTERVAL_SECONDS = 1800   # 30 minutes
BASELINE_WINDOW_DAYS = 30
BASELINE_MIN_DAYS = 14

DATA_DIR.mkdir(parents=True, exist_ok=True)
