import asyncio
import json
import re
import time
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.config import FUNDAMENTALS_MAX_AGE_DAYS, TRENDLYNE_MCP_URL
from app.db import get_latest_fundamentals, insert_fundamentals


class TrendlyneAPIError(Exception):
    """Trendlyne signals failures (rate limits, etc.) as a
    {"status": "error", "message": ...} JSON body — even from tools whose
    success response isn't JSON at all. Confirmed live: a big scan tripped
    "Maximum weighted channel limit exceeded. [code:1002]" partway through,
    and the un-checked code crashed on the missing "markdown_data" key with
    an opaque KeyError instead of surfacing what actually happened."""

# Confirmed via a live discovery call (python -m scripts.discover_trendlyne_tools)
# against the real Trendlyne MCP Pro subscription. There is no single
# "get fundamentals for symbol" tool — instead:
#   - get_parameter_values_multi_stock(query): semantic search over a large
#     parameter catalog; exact parameter names below were confirmed live and
#     must match verbatim (e.g. "ROE Ann. %").
#   - get_ownership_deals_insider_sast(stock_code, type="shareholding"):
#     quarterly promoter-holding/pledge time series.
#   - get_overview_news_corp_events(stock_code, type="overview"): includes an
#     asmData block that's empty when the stock is clear of ASM/GSM
#     surveillance (confirmed empty for INFY and SUZLON) — this finally fills
#     plan.md §7.6's tradability gate, which had no data source before.
# Trendlyne's own Piotroski Score is used directly rather than reconstructed
# from 9 sub-tests (plan.md §6.3) — it's their canonical computed value.

# get_parameter_values_multi_stock does similarity-ranked semantic search,
# not exact keyword matching — confirmed live that cramming all 6 terms into
# one query silently drops some (ROE and D/E vanished) while two smaller,
# themed queries reliably return all of them. Split accordingly.
#
# Also confirmed live: short/ambiguous tickers like "LT" and "BEL" often
# return nothing when used as the query's stock identifier, but querying
# with the full company name ("Larsen and Toubro", "Bharat Electronics")
# reliably matches. Response rows are still keyed by ticker regardless of
# what the query text says, so parsing is unaffected — only the query
# wording changes. `{name}` should be the company name when known, falling
# back to the raw symbol otherwise (see fetch_fundamentals).
QUALITY_PARAMETER_NAMES = {"Piotroski Score", "ROE Ann. %", "ROCE Ann. %", "Total Debt to Total Equity Ann."}
QUALITY_QUERY_TEMPLATE = (
    "{name} Piotroski Score Return on Equity Annual Return on Capital Employed Annual "
    "Total Debt to Total Equity Annual"
)

EARNINGS_PARAMETER_NAMES = {"OPM Qtr YoY Chg %", "EPS Qtr YoY Growth %"}
EARNINGS_QUERY_TEMPLATE = "{name} Operating Margin Quarter YoY Change EPS Quarter YoY Growth"


@asynccontextmanager
async def open_session():
    """Callers should open ONE session per scan and reuse it across every
    symbol/tool call. Each connection is a full HTTP+MCP handshake — opening
    a fresh one per tool call (the original design) made a ~320-call
    fundamentals refresh take several minutes; live-tested this fix, not
    just theorized it."""
    async with streamable_http_client(TRENDLYNE_MCP_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def discover_tools() -> list[dict]:
    async with open_session() as session:
        tools = await session.list_tools()
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools.tools
        ]


# Confirmed live: a big scan (100+ symbols, up to 4 calls each, no delay
# between them) tripped Trendlyne's "Maximum weighted channel limit
# exceeded" partway through, and every call after that point failed for the
# rest of the scan. The exact threshold is unknown — this interval is a
# conservative, untested-at-the-margin guess to avoid tripping it at all.
_MIN_CALL_INTERVAL = 0.5
_last_call_ts = 0.0


async def _throttle():
    global _last_call_ts
    elapsed = time.monotonic() - _last_call_ts
    if elapsed < _MIN_CALL_INTERVAL:
        await asyncio.sleep(_MIN_CALL_INTERVAL - elapsed)
    _last_call_ts = time.monotonic()


