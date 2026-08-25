import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Long-lived (1yr) read-only Analytics token from Upstox's developer
# dashboard — covers Market Data + Streaming, which is all this app ever
# calls. This fork only runs off this token; there is no OAuth login flow.
UPSTOX_ACCESS_TOKEN = os.environ.get("UPSTOX_ACCESS_TOKEN", "").strip() or None

TRENDLYNE_MCP_URL = os.environ.get("TRENDLYNE_MCP_URL", "")
TRENDLYNE_API_KEY = os.environ.get("TRENDLYNE_API_KEY", "")

NIFTY500_SEED_PATH = BASE_DIR / "data" / "nifty500.json"

# Turso — hosted SQLite-compatible database, connected to directly (no local
# file/cache — see db.py's module docstring for why). Required; there's no
# local-SQLite-only fallback in this fork.
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

# plan.md §4.2 recommends a weekly cadence to respect the Trendlyne MCP quota.
FUNDAMENTALS_MAX_AGE_DAYS = int(os.environ.get("FUNDAMENTALS_MAX_AGE_DAYS", "10"))

# Confirmed live: a full fundamentals refresh costs 4 MCP calls/symbol. Caps
# how many calls one scan can spend on fundamentals refreshes, so one scan
# can never exhaust the day's quota on its own.
FUNDAMENTALS_DAILY_QUOTA = int(os.environ.get("FUNDAMENTALS_DAILY_QUOTA", "800"))

# plan.md §6 — history needed for 252-day momentum/52w-high + 200-day SMA gate.
PRICE_HISTORY_LOOKBACK_DAYS = 400

NIFTY_500_INDEX_SYMBOL = "NIFTY 500"

# How many symbols (from the front of data/nifty500.json, roughly market-cap
# order) are actually scanned.
WATCHLIST_LIMIT = int(os.environ.get("WATCHLIST_LIMIT", "50"))
