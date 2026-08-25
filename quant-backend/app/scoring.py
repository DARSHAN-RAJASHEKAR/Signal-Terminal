import pandas as pd

# plan.md §6.5 — block weights (starting point, tunable via backtesting in v2).
BLOCK_WEIGHTS = {"momentum": 0.35, "earnings": 0.30, "quality": 0.20, "technical": 0.15}

BLOCK_FACTORS = {
    "momentum": ["momentum_12_1", "dist_from_52w_high", "rel_strength_nifty"],
    "earnings": ["earnings_surprise_pct", "margin_improving_num"],
    "quality": ["piotroski_score", "roe", "roce", "debt_to_equity_inv"],
    "technical": ["rsi_14", "adx_14", "macd_hist"],
}


def _prep_frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows).set_index("symbol")
    df["margin_improving_num"] = df.get("margin_improving").map(
        {True: 1.0, False: 0.0}
    ) if "margin_improving" in df else None
    if "debt_to_equity" in df:
        df["debt_to_equity_inv"] = -df["debt_to_equity"]
    df["macd_hist"] = df.get("macd") - df.get("macd_signal") if "macd" in df else None
    return df


def _zscore(s: pd.Series) -> pd.Series:
    """plan.md §6.5 — cross-sectional z-score, winsorized at ±3."""
    mean, std = s.mean(), s.std()
    if pd.isna(std) or std == 0:
        return pd.Series(float("nan"), index=s.index)
    return ((s - mean) / std).clip(-3, 3)


def compute_composite_scores(rows: list[dict]) -> dict[str, dict]:
    """rows: one dict per symbol with raw factor values + a `gate_passed` bool.
    Z-score mean/std are computed over the gate-passed universe only (per
    plan.md §6.5: "cross-sectional z-score across that day's eligible
    universe"); gate-failed symbols still get a comparable score against
    that baseline, but are excluded from ranking."""
    df = _prep_frame(rows)
    eligible = df[df["gate_passed"] == True]  # noqa: E712

    block_z_cols = {}
    for block, factor_cols in BLOCK_FACTORS.items():
        z_cols = []
        for col in factor_cols:
            if col not in df.columns:
                continue
            series = pd.to_numeric(df[col], errors="coerce")
            mean = pd.to_numeric(eligible[col], errors="coerce").mean() if col in eligible else None
            std = pd.to_numeric(eligible[col], errors="coerce").std() if col in eligible else None
            if mean is None or pd.isna(std) or std == 0:
                z = pd.Series(float("nan"), index=df.index)
            else:
                z = ((series - mean) / std).clip(-3, 3)
            z_cols.append(z)
        block_z = pd.concat(z_cols, axis=1).mean(axis=1, skipna=True) if z_cols else pd.Series(0.0, index=df.index)
        block_z_cols[f"{block}_z"] = block_z.fillna(0.0)

    z_df = pd.DataFrame(block_z_cols, index=df.index)
    composite = sum(BLOCK_WEIGHTS[b] * z_df[f"{b}_z"] for b in BLOCK_WEIGHTS)
    z_df["composite_score"] = composite

    ranks = (
        z_df.loc[eligible.index, "composite_score"]
        .rank(ascending=False, method="min")
        .astype(int)
    )
    z_df["rank"] = ranks.reindex(z_df.index)

    return {
        symbol: {
            "momentum_z": row["momentum_z"],
            "earnings_z": row["earnings_z"],
            "quality_z": row["quality_z"],
            "technical_z": row["technical_z"],
            "composite_score": row["composite_score"],
            "rank": int(row["rank"]) if pd.notna(row["rank"]) else None,
        }
        for symbol, row in z_df.iterrows()
    }
