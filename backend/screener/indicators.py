"""Pure indicator maths for the Stocks Screener (no I/O, no pandas).

The expensive part — a year of daily history — only changes once per
session, so it's condensed into a small per-symbol "daily state" as of the
previous close. Live values are then derived in O(1) from that state plus
the current price: RSI and MACD are recursive (Wilder smoothing / EMAs), so
"today" is just one more step of the recursion using the live price.
"""

from __future__ import annotations

from typing import Optional, Sequence

RSI_PERIOD = 14
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
MACD_CROSS_LOOKBACK = 3     # a crossover in the last N sessions counts as "fresh"
WEEK_SESSIONS = 5           # "1W avg volume" = mean of the previous 5 sessions
YEAR_SESSIONS = 252
NEAR_52W_PCT = 2.0          # within 2% of the 52W high/low
NEAR_PIVOT_PCT = 1.0        # within 1% below a resistance level counts as "near"


def _alpha(n: int) -> float:
    return 2.0 / (n + 1)


def wilder_rsi_state(closes: Sequence[float], period: int = RSI_PERIOD):
    """Returns (avg_gain, avg_loss) after the last close, or None if too short."""
    if len(closes) < period + 1:
        return None
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    ag, al = gains / period, losses / period
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        ag = (ag * (period - 1) + max(d, 0.0)) / period
        al = (al * (period - 1) + max(-d, 0.0)) / period
    return ag, al


def rsi_from_state(avg_gain: float, avg_loss: float, last_close: float, price: float,
                   period: int = RSI_PERIOD) -> float:
    d = price - last_close
    ag = (avg_gain * (period - 1) + max(d, 0.0)) / period
    al = (avg_loss * (period - 1) + max(-d, 0.0)) / period
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + ag / al)


def macd_state(closes: Sequence[float]):
    """EMA12/EMA26/signal after the last close plus the trailing histogram
    values (oldest first) used to detect recent crossovers."""
    if len(closes) < MACD_SLOW + MACD_SIGNAL:
        return None
    a_f, a_s, a_sig = _alpha(MACD_FAST), _alpha(MACD_SLOW), _alpha(MACD_SIGNAL)
    ema_f = ema_s = closes[0]
    signal = None
    hist: list[float] = []
    for i, c in enumerate(closes):
        if i:
            ema_f += a_f * (c - ema_f)
            ema_s += a_s * (c - ema_s)
        macd = ema_f - ema_s
        signal = macd if signal is None else signal + a_sig * (macd - signal)
        hist.append(macd - signal)
    return {"ema_fast": ema_f, "ema_slow": ema_s, "signal": signal,
            "hist": hist[-MACD_CROSS_LOOKBACK:]}


def macd_live(state: dict, price: float):
    """(macd, signal, histogram, cross) for today at `price`.
    cross is "bullish"/"bearish" when MACD crossed its signal line within the
    last MACD_CROSS_LOOKBACK sessions (today included) and is still on that
    side, else None."""
    ema_f = state["ema_fast"] + _alpha(MACD_FAST) * (price - state["ema_fast"])
    ema_s = state["ema_slow"] + _alpha(MACD_SLOW) * (price - state["ema_slow"])
    macd = ema_f - ema_s
    signal = state["signal"] + _alpha(MACD_SIGNAL) * (macd - state["signal"])
    h = macd - signal
    prev = state["hist"]
    cross = None
    if h > 0 and any(x <= 0 for x in prev):
        cross = "bullish"
    elif h < 0 and any(x >= 0 for x in prev):
        cross = "bearish"
    return macd, signal, h, cross


def classic_pivots(high: float, low: float, close: float) -> dict:
    """Floor-trader pivots from the previous session's H/L/C."""
    p = (high + low + close) / 3.0
    return {
        "p": p,
        "r1": 2 * p - low,
        "r2": p + (high - low),
        "r3": high + 2 * (p - low),
    }


def pivot_zone(price: float, piv: dict, near_pct: float = NEAR_PIVOT_PCT) -> Optional[str]:
    """One of near_r1, r1_breakout, near_r2, r2_breakout, near_r3,
    r3_breakout, or None (below 'near R1').

    'Near Rn'     — price within near_pct% below Rn
    'Rn breakout' — price at/above Rn but not yet near the next level
    """
    levels = [("r1", piv["r1"]), ("r2", piv["r2"]), ("r3", piv["r3"])]
    for i in range(len(levels) - 1, -1, -1):
        name, lvl = levels[i]
        if price >= lvl:
            nxt = levels[i + 1][1] if i + 1 < len(levels) else None
            if nxt is not None and price >= nxt * (1 - near_pct / 100):
                return f"near_{levels[i + 1][0]}"
            return f"{name}_breakout"
    if price >= piv["r1"] * (1 - near_pct / 100):
        return "near_r1"
    return None


def pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b in (None, 0):
        return None
    return (a - b) / b * 100.0


def build_daily_state(dates: Sequence[str], opens, highs, lows, closes, volumes,
                      session_date: str) -> Optional[dict]:
    """Condense daily history into the state needed for live metrics.
    Bars dated on/after `session_date` (the live session) are excluded so
    the state is always "as of the previous close"."""
    rows = [
        (d, h, l, c, v or 0)
        for d, o, h, l, c, v in zip(dates, opens, highs, lows, closes, volumes)
        if d < session_date and c is not None and h is not None and l is not None
    ]
    if len(rows) < MACD_SLOW + MACD_SIGNAL:
        return None
    cl = [r[3] for r in rows]
    rsi = wilder_rsi_state(cl)
    macd = macd_state(cl)
    last = rows[-1]
    year = rows[-(YEAR_SESSIONS - 1):]   # + today's bar = 252 sessions
    week_vols = [r[4] for r in rows[-WEEK_SESSIONS:]]
    return {
        "last_date": last[0],
        "prev_close": last[3],
        "prev_high": last[1],
        "prev_low": last[2],
        "hi_52w": max(r[1] for r in year),
        "lo_52w": min(r[2] for r in year),
        "avg_vol_1w": sum(week_vols) / len(week_vols) if week_vols else None,
        "rsi_ag": rsi[0] if rsi else None,
        "rsi_al": rsi[1] if rsi else None,
        "macd": macd,
    }


def intraday_change(bars: Sequence[tuple], price: float, now_ts: int, minutes: int,
                    bar_seconds: int = 300) -> Optional[float]:
    """% change over the last `minutes`, using 5-minute bars (ts, close, vol)
    where ts is the bar *start*. The reference is the close of the latest
    bar that had finished `minutes` ago; early in the session it falls back
    to the first bar's close."""
    if not bars:
        return None
    eff_now = min(now_ts, bars[-1][0] + bar_seconds)
    cutoff = eff_now - minutes * 60
    ref = None
    for ts, close, _ in bars:
        if ts + bar_seconds <= cutoff and close is not None:
            ref = close
        elif ts + bar_seconds > cutoff:
            break
    if ref is None:
        ref = next((c for _, c, _ in bars if c is not None), None)
    return pct(price, ref)


def last_bar_volume(bars: Sequence[tuple], now_ts: int, bar_seconds: int = 300) -> Optional[int]:
    """Volume of the most recent *completed* 5-minute bar."""
    for ts, _, vol in reversed(bars):
        if ts + bar_seconds <= now_ts:
            return int(vol or 0)
    return int(bars[-1][2] or 0) if bars else None
