"""Dip backtest for BuyTheDip.

Question it answers: "Every past time this stock fell at least W% in a week
AND M% in a month — the same thresholds you just scanned with — what
happened next?"

Definitions mirror the live scanner so the backtest tests the exact signal
the user saw:
  * weekly / monthly change = close vs the last close on or before 7 / 30
    calendar days earlier (the scanner compares against 7 and 30 days ago)
  * a "dip event" is a day where both changes are at or below −W% / −M%
  * after an event, the next one must be ≥ 30 days later — otherwise one
    long slide would be counted as dozens of separate dips
  * forward returns are measured from the event-day close to the first
    close on or after +7 / +30 / +90 days
  * "recovered" = closed back at or above the price from 30 days before the
    dip (the pre-dip level) within 90 days

A baseline over *every* day in the same history is included, so the
result can be judged against simply buying on any random day.
"""

from __future__ import annotations

import time
from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta, timezone
from statistics import median
from threading import Lock
from typing import Optional, Sequence

import requests

HORIZONS = [("1w", 7), ("1m", 30), ("3m", 90)]
WEEK_DAYS, MONTH_DAYS = 7, 30
COOLDOWN_DAYS = 30
RECOVERY_WINDOW_DAYS = 90
ALLOWED_YEARS = (3, 5, 10)

_YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{}"
_BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}
_DAY = 86400


# ── Pure maths ───────────────────────────────────────────────────────────────

def _pct(a: float, b: float) -> float:
    return (a - b) / b * 100.0


def _close_on_or_before(ts: Sequence[int], closes: Sequence[float], t: int) -> Optional[float]:
    i = bisect_right(ts, t) - 1
    return closes[i] if i >= 0 else None


def _index_on_or_after(ts: Sequence[int], t: int) -> Optional[int]:
    i = bisect_left(ts, t)
    return i if i < len(ts) else None


def _stats(values: list[float]) -> Optional[dict]:
    if not values:
        return None
    return {
        "n": len(values),
        "win_rate": round(sum(v > 0 for v in values) / len(values) * 100, 1),
        "avg": round(sum(values) / len(values), 2),
        "median": round(median(values), 2),
        "best": round(max(values), 2),
        "worst": round(min(values), 2),
    }


def run_backtest(ts: Sequence[int], closes: Sequence[float],
                 weekly_threshold: float, monthly_threshold: float) -> dict:
    """ts: ascending unix seconds (one per daily bar); closes aligned to ts."""
    if len(ts) != len(closes):
        raise ValueError("ts and closes must be the same length")

    events = []
    fwd: dict[str, list[float]] = {k: [] for k, _ in HORIZONS}
    base: dict[str, list[float]] = {k: [] for k, _ in HORIZONS}
    last_event_ts = None
    first_ts = ts[0] if ts else 0

    for i, (t, c) in enumerate(zip(ts, closes)):
        # need a full month of history before t to measure the drop
        if t - first_ts < MONTH_DAYS * _DAY:
            continue
        week_ago = _close_on_or_before(ts, closes, t - WEEK_DAYS * _DAY)
        month_ago = _close_on_or_before(ts, closes, t - MONTH_DAYS * _DAY)
        if not week_ago or not month_ago:
            continue

        # forward returns for this day (used by both baseline and events)
        day_fwd = {}
        for key, days in HORIZONS:
            j = _index_on_or_after(ts, t + days * _DAY)
            if j is not None:
                day_fwd[key] = _pct(closes[j], c)
                base[key].append(day_fwd[key])

        w, m = _pct(c, week_ago), _pct(c, month_ago)
        if w > -weekly_threshold or m > -monthly_threshold:
            continue
        if last_event_ts is not None and t - last_event_ts < COOLDOWN_DAYS * _DAY:
            continue
        last_event_ts = t

        # recovery back to the pre-dip (month-ago) level, and the deepest
        # further fall, within the recovery window
        end = t + RECOVERY_WINDOW_DAYS * _DAY
        recovered_days = None
        low = c
        k = i + 1
        while k < len(ts) and ts[k] <= end:
            low = min(low, closes[k])
            if recovered_days is None and closes[k] >= month_ago:
                recovered_days = round((ts[k] - t) / _DAY)
            k += 1
        window_complete = bool(ts) and ts[-1] >= end

        for key in day_fwd:
            fwd[key].append(day_fwd[key])
        events.append({
            "date": datetime.fromtimestamp(t, timezone.utc).date().isoformat(),
            "close": round(c, 4),
            "weekly": round(w, 2),
            "monthly": round(m, 2),
            "fwd": {k: round(v, 2) for k, v in day_fwd.items()},
            "max_further_drop": round(_pct(low, c), 2) if k > i + 1 else None,
            "recovered_days": recovered_days,
            # True/False once the 90-day window has fully played out; None
            # for a recent dip that's still inside its window
            "recovered": True if recovered_days is not None else (False if window_complete else None),
        })

    settled = [e for e in events if e["recovered"] is not None]
    rec_days = [e["recovered_days"] for e in events if e["recovered_days"] is not None]
    return {
        "events": events,
        "summary": {
            "count": len(events),
            "horizons": {k: _stats(v) for k, v in fwd.items()},
            "baseline": {k: _stats(v) for k, v in base.items()},
            "recovery_rate": round(sum(e["recovered"] for e in settled) / len(settled) * 100, 1) if settled else None,
            "median_days_to_recover": median(rec_days) if rec_days else None,
        },
    }