async def _call_tool(session: ClientSession, tool_name: str, arguments: dict) -> Any:
    """No same-scan retry: live-tested that Trendlyne's rate-limit error
    doesn't clear within 16s of backoff, so retrying here only multiplies
    wasted calls on something that won't succeed anyway. Fail fast — the
    symbol stays stale and gets picked up on a later scan instead."""
    await _throttle()
    result = await session.call_tool(tool_name, arguments)
    text_parts = [c.text for c in result.content if hasattr(c, "text")]
    raw = "\n".join(text_parts)

    # Trendlyne signals errors as {"status": "error", ...} even from tools
    # whose success response isn't JSON at all — detect this generically
    # rather than letting downstream parsing crash on a missing key.
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        parsed = None
    if isinstance(parsed, dict) and parsed.get("status") == "error":
        raise TrendlyneAPIError(parsed.get("message", "unknown Trendlyne API error"))
    return raw


def _parse_parameter_values(raw_text: str, symbol: str, wanted: set[str]) -> dict[str, float | None]:
    """get_parameter_values_multi_stock returns double-JSON-encoded markdown:
    an outer {"markdown_data": "<json-string>"} whose value is itself a JSON
    string containing "---"-separated blocks, each starting with a parameter
    name line followed by "<SYMBOL>:<value>" rows for each matched stock."""
    outer = json.loads(raw_text)
    text = json.loads(outer["markdown_data"])
    values: dict[str, float | None] = {}
    for block in text.split("\n---\n"):
        lines = block.strip().split("\n")
        if not lines:
            continue
        name = lines[0].strip()
        if name not in wanted:
            continue
        for line in lines[1:]:
            prefix = f"{symbol}:"
            if line.startswith(prefix):
                raw_val = line[len(prefix):].strip()
                values[name] = None if raw_val in ("None", "") else float(raw_val)
                break
    return values


def _parse_pledge_trend(raw_text: str) -> tuple[float | None, float | None]:
    """get_ownership_deals_insider_sast(type='shareholding') returns a plain
    "section:\\n  key: value" text block; the Promoter chart row is a single
    line of comma-separated JSON array literals (one per quarter):
    ["Mar 2025", holding%, annotation, pledge%, annotation, locked%, annotation]."""
    match = re.search(r"Promoter:\s*\n\s*(\[.+)", raw_text)
    if not match:
        return None, None
    line = match.group(1).splitlines()[0].strip()
    try:
        rows = json.loads(f"[{line}]")
    except json.JSONDecodeError:
        return None, None
    data_rows = rows[1:]  # first row is the header labels
    if not data_rows:
        return None, None
    pledge_latest = data_rows[-1][3] if len(data_rows[-1]) > 3 else None
    pledge_4q_ago = data_rows[-5][3] if len(data_rows) >= 5 and len(data_rows[-5]) > 3 else None
    return pledge_latest, pledge_4q_ago


def _parse_asm_flag(raw_text: str) -> bool:
    """asmData block is present but all-blank when a stock is clear of ASM/GSM
    surveillance (confirmed live for INFY, SUZLON). Any non-empty field value
    is treated as an active flag. Unconfirmed: the exact text of a flagged
    stock's block, since none in the current watchlist happened to be flagged
    at discovery time — treat this gate cautiously until cross-checked."""
    match = re.search(r"asmData:\s*\n((?:\s+\w+:.*\n?)+)", raw_text)
    if not match:
        return False
    for line in match.group(1).strip().split("\n"):
        _, _, value = line.partition(":")
        if value.strip():
            return True
    return False


