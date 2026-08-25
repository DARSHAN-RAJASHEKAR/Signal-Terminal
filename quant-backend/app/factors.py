import pandas as pd
import pandas_ta as ta


def compute_technical_indicators(price_df: pd.DataFrame) -> dict:
    """plan.md §6.4 — RSI/MACD/ADX/Bollinger/ATR via pandas-ta (not hand-rolled)."""
    df = price_df.copy()
    if len(df) < 30:
        return {
            "rsi_14": None, "macd": None, "macd_signal": None,
            "adx_14": None, "atr_14": None, "bb_upper": None, "bb_lower": None,
            "avg_volume_20": None, "volume_ratio_today": None,
        }

    rsi = ta.rsi(df["close"], length=14)
    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    adx = ta.adx(df["high"], df["low"], df["close"], length=14)
    atr = ta.atr(df["high"], df["low"], df["close"], length=14)
    bb = ta.bbands(df["close"], length=20, std=2)

    avg_volume_20 = df["volume"].rolling(20).mean()

    def last(series):
        if series is None or len(series) == 0:
            return None
        val = series.iloc[-1]
        return float(val) if pd.notna(val) else None

    return {
        "rsi_14": last(rsi),
        "macd": last(macd["MACD_12_26_9"]) if macd is not None else None,
        "macd_signal": last(macd["MACDs_12_26_9"]) if macd is not None else None,
        "adx_14": last(adx["ADX_14"]) if adx is not None else None,
        "atr_14": last(atr),
        "bb_upper": last(bb["BBU_20_2.0_2.0"]) if bb is not None else None,
        "bb_lower": last(bb["BBL_20_2.0_2.0"]) if bb is not None else None,
        "avg_volume_20": last(avg_volume_20),
        "volume_ratio_today": (
            float(df["volume"].iloc[-1]) / last(avg_volume_20)
            if last(avg_volume_20) else None
        ),
    }


def compute_momentum_block(price_df: pd.DataFrame, nifty_df: pd.DataFrame | None,
                            rel_strength_window: int = 75) -> dict:
    """plan.md §6.1."""
    close = price_df["close"]
    n = len(close)

    momentum_12_1 = None
    if n > 252:
        c_t1, c_t252 = close.iloc[-21], close.iloc[-252]
        if c_t252:
            momentum_12_1 = 100 * (c_t1 - c_t252) / c_t252

    dist_from_52w_high = None
    if n >= 2:
        window = close.iloc[-252:] if n >= 252 else close
        high_52w = window.max()
        if high_52w:
            dist_from_52w_high = float(close.iloc[-1] / high_52w)

    rel_strength_nifty = None
    if nifty_df is not None and n > rel_strength_window and len(nifty_df) > rel_strength_window:
        stock_ret = (close.iloc[-1] / close.iloc[-rel_strength_window] - 1) * 100
        nifty_close = nifty_df["close"]
        if len(nifty_close) > rel_strength_window:
            nifty_ret = (nifty_close.iloc[-1] / nifty_close.iloc[-rel_strength_window] - 1) * 100
            rel_strength_nifty = float(stock_ret - nifty_ret)

    return {
        "momentum_12_1": float(momentum_12_1) if momentum_12_1 is not None else None,
        "dist_from_52w_high": dist_from_52w_high,
        "rel_strength_nifty": rel_strength_nifty,
    }


def compute_earnings_block(f: dict) -> dict:
    """plan.md §6.2. Trendlyne exposes EPS YoY growth and OPM QoQ-YoY change
    as precomputed parameters (confirmed via live discovery), used directly
    rather than reconstructed from raw revenue/EBITDA/margin line items —
    this is the plan's stated EPS-YoY fallback methodology for earnings
    surprise, since Trendlyne's MCP tools don't expose a consensus-estimate
    field under a confirmed, stable name."""
    if f is None:
        return {"earnings_surprise_pct": None, "margin_improving": None}

    eps_yoy_growth_pct = f.get("eps_yoy_growth_pct")
    opm_yoy_chg_pct = f.get("operating_margin_yoy_chg_pct")

    return {
        "earnings_surprise_pct": eps_yoy_growth_pct,
        "margin_improving": (opm_yoy_chg_pct > 0) if opm_yoy_chg_pct is not None else None,
    }
