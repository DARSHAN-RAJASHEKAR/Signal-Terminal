import gzip
import json
import time
from datetime import date, datetime, timedelta
from urllib.parse import quote

import requests

from app.config import PRICE_HISTORY_LOOKBACK_DAYS, UPSTOX_ACCESS_TOKEN
from app.db import get_last_price_date, insert_price_rows, set_upstox_instrument_key

# Upstox's documented tiers for "Other Standard APIs" (holdings, positions,
# funds, historical candles, quotes — everything this client calls) per the
# May 5 2025 SEBI circular: 50/sec, 500/min, 2000/30min. The per-minute tier
# is the binding one for a scan-sized burst (500 calls in a row would hit it
# exactly at 8.33 req/sec), so throttle to a rate safely under that rather
# than the much higher per-second ceiling.
_MIN_INTERVAL = 0.15  # ~6.7 req/sec, ~400/min — margin under the 500/min cap
_last_call_ts = 0.0

_BASE_URL = "https://api.upstox.com/v2"
_INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
# Live-tested: v2 historical-candle only accepts one of these — no 15minute.
INTRADAY_INTERVAL = "30minute"


def _throttle():
    global _last_call_ts
    elapsed = time.monotonic() - _last_call_ts
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_call_ts = time.monotonic()


def is_authenticated() -> bool:
    """This fork only ever runs off the long-lived Analytics token in
    .env (UPSTOX_ACCESS_TOKEN) — no daily OAuth login flow, nothing to
    expire, nothing to refresh."""
    return bool(UPSTOX_ACCESS_TOKEN)


def get_client() -> str | None:
    """Returns the access_token string (Upstox has no SDK client object like
    KiteConnect — every call here is a plain `requests` call with a Bearer
    header), or None if UPSTOX_ACCESS_TOKEN isn't configured."""
    return UPSTOX_ACCESS_TOKEN


def _auth_headers(token: str) -> dict:
    return {"Accept": "application/json", "Authorization": f"Bearer {token}"}


_instrument_cache: dict[str, dict] | None = None


def _load_instruments() -> dict[str, dict]:
    """Public, unauthenticated instrument master dump — no token needed,
    unlike Kite's instruments() call. Cached in-process for the scan."""
    global _instrument_cache
    if _instrument_cache is None:
        resp = requests.get(_INSTRUMENTS_URL, timeout=30)
        resp.raise_for_status()
        data = json.loads(gzip.decompress(resp.content))
        _instrument_cache = {
            i["trading_symbol"]: i for i in data if i.get("instrument_type") == "EQ"
        }
    return _instrument_cache


def resolve_instrument_key(symbol: str) -> str | None:
    instruments = _load_instruments()
    row = instruments.get(symbol)
    if row is None:
        return None
    set_upstox_instrument_key(symbol, row["instrument_key"], row.get("name"))
    return row["instrument_key"]


def resolve_nifty500_index_key() -> str | None:
    """UNVERIFIED live — Upstox's NSE instrument dump is filtered to
    instrument_type == 'EQ' above (equities only) for resolve_instrument_key,
    so an index symbol like 'Nifty 500' would need a separate, unfiltered
    lookup (indices likely have instrument_type == 'INDEX' or similar in the
    raw dump). Not tested — this will need fixing once actually exercised."""
    resp = requests.get(_INSTRUMENTS_URL, timeout=30)
    resp.raise_for_status()
    data = json.loads(gzip.decompress(resp.content))
    for i in data:
        if i.get("trading_symbol", "").upper() == "NIFTY 500" or i.get("name", "").upper() == "NIFTY 500":
            return i["instrument_key"]
    return None


def get_ltp(token: str, symbols: list[str]) -> dict[str, float]:
    if not symbols or not token:
        return {}
    instruments = _load_instruments()
    keys = [instruments[s]["instrument_key"] for s in symbols if s in instruments]
    if not keys:
        return {}
    _throttle()
    url = f"{_BASE_URL}/market-quote/ltp?instrument_key=" + quote(",".join(keys), safe=",")
    resp = requests.get(url, headers=_auth_headers(token))
    resp.raise_for_status()
    data = resp.json().get("data", {})
    result = {}
    for symbol in symbols:
        row = instruments.get(symbol)
        if not row:
            continue
        # response keys are "EXCHANGE_SEGMENT:SYMBOL", e.g. "NSE_EQ:INFY"
        quote_key = f"{row['segment']}:{symbol}"
        entry = data.get(quote_key)
        if entry:
            result[symbol] = entry["last_price"]
    return result


