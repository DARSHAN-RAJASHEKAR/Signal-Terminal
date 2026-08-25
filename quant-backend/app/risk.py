import pandas as pd
import pandas_ta as ta

# plan.md §9 — tunable defaults.
ATR_STOP_MULTIPLIER = 2.0          # k in Entry − k×ATR_14
TARGET_GAIN_PCT = 0.07             # midpoint of the 5–9% target band
ADX_TREND_THRESHOLD = 25           # plan.md §6.4/§8
VOLUME_SURGE_MULTIPLIER = 1.5      # plan.md §8


def check_entry_trigger(price_df: pd.DataFrame) -> bool:
    """plan.md §8 — a same-day technical trigger, combined with ADX>25 and
    above-average volume. Returns False if there isn't enough history."""
    if len(price_df) < 60:
        return False

    close, high, low, volume = price_df["close"], price_df["high"], price_df["low"], price_df["volume"]

    adx = ta.adx(high, low, close, length=14)
    adx_today = adx["ADX_14"].iloc[-1] if adx is not None else None
    if adx_today is None or pd.isna(adx_today) or adx_today <= ADX_TREND_THRESHOLD:
        return False

    avg_vol_20 = volume.rolling(20).mean().iloc[-1]
    if pd.isna(avg_vol_20) or avg_vol_20 == 0:
        return False
    volume_today = volume.iloc[-1]
    if volume_today < VOLUME_SURGE_MULTIPLIER * avg_vol_20:
        return False

    # Trigger A: breakout above the prior 20-session high.
    prior_high_20 = high.iloc[-21:-1].max()
    breakout = close.iloc[-1] > prior_high_20

    # Trigger B: MACD bullish crossover today.
    macd = ta.macd(close, fast=12, slow=26, signal=9)
    macd_crossover = False
    if macd is not None and len(macd) >= 2:
        m, s = macd["MACD_12_26_9"], macd["MACDs_12_26_9"]
        if pd.notna(m.iloc[-2]) and pd.notna(s.iloc[-2]) and pd.notna(m.iloc[-1]) and pd.notna(s.iloc[-1]):
            macd_crossover = m.iloc[-2] <= s.iloc[-2] and m.iloc[-1] > s.iloc[-1]

    # Trigger C: Bollinger squeeze resolving upward — width was in the bottom
    # quintile of the last 60 sessions, and today's close breaks the upper band.
    bb = ta.bbands(close, length=20, std=2)
    bb_squeeze_breakout = False
    if bb is not None:
        upper, lower, mid = bb["BBU_20_2.0_2.0"], bb["BBL_20_2.0_2.0"], bb["BBM_20_2.0_2.0"]
        width = (upper - lower) / mid
        if len(width.dropna()) >= 60:
            recent_width = width.iloc[-60:]
            squeeze_threshold = recent_width.quantile(0.20)
            was_squeezed = width.iloc[-2] <= squeeze_threshold
            breaks_upper = close.iloc[-1] > upper.iloc[-1]
            bb_squeeze_breakout = bool(was_squeezed and breaks_upper)

    return bool(breakout or macd_crossover or bb_squeeze_breakout)


def compute_risk_levels(price_df: pd.DataFrame, atr_14: float | None) -> dict:
    """plan.md §9 — ATR-based stop, fixed target midpoint. `entry_price` here
    is the last close (indicative reference price for the report only — a
    real backtest must lag entry to next-day open per plan.md §11)."""
    entry_price = float(price_df["close"].iloc[-1])
    if atr_14 is None or pd.isna(atr_14) or atr_14 <= 0:
        return {"entry_price": entry_price, "stop_loss": None, "target": None, "reward_risk": None}

    stop_loss = entry_price - ATR_STOP_MULTIPLIER * atr_14
    target = entry_price * (1 + TARGET_GAIN_PCT)
    risk = entry_price - stop_loss
    reward_risk = (target - entry_price) / risk if risk > 0 else None

    return {
        "entry_price": entry_price,
        "stop_loss": round(stop_loss, 2),
        "target": round(target, 2),
        "reward_risk": round(reward_risk, 2) if reward_risk else None,
    }