async def fetch_fundamentals(session: ClientSession, symbol: str, company_name: str | None = None) -> dict | None:
    """Each of the 4 sub-calls is caught independently: if e.g. the 3rd call
    hits a rate limit, the 2 that already succeeded are kept rather than
    discarded. Previously any single failure raised and threw away the
    whole fetch — meaning a symbol that failed partway through would need
    ALL 4 calls repeated from scratch on the next scan, including the ones
    that had already worked. That compounds badly under rate limiting,
    which is exactly when wasted calls hurt most."""
    name = company_name or symbol
    params: dict[str, float | None] = {}
    pledge_pct = pledge_pct_4q_ago = None
    asm_flag = False

    try:
        quality_raw = await _call_tool(
            session, "get_parameter_values_multi_stock",
            {"query": QUALITY_QUERY_TEMPLATE.format(name=name), "type": "stock"},
        )
        params.update(_parse_parameter_values(quality_raw, symbol, QUALITY_PARAMETER_NAMES))
    except TrendlyneAPIError:
        pass

    try:
        earnings_raw = await _call_tool(
            session, "get_parameter_values_multi_stock",
            {"query": EARNINGS_QUERY_TEMPLATE.format(name=name), "type": "stock"},
        )
        params.update(_parse_parameter_values(earnings_raw, symbol, EARNINGS_PARAMETER_NAMES))
    except TrendlyneAPIError:
        pass

    try:
        shareholding_raw = await _call_tool(
            session, "get_ownership_deals_insider_sast", {"stock_code": symbol, "type": "shareholding"}
        )
        pledge_pct, pledge_pct_4q_ago = _parse_pledge_trend(shareholding_raw)
    except TrendlyneAPIError:
        pass

    try:
        overview_raw = await _call_tool(
            session, "get_overview_news_corp_events", {"stock_code": symbol, "type": "overview"}
        )
        asm_flag = _parse_asm_flag(overview_raw)
    except TrendlyneAPIError:
        pass

    return {
        "piotroski_score": params.get("Piotroski Score"),
        "roe": params.get("ROE Ann. %"),
        "roce": params.get("ROCE Ann. %"),
        "debt_to_equity": params.get("Total Debt to Total Equity Ann."),
        "operating_margin_yoy_chg_pct": params.get("OPM Qtr YoY Chg %"),
        "eps_yoy_growth_pct": params.get("EPS Qtr YoY Growth %"),
        "promoter_pledge_pct": pledge_pct,
        "promoter_pledge_pct_4q_ago": pledge_pct_4q_ago,
        "asm_gsm_flag": int(asm_flag),
    }


def is_stale(symbol: str) -> bool:
    """plan.md §4.2 — pull fundamentals weekly, never daily, to respect quota."""
    row = get_latest_fundamentals(symbol)
    if row is None:
        return True
    as_of = date.fromisoformat(row["as_of_date"])
    return (date.today() - as_of) > timedelta(days=FUNDAMENTALS_MAX_AGE_DAYS)


CALLS_PER_SYMBOL_REFRESH = 4  # quality query + earnings query + shareholding + overview


# If the semantic-search calls return nothing for ANY of these, treat the
# whole fetch as failed rather than caching a hollow row — confirmed live
# that BEL and LT got a "successful" all-None response (no error, just no
# matching parameter blocks for those specific stocks).
_CORE_QUALITY_FIELDS = ("piotroski_score", "roe", "roce", "debt_to_equity")


async def refresh_if_stale(session: ClientSession, symbol: str, company_name: str | None = None) -> bool:
    """Returns True if a fresh pull happened, False if the cached row was
    reused OR the fetch came back empty. A failed/empty fetch is NOT cached,
    so is_stale() keeps returning True and the symbol gets retried on a
    later scan instead of being silently locked out for 7 days.

    4 tool calls per symbol refreshed (plan.md §4.2 flagged this as 1x-3x
    unknown until tested live — it's actually 4x). At a weekly cadence for
    100 symbols that's ~400 calls/week, ~1730/month — under the 2000/month
    cap but not by much, and a first-ever run refreshing all 100 symbols in
    one scan would hit exactly the 400/day cap with zero headroom. Callers
    (pipeline.py) must cap how many symbols they refresh per scan rather
    than relying on this function alone."""
    if not is_stale(symbol):
        return False
    data = await fetch_fundamentals(session, symbol, company_name)
    if data and any(data.get(f) is not None for f in _CORE_QUALITY_FIELDS):
        insert_fundamentals(symbol, data)
        return True
    return False
