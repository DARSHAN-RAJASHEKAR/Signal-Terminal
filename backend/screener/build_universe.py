"""Build backend/screener/data/universe.json for the Stocks Screener.

Run from the backend/ directory:

    python -m screener.build_universe

Sources (all public NSE downloads):
  * niftyindices.com constituent CSVs — membership of each filterable index,
    company name and NSE industry.
  * NSE daily "PR" bhavcopy bundle (mcapDDMMYYYY.csv) — issued share count
    per symbol, so the server can compute live market cap = price x shares.

Index membership changes at the semi-annual rebalances (March/September),
and share counts change on buybacks/QIPs/splits — re-run this every few
months and commit the regenerated JSON.
"""

from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path

import requests

from .sectors import SECTORS, resolve_sector

OUT_PATH = Path(__file__).resolve().parent / "data" / "universe.json"

# niftyindices rejects requests without a browser-style User-Agent.
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
}

_INDEX_CSV = "https://www.niftyindices.com/IndexConstituent/ind_{}.csv"
# Screener index code -> niftyindices file stem. "total" (Nifty Total
# Market) is the full screener universe; every other index is a subset.
INDEX_FILES = {
    "total": "niftytotalmarket_list",
    "nifty50": "nifty50list",
    "nifty100": "nifty100list",
    "nifty500": "nifty500list",
    "midcap100": "niftymidcap100list",
    "midcap150": "niftymidcap150list",
    "smallcap100": "niftysmallcap100list",
    "smallcap250": "niftysmallcap250list",
}

_PR_ZIP = "https://nsearchives.nseindia.com/archives/equities/bhavcopy/pr/PR{}.zip"


def _get(url: str) -> requests.Response:
    r = requests.get(url, headers=_HEADERS, timeout=30)
    r.raise_for_status()
    return r


def fetch_index(stem: str) -> list[dict]:
    text = _get(_INDEX_CSV.format(stem)).text
    return [row for row in csv.DictReader(io.StringIO(text)) if row.get("Symbol")]


def fetch_share_counts(max_days_back: int = 10) -> tuple[str, dict[str, int]]:
    """Issued shares per symbol from the most recent PR bundle available."""
    day = date.today()
    for _ in range(max_days_back):
        tag = day.strftime("%d%m%y")
        try:
            r = _get(_PR_ZIP.format(tag))
        except requests.HTTPError:
            day -= timedelta(days=1)
            continue
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            name = next(n for n in zf.namelist() if n.lower().startswith("mcap"))
            text = zf.read(name).decode("utf-8", errors="replace")
        shares: dict[str, int] = {}
        for row in csv.DictReader(io.StringIO(text)):
            row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
            sym, series = row.get("Symbol"), row.get("Series")
            try:
                issue = int(float(row.get("Issue Size", "")))
            except ValueError:
                continue
            # Prefer the EQ line when a symbol trades in several series.
            if sym and (sym not in shares or series == "EQ"):
                shares[sym] = issue
        return day.isoformat(), shares
    raise RuntimeError(f"No NSE PR bundle found in the last {max_days_back} days")


def _clean_name(name: str) -> str:
    name = name.strip()
    for suffix in (" Ltd.", " Ltd", " Limited", " LTD.", " LTD"):
        if name.endswith(suffix):
            return name[: -len(suffix)].strip()
    return name


def build() -> dict:
    members: dict[str, list[dict]] = {}
    for code, stem in INDEX_FILES.items():
        members[code] = fetch_index(stem)
        print(f"  {code:<12} {len(members[code]):>4} constituents")

    shares_date, shares = fetch_share_counts()
    print(f"  share counts from NSE PR bundle of {shares_date}: {len(shares)} symbols")

    index_of: dict[str, list[str]] = {}
    for code, rows in members.items():
        if code == "total":
            continue
        for row in rows:
            index_of.setdefault(row["Symbol"], []).append(code)

    stocks, missing_shares = [], []
    for row in members["total"]:
        sym = row["Symbol"].strip()
        if sym.startswith("DUMMY"):  # NSE placeholder rows during corporate actions
            continue
        if sym not in shares:
            missing_shares.append(sym)
        stocks.append({
            "symbol": sym,
            "name": _clean_name(row["Company Name"]),
            "sector": resolve_sector(sym, row["Industry"].strip()),
            "indices": sorted(index_of.get(sym, [])),
            "shares": shares.get(sym),
        })

    if missing_shares:
        print(f"  WARNING: no share count for {missing_shares} — market cap will show as —")

    # Membership outside Total Market would be silently dropped; surface it.
    total_syms = {s["symbol"] for s in stocks}
    stray = sorted(s for s in index_of if s not in total_syms and not s.startswith("DUMMY"))
    if stray:
        print(f"  WARNING: in a sub-index but not Total Market (dropped): {stray}")

    return {
        "generated_on": date.today().isoformat(),
        "shares_as_of": shares_date,
        "sectors": SECTORS,
        "stocks": stocks,
    }


def main() -> int:
    print("Building screener universe…")
    data = build()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"Wrote {len(data['stocks'])} stocks -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
