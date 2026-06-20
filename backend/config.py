"""Central config: paths, constants, and credentials loaded from .env.

Credential values are read from the environment and never logged.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "dashboard.db"
TOKENSTORE_DIR = DATA_DIR / ".garth"

GARMIN_EMAIL = os.environ.get("GARMIN_EMAIL")
GARMIN_PASSWORD = os.environ.get("GARMIN_PASSWORD")

SYNC_INTERVAL_SECONDS = 1800   # 30 minutes
BASELINE_WINDOW_DAYS = 30
BASELINE_MIN_DAYS = 14

DATA_DIR.mkdir(exist_ok=True)
