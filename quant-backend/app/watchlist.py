import json

from app.config import NIFTY500_SEED_PATH, WATCHLIST_LIMIT
from app.db import get_setting, set_active_symbols, set_setting, upsert_watchlist

ALLOWED_WATCHLIST_LIMITS = [10, 50, 100, 200, 500]
_SETTING_KEY = "watchlist_limit"


def load_seed_watchlist() -> list[dict]:
    with open(NIFTY500_SEED_PATH) as f:
        return json.load(f)


def get_watchlist_limit() -> int:
    """Persisted choice (set via the Scan Top N selector) takes precedence
    over the .env default, so it survives across restarts and page loads."""
    stored = get_setting(_SETTING_KEY)
    if stored and stored.isdigit() and int(stored) in ALLOWED_WATCHLIST_LIMITS:
        return int(stored)
    return WATCHLIST_LIMIT


def ensure_watchlist_seeded(limit: int | None = None):
    """Idempotent: upsert the full seed list, then activate only the first
    `limit` symbols (seed-file order ≈ market-cap order). Safe to call every
    scan — cheap local DB writes, no network calls. Persists `limit` as the
    new default for the next page load / scan when explicitly provided."""
    if limit is not None:
        if limit not in ALLOWED_WATCHLIST_LIMITS:
            raise ValueError(f"limit must be one of {ALLOWED_WATCHLIST_LIMITS}, got {limit}")
        set_setting(_SETTING_KEY, str(limit))
    else:
        limit = get_watchlist_limit()

    rows = load_seed_watchlist()
    ranked_rows = [{**r, "rank": i + 1} for i, r in enumerate(rows)]
    upsert_watchlist(ranked_rows)
    limited_symbols = [r["symbol"] for r in rows[:limit]]
    set_active_symbols(limited_symbols)
    return rows
