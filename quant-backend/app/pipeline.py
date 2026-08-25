import asyncio
import threading
import time
from datetime import date

from app import db, factors, gates, risk, scoring, trendlyne_client, upstox_client
from app.config import FUNDAMENTALS_DAILY_QUOTA, NIFTY_500_INDEX_SYMBOL
from app.watchlist import ensure_watchlist_seeded, get_watchlist_limit

# threading.Event (not asyncio.Event) because _ingest_prices runs in a worker
# thread via asyncio.to_thread — this needs to be checkable safely from both
# that thread and the main event loop. Single-user app, so one global flag
# is enough; no per-scan tracking needed.
_cancel_event = threading.Event()


def request_cancel():
    _cancel_event.set()


def _is_cancelled() -> bool:
    return _cancel_event.is_set()


def _ingest_prices(client, watchlist_rows) -> list[str]:
    """Blocking calls — invoked via asyncio.to_thread so the event loop
    isn't blocked for the time a full-universe pull can take. `client` is a
    bare access_token string — Upstox has no SDK object, every call here is
    a plain `requests` call with a Bearer header."""
    errors = []

    nifty_key = upstox_client.resolve_nifty500_index_key()
    if nifty_key:
        try:
            upstox_client.fetch_incremental_history(client, NIFTY_500_INDEX_SYMBOL, nifty_key)
        except Exception as e:
            errors.append(f"Upstox: {NIFTY_500_INDEX_SYMBOL}: {e}")
    else:
        errors.append(f"Upstox: {NIFTY_500_INDEX_SYMBOL}: instrument key not found")

    for row in watchlist_rows:
        if _is_cancelled():
            errors.append("Upstox: price ingestion stopped — cancelled by user")
            break
        symbol = row["symbol"]
        key = row["upstox_instrument_key"]
        if key is None or row["company_name"] is None:
            # also backfills company_name for symbols resolved before that
            # column existed — no extra API call, the instrument list is
            # cached in-process for the whole scan either way.
            key = upstox_client.resolve_instrument_key(symbol)
        if key is None:
            errors.append(f"Upstox: {symbol}: instrument key not found")
            continue
        try:
            upstox_client.fetch_incremental_history(client, symbol, key)
        except Exception as e:
            errors.append(f"Upstox: {symbol}: {e}")
    return errors


_FUNDAMENTALS_CONCURRENCY = 20  # live-tested clean at 20 (0 errors); 40 and 80 both failed badly (42.5%, 70%)


