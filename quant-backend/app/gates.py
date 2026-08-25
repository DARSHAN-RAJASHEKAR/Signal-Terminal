import pandas as pd
import pandas_ta as ta

# plan.md §7.1 — tunable liquidity floor (median daily traded value, INR).
MIN_MEDIAN_TRADED_VALUE = 5_00_00_000  # ₹5 crore

# plan.md §7.5 — per-sector debt/equity ceilings; capital-intensive sectors
# get a higher ceiling than a flat global cutoff would allow. Tunable.
SECTOR_DE_CEILING = {
    "Power": 2.5, "Infrastructure": 2.5, "Metals": 1.5, "Cement": 1.2,
    "Realty": 1.5, "Aviation": 3.0, "Construction": 2.0, "Capital Goods": 1.5,
    "Telecom": 2.0, "Aerospace & Defence": 1.5,
    # Added after TITAN (D/E 1.75) failed on the 1.0 default: owned/leased
    # store networks and inventory-heavy financing push retail-format
    # businesses' D/E structurally higher than manufacturers — a starting
    # estimate, not backtested. Revisit per plan.md §15.
    "Consumer Durables": 1.75, "Retail": 1.75,
}
DEFAULT_DE_CEILING = 1.0
# Banks/NBFCs/insurers are leveraged institutions by design; D/E isn't a
# meaningful comparison against non-financial sectors.
DE_GATE_EXEMPT_SECTORS = {"Financial Services", "Insurance"}


def apply_gates(price_df: pd.DataFrame, fundamentals: dict | None,
                 sector: str | None) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    if len(price_df) < 200:
        reasons.append("insufficient price history (<200 sessions)")
        return False, reasons

    # 1. Liquidity
    traded_value = (price_df["close"] * price_df["volume"]).iloc[-20:]
    median_traded_value = traded_value.median()
    if median_traded_value < MIN_MEDIAN_TRADED_VALUE:
        reasons.append(
            f"liquidity below ₹5cr (median traded value ₹{median_traded_value:,.0f})"
        )

    # 2. Trend regime: Close > 200-day SMA
    sma_200 = ta.sma(price_df["close"], length=200)
    last_close = price_df["close"].iloc[-1]
    last_sma_200 = sma_200.iloc[-1] if sma_200 is not None else None
    if last_sma_200 is None or pd.isna(last_sma_200) or last_close <= last_sma_200:
        reasons.append("price below 200-day SMA")

    # 3-5 require fundamentals
    if fundamentals is None:
        reasons.append("fundamentals unavailable")
    else:
        # 3. Pledge: 0, or not rising over last 4 quarters
        pledge = fundamentals.get("promoter_pledge_pct")
        pledge_4q_ago = fundamentals.get("promoter_pledge_pct_4q_ago")
        if pledge is not None and pledge > 0:
            if pledge_4q_ago is not None and pledge > pledge_4q_ago:
                reasons.append(f"promoter pledge rising ({pledge_4q_ago}% → {pledge}%)")

        # 4. Quality floor
        piotroski_score = fundamentals.get("piotroski_score")
        if piotroski_score is None or piotroski_score < 5:
            reasons.append(f"Piotroski F-Score below 5 ({piotroski_score})")

        # 5. Leverage floor (sector-appropriate)
        if sector not in DE_GATE_EXEMPT_SECTORS:
            de = fundamentals.get("debt_to_equity")
            ceiling = SECTOR_DE_CEILING.get(sector, DEFAULT_DE_CEILING)
            if de is None or de > ceiling:
                reasons.append(f"debt/equity above sector ceiling ({de} > {ceiling})")

        # 6. Tradability — Trendlyne's overview asmData block is blank when a
        # stock is clear of ASM/GSM surveillance (confirmed live). No circuit
        # lock data source is wired up yet.
        if fundamentals.get("asm_gsm_flag"):
            reasons.append("stock flagged in ASM/GSM surveillance")

    gate_passed = len(reasons) == 0
    return gate_passed, reasons