# ── Data fetchers ────────────────────────────────────────────────────────────

def fetch_yahoo_daily(symbol: str, years: int) -> tuple[list[int], list[float]]:
    from urllib.parse import quote
    r = requests.get(_YAHOO.format(quote(symbol, safe="")), headers=_HEADERS, timeout=20,
                     params={"range": f"{years}y", "interval": "1d"})
    if r.status_code == 404:
        raise LookupError(f"No price history for {symbol}")
    r.raise_for_status()
    res = (r.json().get("chart") or {}).get("result")
    if not res or not res[0].get("timestamp"):
        raise LookupError(f"No price history for {symbol}")
    q = (res[0].get("indicators", {}).get("quote") or [{}])[0]
    pairs = [(t, c) for t, c in zip(res[0]["timestamp"], q.get("close", [])) if c is not None]
    if not pairs:
        raise LookupError(f"No price history for {symbol}")
    return [p[0] for p in pairs], [float(p[1]) for p in pairs]


def fetch_binance_daily(base: str, years: int, headers: dict | None = None) -> tuple[list[int], list[float]]:
    pair = base.upper() + "USDT"
    start_ms = int((time.time() - years * 365 * _DAY) * 1000)
    out: dict[int, float] = {}
    while True:   # Binance returns at most 1000 candles per call
        r = requests.get(_BINANCE_KLINES, headers=headers or {}, timeout=20,
                         params={"symbol": pair, "interval": "1d", "startTime": start_ms, "limit": 1000})
        if r.status_code == 400:   # Binance: {"code": -1121, "msg": "Invalid symbol."}
            raise LookupError(f"{pair} isn't traded on Binance")
        r.raise_for_status()
        kl = r.json()
        if not kl:
            break
        for k in kl:
            out[int(k[0]) // 1000] = float(k[4])
        if len(kl) < 1000:
            break
        start_ms = int(kl[-1][0]) + _DAY * 1000
    if not out:
        raise LookupError(f"No price history for {pair}")
    ts = sorted(out)
    return ts, [out[t] for t in ts]


# Results are cached briefly: reopening the same stock's panel, or trying
# another threshold, shouldn't refetch years of history.
_cache: dict[tuple, tuple[float, tuple]] = {}
_cache_lock = Lock()
_CACHE_TTL = 6 * 3600


def get_history(symbol: str, market: str, years: int, binance_headers: dict | None = None):
    key = (symbol, market, years)
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < _CACHE_TTL:
            return hit[1]
    data = fetch_binance_daily(symbol, years, binance_headers) if market == "crypto" else fetch_yahoo_daily(symbol, years)
    with _cache_lock:
        if len(_cache) > 500:
            _cache.clear()
        _cache[key] = (time.time(), data)
    return data


def backtest(symbol: str, market: str, weekly: float, monthly: float, years: int,
             binance_headers: dict | None = None) -> dict:
    ts, closes = get_history(symbol, market, years, binance_headers)
    if not ts:
        raise LookupError(f"No price history for {symbol}")
    result = run_backtest(ts, closes, weekly, monthly)
    # A thinned price series for the chart (≤ ~400 points keeps payload small)
    step = max(1, len(ts) // 400)
    idx = list(range(0, len(ts), step))
    if idx[-1] != len(ts) - 1:
        idx.append(len(ts) - 1)
    result["series"] = [[datetime.fromtimestamp(ts[i], timezone.utc).date().isoformat(), round(closes[i], 4)] for i in idx]
    result["params"] = {"symbol": symbol, "market": market, "weekly": weekly, "monthly": monthly,
                        "years": years, "from": result["series"][0][0], "to": result["series"][-1][0]}
    return result