async def _refresh_fundamentals(watchlist_rows) -> list[str]:
    """Caps how many symbols get a fresh Trendlyne pull per scan, so a first
    run (or any day with a big batch of stale symbols) can't burn the daily
    quota in one call — see trendlyne_client.CALLS_PER_SYMBOL_REFRESH.
    Leftover stale symbols just get picked up on a later scan.

    Processes the capped set in concurrent batches of _FUNDAMENTALS_CONCURRENCY
    rather than one symbol at a time. The cap is applied by slicing the stale
    list BEFORE dispatching, so it still counts every attempted symbol (not
    just successes) against the budget."""
    errors = []
    max_refreshes = FUNDAMENTALS_DAILY_QUOTA // trendlyne_client.CALLS_PER_SYMBOL_REFRESH
    stale_rows = [row for row in watchlist_rows if trendlyne_client.is_stale(row["symbol"])]
    to_process = stale_rows[:max_refreshes]

    async with trendlyne_client.open_session() as session:
        for i in range(0, len(to_process), _FUNDAMENTALS_CONCURRENCY):
            if _is_cancelled():
                errors.append("Trendlyne: fundamentals refresh stopped — cancelled by user")
                break
            batch = to_process[i:i + _FUNDAMENTALS_CONCURRENCY]
            tasks = [
                trendlyne_client.refresh_if_stale(session, row["symbol"], row["company_name"])
                for row in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for row, result in zip(batch, results):
                if isinstance(result, Exception):
                    errors.append(f"Trendlyne: {row['symbol']}: {result}")
    return errors


def _compute_row(symbol: str, sector: str, price_df, nifty_df, today: str) -> dict | None:
    if price_df.empty:
        return None

    technical = factors.compute_technical_indicators(price_df)
    momentum = factors.compute_momentum_block(price_df, nifty_df)

    fundamentals_row = db.get_latest_fundamentals(symbol)
    fundamentals = dict(fundamentals_row) if fundamentals_row else None
    earnings = factors.compute_earnings_block(fundamentals)

    gate_passed, gate_reasons = gates.apply_gates(price_df, fundamentals, sector)
    entry_trigger = risk.check_entry_trigger(price_df)
    risk_levels = risk.compute_risk_levels(price_df, technical.get("atr_14"))

    return {
        "symbol": symbol,
        "sector": sector,
        "date": today,
        "close_price": float(price_df["close"].iloc[-1]),
        **technical,
        **momentum,
        **earnings,
        "piotroski_score": fundamentals.get("piotroski_score") if fundamentals else None,
        "roe": fundamentals.get("roe") if fundamentals else None,
        "roce": fundamentals.get("roce") if fundamentals else None,
        "debt_to_equity": fundamentals.get("debt_to_equity") if fundamentals else None,
        "gate_passed": gate_passed,
        "gate_reasons": "; ".join(gate_reasons),
        "entry_trigger_today": entry_trigger,
        **risk_levels,
    }


_FACTOR_DAILY_COLUMNS = [
    "symbol", "date", "close_price",
    "momentum_12_1", "dist_from_52w_high", "rel_strength_nifty",
    "rsi_14", "macd", "macd_signal", "adx_14", "atr_14", "bb_upper", "bb_lower",
    "piotroski_score", "earnings_surprise_pct", "roe", "roce", "debt_to_equity",
    "momentum_z", "earnings_z", "quality_z", "technical_z", "composite_score", "rank",
    "gate_passed", "gate_reasons", "entry_trigger_today",
    "entry_price", "stop_loss", "target", "reward_risk",
]


async def run_scan(limit: int | None = None) -> dict:
    _cancel_event.clear()  # fresh scan — clear any stale flag from a previous cancelled run
    timing: dict[str, float] = {}
    t0 = time.monotonic()

    db.init_db()
    ensure_watchlist_seeded(limit)
    effective_limit = limit if limit is not None else get_watchlist_limit()
    watchlist_rows = db.get_watchlist()
    timing["setup"] = time.monotonic() - t0

    if not upstox_client.is_authenticated():
        return {"status": "auth_required"}
    client = upstox_client.get_client()

    t1 = time.monotonic()
    price_errors = await asyncio.to_thread(_ingest_prices, client, watchlist_rows)
    timing["price_ingestion"] = time.monotonic() - t1

    if _is_cancelled():
        # Whatever prices/fundamentals were already fetched this run are
        # still persisted (each symbol commits as it completes) — only the
        # ranked report for THIS scan is skipped, nothing already saved is lost.
        return {"status": "cancelled", "errors": price_errors, "timing": timing}

    # re-fetch: _ingest_prices may have just backfilled company_name via
    # resolve_instrument_key, and the fundamentals queries need it.
    watchlist_rows = db.get_watchlist()

    t2 = time.monotonic()
    fundamentals_errors = await _refresh_fundamentals(watchlist_rows)
    timing["fundamentals_refresh"] = time.monotonic() - t2

    if _is_cancelled():
        return {
            "status": "cancelled",
            "errors": price_errors + fundamentals_errors,
            "timing": timing,
        }

    nifty_df = db.get_price_df(NIFTY_500_INDEX_SYMBOL)
    today = date.today().isoformat()

    t3 = time.monotonic()
    raw_rows = []
    for row in watchlist_rows:
        price_df = db.get_price_df(row["symbol"])
        computed = _compute_row(row["symbol"], row["sector"], price_df, nifty_df, today)
        if computed:
            raw_rows.append(computed)
    timing["factor_computation"] = time.monotonic() - t3

    if not raw_rows:
        return {
            "status": "no_data", "date": today,
            "errors": price_errors + fundamentals_errors,
            "timing": timing,
        }

    t4 = time.monotonic()
    scores = scoring.compute_composite_scores(raw_rows)
    for r in raw_rows:
        r.update(scores[r["symbol"]])
    timing["scoring"] = time.monotonic() - t4

    persist_rows = [{col: r.get(col) for col in _FACTOR_DAILY_COLUMNS} for r in raw_rows]
    for r in persist_rows:
        r["gate_passed"] = int(r["gate_passed"]) if r["gate_passed"] is not None else None
        r["entry_trigger_today"] = (
            int(r["entry_trigger_today"]) if r["entry_trigger_today"] is not None else None
        )

    t5 = time.monotonic()
    all_errors = price_errors + fundamentals_errors
    gates_passed = sum(1 for r in persist_rows if r["gate_passed"])
    scan_run_id = db.create_scan_run(today, len(persist_rows), gates_passed, all_errors, effective_limit)
    db.save_factor_rows(scan_run_id, persist_rows)

    # Only log gate-passed AND triggered stocks — a trigger on a gate-failed
    # stock (e.g. fails the Piotroski quality floor) isn't a buy signal, it's
    # just a technical event on a stock the gates already excluded.
    #
    # 30-day cooldown: a stock whose trigger condition stays true for several
    # days in a row would otherwise get logged as a "new" entry every single
    # day (each is a distinct (symbol, trigger_date) row). Treat it as
    # still-held rather than a fresh buy signal until 30 days have passed
    # since its last logged entry.
    _TRIGGER_COOLDOWN_DAYS = 30
    last_trigger_dates = db.get_last_trigger_dates()
    today_date = date.fromisoformat(today)

    def _past_cooldown(symbol: str) -> bool:
        last = last_trigger_dates.get(symbol)
        return last is None or (today_date - date.fromisoformat(last)).days > _TRIGGER_COOLDOWN_DAYS

    triggered = {
        r["symbol"]: r["entry_price"] for r in persist_rows
        if r["entry_trigger_today"] and r["gate_passed"] and r["entry_price"] is not None
        and _past_cooldown(r["symbol"])
    }
    db.record_triggers(scan_run_id, today, triggered)
    timing["persistence"] = time.monotonic() - t5
    timing["total"] = time.monotonic() - t0

    scan_run = db.get_scan_run(scan_run_id)
    return {
        "status": "ok",
        "date": today,
        "scan_timestamp_ist": scan_run["scan_timestamp_ist"] if scan_run else None,
        "results": db.get_run_results(scan_run_id),
        "errors": all_errors,
        "timing": timing,
    }
