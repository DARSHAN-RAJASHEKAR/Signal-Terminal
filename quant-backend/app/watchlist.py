import json

from app.config import (
    NIFTY500_SEED_PATH,
    NIFTYMICROCAP250_SEED_PATH,
    NIFTYSMALLCAP250_SEED_PATH,
    WATCHLIST_LIMIT,
)
from app.db import get_setting, set_active_symbols, set_setting, upsert_watchlist

# Numeric selections slice the Nifty 500 seed file (seed-file order ~=
# market-cap order). The two fixed-universe selections below load an
# entirely different seed file instead, in full — those files are
# alphabetically ordered (NSE's published constituent lists), not
# market-cap ranked, so there's no meaningful "Top 50 of Smallcap 250"
# slice; picking one always means the whole 250.
ALLOWED_WATCHLIST_LIMITS = [10, 50, 100, 200, 500]
WATCHLIST_SOURCE_LABELS = {
    "smallcap250": "Smallcap 250",
    "microcap250": "Microcap 250",
}
_SOURCE_SEED_PATHS = {
    "smallcap250": NIFTYSMALLCAP250_SEED_PATH,
    "microcap250": NIFTYMICROCAP250_SEED_PATH,
}
_SETTING_KEY = "watchlist_limit"


def is_valid_selection(selection: str) -> bool:
    return selection in _SOURCE_SEED_PATHS or (selection.isdigit() and int(selection) in ALLOWED_WATCHLIST_LIMITS)


def watchlist_selection_options() -> list[tuple[str, str]]:
    """(value, label) pairs in dropdown order — numeric Top-N sizes first,
    then the fixed alternate universes."""
    options = [(str(n), f"Top {n}") for n in ALLOWED_WATCHLIST_LIMITS]
    options += [(key, label) for key, label in WATCHLIST_SOURCE_LABELS.items()]
    return options


def get_watchlist_selection() -> str:
    """Persisted choice (set via the Scan selector) takes precedence over
    the .env default, so it survives across restarts and page loads."""
    stored = get_setting(_SETTING_KEY)
    if stored and is_valid_selection(stored):
        return stored
    return str(WATCHLIST_LIMIT)


def load_seed_watchlist(selection: str | None = None) -> list[dict]:
    path = _SOURCE_SEED_PATHS.get(selection, NIFTY500_SEED_PATH)
    with open(path) as f:
        return json.load(f)


def ensure_watchlist_seeded(selection: str | None = None):
    """Idempotent: upsert the full seed list for `selection`'s source, then
    activate the right subset — every symbol for a fixed alternate universe
    (smallcap250/microcap250), or the first N for a numeric Nifty Top-N
    selection. Safe to call every scan — cheap local DB writes, no network
    calls. Persists `selection` as the new default for the next page load /
    scan when explicitly provided."""
    if selection is not None:
        if not is_valid_selection(selection):
            raise ValueError(f"selection must be one of {watchlist_selection_options()}, got {selection}")
        set_setting(_SETTING_KEY, selection)
    else:
        selection = get_watchlist_selection()

    rows = load_seed_watchlist(selection)
    ranked_rows = [{**r, "rank": i + 1} for i, r in enumerate(rows)]
    upsert_watchlist(ranked_rows)
    if selection in _SOURCE_SEED_PATHS:
        limited_symbols = [r["symbol"] for r in rows]
    else:
        limited_symbols = [r["symbol"] for r in rows[:int(selection)]]
    set_active_symbols(limited_symbols)
    return rows
