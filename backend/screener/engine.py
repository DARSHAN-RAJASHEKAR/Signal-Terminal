"""Snapshot engine for the Stocks Screener.

One "snapshot" = every stock in the universe with its live metrics. The
browser downloads the whole snapshot (~750 rows) and does all filtering and
sorting client-side, so changing a filter never waits on the network.

Refreshing is demand-driven: a request for a stale snapshot kicks off a
background refresh and the previous snapshot keeps being served meanwhile.
Nothing is fetched while nobody has the screener open.

Gunicorn runs several worker processes, each with its own memory. To avoid
every worker hammering Yahoo, the snapshot, progress and daily cache live in
files under SCREENER_CACHE_DIR, and an flock makes sure only one process
refreshes at a time; the others just pick up the file it writes.

Data per symbol (Yahoo chart API, same source BuyTheDip uses):
  * 1y of daily bars    — once per session, condensed into indicators.build_daily_state
  * today's 5-min bars  — every refresh: live price, intraday moves, volume
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests

from . import indicators as ind

IST = timezone(timedelta(hours=5, minutes=30))
UNIVERSE_PATH = Path(__file__).resolve().parent / "data" / "universe.json"
CACHE_DIR = Path(os.environ.get("SCREENER_CACHE_DIR", tempfile.gettempdir())) / "screener-cache"
SNAPSHOT_FILE = CACHE_DIR / "snapshot.json"
DAILY_FILE = CACHE_DIR / "daily_state.json"
PROGRESS_FILE = CACHE_DIR / "progress.json"
LOCK_FILE = CACHE_DIR / "refresh.lock"

REFRESH_OPEN_S = int(os.environ.get("SCREENER_REFRESH_SECONDS", "60"))
REFRESH_CLOSED_S = 3600
WORKERS = int(os.environ.get("SCREENER_WORKERS", "12"))
# A refresh whose progress file hasn't moved for this long is considered dead
# (e.g. the worker was killed mid-refresh) and may be retried.
STALL_S = 180
# After a failed refresh, wait this long before trying again.
ERROR_BACKOFF_S = 60

_YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{}"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

_universe: dict | None = None
_snapshot: dict | None = None
_snapshot_mtime = 0.0
_refresh_thread: threading.Thread | None = None
_mem_lock = threading.Lock()


# ── Market clock ─────────────────────────────────────────────────────────────

def market_open(now: datetime | None = None) -> bool:
    """NSE cash session, Mon–Fri 09:15–15:30 IST. Exchange holidays aren't
    modelled — on a holiday this only means a shorter refresh interval."""
    now = (now or datetime.now(IST)).astimezone(IST)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 + 15 <= minutes <= 15 * 60 + 30


def refresh_interval() -> int:
    return REFRESH_OPEN_S if market_open() else REFRESH_CLOSED_S


# ── Files ────────────────────────────────────────────────────────────────────

def _read_json(path: Path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_json_atomic(path: Path, data) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=CACHE_DIR, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    os.replace(tmp, path)


def load_universe() -> dict:
    global _universe
    if _universe is None:
        with open(UNIVERSE_PATH) as f:
            _universe = json.load(f)
    return _universe


# ── Yahoo fetchers ───────────────────────────────────────────────────────────

def _chart(symbol: str, rng: str, interval: str) -> dict | None:
    url = _YAHOO_CHART.format(quote(f"{symbol}.NS", safe=""))
    for attempt in range(2):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=12,
                             params={"range": rng, "interval": interval})
            if r.status_code == 429 and attempt == 0:
                time.sleep(1.5)
                continue
            if r.status_code != 200:
                return None
            res = (r.json().get("chart") or {}).get("result")
            return res[0] if res else None
        except (requests.RequestException, ValueError):
            if attempt:
                return None
    return None


def _ist_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, IST).date().isoformat()


def fetch_intraday(symbol: str) -> dict | None:
    res = _chart(symbol, "1d", "5m")
    if not res or not res.get("timestamp"):
        return None
    meta = res.get("meta", {})
    q = (res.get("indicators", {}).get("quote") or [{}])[0]
    bars = [
        (ts, c, v)
        for ts, c, v in zip(res["timestamp"], q.get("close", []), q.get("volume", []))
        if c is not None
    ]
    if not bars:
        return None
    highs = [h for h in q.get("high", []) if h is not None]
    lows = [l for l in q.get("low", []) if l is not None]
    price = meta.get("regularMarketPrice") or bars[-1][1]
    day_vol = meta.get("regularMarketVolume")
    if not day_vol:
        day_vol = sum(int(v or 0) for _, _, v in bars)
    return {
        "session_date": _ist_date(bars[-1][0]),
        "price": float(price),
        "day_high": max([meta.get("regularMarketDayHigh") or 0] + highs) or None,
        "day_low": min([x for x in [meta.get("regularMarketDayLow")] + lows if x] or [None]),
        "day_vol": int(day_vol),
        "bars": bars,
    }


# Cached in place of a daily state when the history fetched fine but is too
# short for the indicators (recent listings). Unlike a failed fetch, that
# won't change within the session, so it isn't refetched every refresh.
INSUFFICIENT = "insufficient"


def fetch_daily_state(symbol: str, session_date: str) -> dict | str | None:
    """Daily state, INSUFFICIENT for too-short history, or None if the
    fetch itself failed (retried next refresh)."""
    res = _chart(symbol, "1y", "1d")
    if not res or not res.get("timestamp"):
        return None
    q = (res.get("indicators", {}).get("quote") or [{}])[0]
    dates = [_ist_date(ts) for ts in res["timestamp"]]
    state = ind.build_daily_state(dates, q.get("open", []), q.get("high", []), q.get("low", []),
                                  q.get("close", []), q.get("volume", []), session_date)
    return state if state is not None else INSUFFICIENT


# ── Row assembly ─────────────────────────────────────────────────────────────

def _r(x, nd=2):
    return None if x is None else round(x, nd)


def build_row(stock: dict, intra: dict, daily: dict | None, now_ts: int) -> dict:
    price = intra["price"]
    bars = intra["bars"]
    row = {
        "s": stock["symbol"],
        "n": stock["name"],
        "sec": stock["sector"],
        "idx": stock["indices"],
        "p": _r(price),
        "vol": intra["day_vol"],
        "vol5m": ind.last_bar_volume(bars, now_ts),
        "ch5m": _r(ind.intraday_change(bars, price, now_ts, 5)),
        "ch15m": _r(ind.intraday_change(bars, price, now_ts, 15)),
        "ch1h": _r(ind.intraday_change(bars, price, now_ts, 60)),
        "mcap": _r(price * stock["shares"] / 1e7, 0) if stock.get("shares") else None,
        "turnover": round(price * intra["day_vol"]),
    }
    if daily:
        prev = daily["prev_close"]
        hi = max(daily["hi_52w"], intra["day_high"] or price, price)
        lo = min(daily["lo_52w"], intra["day_low"] or price, price)
        piv = ind.classic_pivots(daily["prev_high"], daily["prev_low"], prev)
        rsi = None
        if daily.get("rsi_ag") is not None:
            rsi = ind.rsi_from_state(daily["rsi_ag"], daily["rsi_al"], prev, price)
        macd = sig = cross = None
        if daily.get("macd"):
            macd, sig, _, cross = ind.macd_live(daily["macd"], price)
        avg = daily.get("avg_vol_1w")
        row.update({
            "pc": _r(prev),
            "ch": _r(price - prev),
            "chp": _r(ind.pct(price, prev)),
            "hi52": _r(hi),
            "lo52": _r(lo),
            "avgVol": round(avg) if avg else None,
            "volDiff": _r(ind.pct(intra["day_vol"], avg)) if avg else None,
            "rsi": _r(rsi, 1),
            "macd": _r(macd, 3),
            "macdSig": _r(sig, 3),
            "macdCross": cross,
            "piv": {k: _r(v) for k, v in piv.items()},
            "pivZone": ind.pivot_zone(price, piv),
        })
    return row


# ── Refresh ──────────────────────────────────────────────────────────────────

def _write_progress(done: int, total: int, started: float) -> None:
    _write_json_atomic(PROGRESS_FILE, {"done": done, "total": total,
                                       "started": started, "updated": time.time()})


def _refresh_locked() -> None:
    universe = load_universe()
    stocks = universe["stocks"]
    total = len(stocks)
    started = time.time()
    _write_progress(0, total, started)

    old = _read_json(SNAPSHOT_FILE) or {}
    old_rows = {r["s"]: r for r in old.get("rows", [])}
    daily_cache = _read_json(DAILY_FILE) or {}
    daily_by_session: dict[str, dict] = daily_cache.get("sessions", {})
    now_ts = int(time.time())

    def work(stock):
        intra = fetch_intraday(stock["symbol"])
        if intra is None:
            return stock["symbol"], None, None, None
        session = intra["session_date"]
        states = daily_by_session.get(session, {})
        daily = states.get(stock["symbol"])
        fresh_daily = None
        if daily is None:
            daily = fresh_daily = fetch_daily_state(stock["symbol"], session)
        if daily == INSUFFICIENT:
            daily = None
        return stock["symbol"], session, build_row(stock, intra, daily, now_ts), fresh_daily

    rows, failed, done = [], [], 0
    sessions_seen: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(work, s) for s in stocks]
        for fut in as_completed(futures):
            sym, session, row, fresh_daily = fut.result()
            done += 1
            if row is None:
                failed.append(sym)
                if sym in old_rows:      # keep last known values rather than dropping the stock
                    rows.append({**old_rows[sym], "stale": True})
            else:
                rows.append(row)
                sessions_seen[session] = sessions_seen.get(session, 0) + 1
                if fresh_daily is not None:
                    daily_by_session.setdefault(session, {})[sym] = fresh_daily
            if done % 25 == 0:
                _write_progress(done, total, started)

    # Keep only the current session's daily states; older ones are useless.
    session = max(sessions_seen, key=sessions_seen.get) if sessions_seen else None
    if session:
        _write_json_atomic(DAILY_FILE, {"sessions": {session: daily_by_session.get(session, {})}})

    if not rows:
        _write_progress(done, total, started)
        raise RuntimeError("Market data source returned nothing for every symbol")

    snapshot = {
        "version": int(time.time() * 1000),
        "started": started,
        "as_of": datetime.now(IST).isoformat(timespec="seconds"),
        "session_date": session,
        "market_open": market_open(),
        "universe_size": total,
        "failed": len(failed),
        "duration_s": round(time.time() - started, 1),
        "shares_as_of": universe.get("shares_as_of"),
        "rows": rows,
    }
    _write_json_atomic(SNAPSHOT_FILE, snapshot)
    _write_progress(total, total, started)


def _refresh() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOCK_FILE, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return  # another worker process is already refreshing
        try:
            # Another process may have just finished while we were waiting.
            if not _is_stale(_read_json(SNAPSHOT_FILE)):
                return
            _refresh_locked()
        except Exception as e:  # noqa: BLE001 — surfaced to the client via progress
            _write_json_atomic(PROGRESS_FILE, {"error": str(e), "updated": time.time()})
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _age(snap: dict) -> float:
    # Measured from when the refresh *started*, so a 60s interval means a
    # new snapshot roughly every 60s rather than every 60s + fetch time.
    return time.time() - snap.get("started", snap["version"] / 1000.0)


def _is_stale(snap: dict | None) -> bool:
    if snap is None:
        return True
    # Taken during the session but the market has since closed → one more
    # refresh to capture closing prices instead of waiting the full hour.
    if snap.get("market_open") and not market_open():
        return True
    return _age(snap) >= refresh_interval()


def _refreshing() -> bool:
    prog = _read_json(PROGRESS_FILE)
    if not prog or "error" in prog:
        return False
    return prog["done"] < prog["total"] and time.time() - prog["updated"] < STALL_S


def _ensure_refresh() -> None:
    global _refresh_thread
    with _mem_lock:
        if _refresh_thread and _refresh_thread.is_alive():
            return
        if _refreshing():
            return
        prog = _read_json(PROGRESS_FILE) or {}
        if prog.get("error") and time.time() - prog.get("updated", 0) < ERROR_BACKOFF_S:
            return
        _refresh_thread = threading.Thread(target=_refresh, name="screener-refresh", daemon=True)
        _refresh_thread.start()


def _current_snapshot() -> dict | None:
    global _snapshot, _snapshot_mtime
    try:
        mtime = SNAPSHOT_FILE.stat().st_mtime
    except OSError:
        return _snapshot
    if mtime != _snapshot_mtime:
        snap = _read_json(SNAPSHOT_FILE)
        if snap:
            _snapshot, _snapshot_mtime = snap, mtime
    return _snapshot


def get_snapshot(since: int | None = None) -> dict:
    """Payload for GET /screener/snapshot.

    status: "ready"    — rows included (or `unchanged` if the client's
                         `since` version is still current)
            "warming"  — first build in progress; no rows yet
            "error"    — refresh failed and there's nothing to serve
    """
    snap = _current_snapshot()
    if _is_stale(snap):
        _ensure_refresh()

    prog = _read_json(PROGRESS_FILE) or {}
    meta = {
        "refreshing": _refreshing() or bool(_refresh_thread and _refresh_thread.is_alive()),
        "progress": {"done": prog.get("done", 0), "total": prog.get("total", 0)},
        "refresh_interval_s": refresh_interval(),
        "market_open": market_open(),
    }
    if snap is None:
        if prog.get("error") and not meta["refreshing"]:
            return {"status": "error", "message": prog["error"], **meta}
        return {"status": "warming", **meta}

    head = {k: v for k, v in snap.items() if k != "rows"}
    if since is not None and since == snap["version"]:
        return {"status": "ready", "unchanged": True, **head, **meta}
    return {"status": "ready", **head, **meta, "rows": snap["rows"]}