def _fetch_minute_extremes_between(
    token: str, instrument_key: str, day: date, start: datetime, end: datetime
) -> tuple[float | None, float | None]:
    """Refines a single 30-minute window down to 1-minute candles, filtered
    to [start, end) — used only for the one candle a trigger lands inside,
    so a trigger at e.g. 10:38 doesn't miss the real 10:38-10:45 high/low
    that the coarser 30-minute bar would otherwise blur together with the
    10:15-10:38 pre-entry portion of the same bar."""
    _throttle()
    day_str = day.isoformat()
    url = f"{_BASE_URL}/historical-candle/{quote(instrument_key, safe='')}/1minute/{day_str}/{day_str}"
    resp = requests.get(url, headers=_auth_headers(token))
    if resp.status_code != 200:
        return None, None
    candles = resp.json().get("data", {}).get("candles", [])
    relevant = [
        c for c in candles
        if start <= datetime.fromisoformat(c[0]).replace(tzinfo=None) < end
    ]
    if not relevant:
        return None, None
    return max(c[2] for c in relevant), min(c[3] for c in relevant)


def fetch_same_day_extremes_since(
    token: str, instrument_key: str, day: date, after_time_ist: datetime
) -> tuple[float | None, float | None]:
    """Same purpose as kite_client.fetch_same_day_extremes_since — avoids
    the ambiguity of daily OHLC granularity for a stock's own trigger day.
    Uses 30-minute candles (live-tested; Upstox's v2 API only accepts
    1minute/30minute/day/week/month, no 15minute) for everything after the
    trigger, EXCEPT the one 30-minute candle the trigger itself lands inside
    (e.g. a 10:38 trigger falls inside the 10:15-10:45 bar) — that single
    candle is refined with 1-minute candles instead, so the real
    post-trigger portion of it isn't silently dropped (confirmed live: the
    plain start-time filter used to exclude that whole bar whenever the
    trigger wasn't exactly on a 30-minute boundary)."""
    _throttle()
    day_str = day.isoformat()
    url = f"{_BASE_URL}/historical-candle/{quote(instrument_key, safe='')}/{INTRADAY_INTERVAL}/{day_str}/{day_str}"
    resp = requests.get(url, headers=_auth_headers(token))
    if resp.status_code != 200:
        return None, None
    candles = resp.json().get("data", {}).get("candles", [])
    # candle: [timestamp_iso, open, high, low, close, volume, oi]
    highs, lows = [], []
    for c in candles:
        start = datetime.fromisoformat(c[0]).replace(tzinfo=None)
        end = start + timedelta(minutes=30)
        if start >= after_time_ist:
            highs.append(c[2])
            lows.append(c[3])
        elif start < after_time_ist < end:
            b_high, b_low = _fetch_minute_extremes_between(token, instrument_key, day, after_time_ist, end)
            if b_high is not None:
                highs.append(b_high)
            if b_low is not None:
                lows.append(b_low)
    if not highs and not lows:
        return None, None
    return (max(highs) if highs else None), (min(lows) if lows else None)


def fetch_incremental_history(token: str, symbol: str, instrument_key: str):
    """Pull only new daily candles since the last stored date; full lookback
    on first run. Writes to the same price_daily table Kite writes to — the
    schema doesn't care which broker sourced the data."""
    last_date = get_last_price_date(symbol)
    if last_date:
        from_date = (datetime.strptime(last_date, "%Y-%m-%d") + timedelta(days=1)).date()
    else:
        from_date = date.today() - timedelta(days=PRICE_HISTORY_LOOKBACK_DAYS)
    to_date = date.today()
    if from_date > to_date:
        return

    _throttle()
    url = f"{_BASE_URL}/historical-candle/{quote(instrument_key, safe='')}/day/{to_date.isoformat()}/{from_date.isoformat()}"
    resp = requests.get(url, headers=_auth_headers(token))
    resp.raise_for_status()
    candles = resp.json().get("data", {}).get("candles", [])
    rows = [
        {
            "date": datetime.fromisoformat(c[0]).strftime("%Y-%m-%d"),
            "open": c[1],
            "high": c[2],
            "low": c[3],
            "close": c[4],
            "volume": c[5],
            "delivery_pct": None,
        }
        for c in candles
    ]
    insert_price_rows(symbol, rows)
