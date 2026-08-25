import re
from contextlib import contextmanager
from datetime import date

import libsql_experimental as libsql
import pandas as pd

from app.config import TURSO_AUTH_TOKEN, TURSO_DATABASE_URL

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS watchlist (
    symbol TEXT PRIMARY KEY,
    upstox_instrument_key TEXT,
    company_name TEXT,
    sector TEXT,
    rank INTEGER,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS price_daily (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER,
    delivery_pct REAL,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_price_daily_symbol_date ON price_daily(symbol, date);

-- plan.md §6.2/§6.3 fields, sourced from Trendlyne MCP's own precomputed
-- parameters rather than reconstructed from raw balance-sheet line items.
CREATE TABLE IF NOT EXISTS fundamentals_quarterly (
    symbol TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    piotroski_score REAL,
    roe REAL, roce REAL, debt_to_equity REAL,
    operating_margin_yoy_chg_pct REAL,
    eps_yoy_growth_pct REAL,
    promoter_pledge_pct REAL, promoter_pledge_pct_4q_ago REAL,
    asm_gsm_flag INTEGER,
    PRIMARY KEY (symbol, as_of_date)
);

-- One row per Scan click — the history index. factor_daily rows are tagged
-- with the run that produced them and are never overwritten, so every past
-- scan stays browsable.
CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_timestamp TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    symbols_scanned INTEGER,
    gates_passed INTEGER,
    errors TEXT,
    watchlist_limit INTEGER
);
CREATE INDEX IF NOT EXISTS idx_scan_runs_timestamp ON scan_runs(scan_timestamp);

CREATE TABLE IF NOT EXISTS factor_daily (
    scan_run_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    close_price REAL,
    momentum_12_1 REAL, dist_from_52w_high REAL, rel_strength_nifty REAL,
    rsi_14 REAL, macd REAL, macd_signal REAL, adx_14 REAL, atr_14 REAL,
    bb_upper REAL, bb_lower REAL,
    piotroski_score INTEGER, earnings_surprise_pct REAL,
    roe REAL, roce REAL, debt_to_equity REAL,
    momentum_z REAL, earnings_z REAL, quality_z REAL, technical_z REAL,
    composite_score REAL, rank INTEGER,
    gate_passed INTEGER, gate_reasons TEXT,
    entry_trigger_today INTEGER,
    entry_price REAL, stop_loss REAL, target REAL, reward_risk REAL,
    PRIMARY KEY (scan_run_id, symbol),
    FOREIGN KEY (scan_run_id) REFERENCES scan_runs(id)
);
CREATE INDEX IF NOT EXISTS idx_factor_daily_run ON factor_daily(scan_run_id, rank);

-- One row per symbol per day it showed a live entry trigger (plan.md §8).
-- Keyed on (symbol, trigger_date) so re-scanning the same day doesn't
-- duplicate the entry.
CREATE TABLE IF NOT EXISTS triggers (
    symbol TEXT NOT NULL,
    trigger_date TEXT NOT NULL,
    triggered_at TEXT NOT NULL,
    entry_price REAL NOT NULL,
    scan_run_id INTEGER,
    PRIMARY KEY (symbol, trigger_date)
);
CREATE INDEX IF NOT EXISTS idx_triggers_date ON triggers(trigger_date);
"""


# --- Turso/libsql compatibility layer -----------------------------------
#
# libsql_experimental's `execute()`/`executemany()` only accept positional
# (list/tuple) parameters — unlike sqlite3, it has no support for named
# `:name` placeholders bound from a dict, and no `sqlite3.Row` row factory
# for dict-style `row["col"]` access. Both were used throughout this file.
# This layer converts `:name` SQL + dict params to `?` SQL + positional
# tuples transparently, and wraps cursors so `row["col"]` and `dict(row)`
# keep working exactly like they did with sqlite3.Row.
#
# Two things had to be worked around after live-testing against a real Turso
# database, not just guessed from docs:
#
# 1. The "embedded replica" pattern (local file + sync_url, reads served
#    locally, writes forwarded on commit) — the officially recommended mode
#    for this kind of app — is unreliable in this library version: a 10-row
#    executemany() hung indefinitely, and a table was reported "not found"
#    immediately after being created and committed on the same connection.
#    A plain remote-only connection (no local file, every call goes straight
#    to Turso) does not exhibit either problem — confirmed with repeated
#    live create/write/read cycles. It costs a real network round-trip per
#    call (no free local reads), which this app's per-scan call volume can
#    absorb; it does not get the "Render disk gets wiped" benefit from local
#    caching, but doesn't need to — Turso is the only copy either way.
#
# 2. executemany() itself hangs against Turso regardless of row count.
#    Every INSERT ... VALUES (...) executemany() call site in this file is
#    rewritten into one (or a few, if large) genuine multi-row
#    VALUES (...),(...),(...) statement instead, sent via a single execute()
#    — one round-trip instead of N, and it sidesteps executemany() entirely.

_NAMED_PARAM_RE = re.compile(r":(\w+)")
_VALUES_CLAUSE_RE = re.compile(r"VALUES\s*(\([^)]*\))", re.IGNORECASE)
# Conservative margin under SQLite's default 999-bound-variable limit —
# chunk size is derived from how many params one row actually uses so wide
# tables (factor_daily) and narrow ones (watchlist) both stay safely under it.
_MAX_PARAMS_PER_STATEMENT = 900


class Row(dict):
    """dict subclass — supports row['col'] and dict(row), matching how
    sqlite3.Row was used throughout this codebase."""


def _to_positional(sql: str, params):
    if params is None:
        return sql, None
    if isinstance(params, (list, tuple)):
        return sql, tuple(params)
    names = _NAMED_PARAM_RE.findall(sql)
    if not names:
        return sql, None
    return _NAMED_PARAM_RE.sub("?", sql), tuple(params[n] for n in names)


class _CursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    def _cols(self):
        return [d[0] for d in self._cursor.description] if self._cursor.description else []

    def fetchone(self):
        row = self._cursor.fetchone()
        return Row(zip(self._cols(), row)) if row is not None else None

    def fetchall(self):
        cols = self._cols()
        return [Row(zip(cols, r)) for r in self._cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())

    @property
    def lastrowid(self):
        return self._cursor.lastrowid


def _is_stale_stream_error(exc: Exception) -> bool:
    """Turso's remote Hrana stream backing a connection has a server-side
    idle/lifetime limit — confirmed live that a long-lived connection can
    outlive it, after which every further call fails with 'stream not
    found' (HTTP 404) instead of something recoverable-looking. Detected
    generically off the message since libsql_experimental raises a plain
    ValueError, not a dedicated exception type."""
    msg = str(exc)
    return "stream not found" in msg or "Hrana" in msg


def _with_reconnect(fn):
    """Retries once, against a freshly-opened connection, if the call fails
    with a stale-stream error."""

    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as e:
            if not _is_stale_stream_error(e):
                raise
            _reconnect()
            return fn(*args, **kwargs)

    return wrapper


class _ConnWrapper:
    """Thin wrapper around the shared libsql connection — every get_conn()
    call reuses the same underlying connection (see _get_connection) rather
    than opening a new one per call. Always resolves the connection fresh
    via _get_connection() rather than capturing it at construction time, so
    a mid-request reconnect (see _with_reconnect) is picked up by every
    subsequent call, not just new _ConnWrapper instances."""

    @_with_reconnect
    def execute(self, sql, params=None):
        conn = _get_connection()
        sql, params = _to_positional(sql, params)
        cur = conn.execute(sql, params) if params is not None else conn.execute(sql)
        return _CursorWrapper(cur)

    @_with_reconnect
    def executemany(self, sql, params_list):
        """executemany() itself hangs indefinitely against Turso (confirmed
        live, regardless of row count) — every call site in this file is an
        INSERT ... VALUES (...) [ON CONFLICT ...] template, so this rebuilds
        it into one or more genuine multi-row VALUES (...),(...),... batches
        sent via execute(), chunked to stay under SQLite's bound-variable
        limit. There is exactly one non-INSERT executemany() caller in this
        file (set_active_symbols) — it doesn't go through this method; see
        its own IN-clause rewrite instead."""
        params_list = list(params_list)
        if not params_list:
            return
        if isinstance(params_list[0], dict):
            names = _NAMED_PARAM_RE.findall(sql)
            sql = _NAMED_PARAM_RE.sub("?", sql)
            rows = [tuple(p[n] for n in names) for p in params_list]
        else:
            rows = [tuple(p) for p in params_list]

        match = _VALUES_CLAUSE_RE.search(sql)
        values_clause = match.group(1)
        n_params_per_row = values_clause.count("?")
        chunk_size = max(1, _MAX_PARAMS_PER_STATEMENT // max(n_params_per_row, 1))

        conn = _get_connection()
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i:i + chunk_size]
            batch_values = ",".join([values_clause] * len(chunk))
            batch_sql = sql[:match.start()] + "VALUES " + batch_values + sql[match.end():]
            flat_params = tuple(v for row in chunk for v in row)
            conn.execute(batch_sql, flat_params)

    @_with_reconnect
    def executescript(self, script):
        return _get_connection().executescript(script)

    @_with_reconnect
    def commit(self):
        _get_connection().commit()

    @property
    def raw(self):
        """The underlying libsql connection object, for callers (pandas)
        that need a real DBAPI2-ish connection rather than this wrapper."""
        return _get_connection()


_connection = None


def _open_connection():
    """Plain remote connection — no local file, no sync_url. Turso's
    "embedded replica" mode (local file + sync_url) is the officially
    recommended pattern and was tried first, but proved unreliable in this
    library version (see the module docstring above): a 10-row executemany
    hung indefinitely, and a just-created, just-committed table was
    reported "not found" on the very next read on the same connection. This
    plain remote mode showed neither problem across repeated live testing —
    every call just costs a real network round-trip, which this app's
    per-scan call volume can absorb."""
    return libsql.connect(TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)


def _get_connection():
    """One persistent connection for the process lifetime (barring a
    reconnect — see _with_reconnect)."""
    global _connection
    if _connection is None:
        _connection = _open_connection()
    return _connection


def _reconnect():
    global _connection
    if _connection is not None:
        try:
            _connection.close()
        except Exception:
            pass  # stale connection may already be unusable — fine to drop either way
    _connection = _open_connection()


def get_setting(key: str, default: str | None = None) -> str | None:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


@contextmanager
def get_conn():
    conn = _ConnWrapper()
    yield conn
    conn.commit()


def init_db():
    with get_conn() as conn:
        factor_cols = {row["name"] for row in conn.execute("PRAGMA table_info(factor_daily)")}
        if factor_cols and "scan_run_id" not in factor_cols:
            conn.execute("DROP TABLE factor_daily")
        conn.executescript(SCHEMA)


def upsert_watchlist(rows: list[dict]):
    """rows must include a `rank` field (seed-file position, ~market-cap
    order) — get_watchlist() orders by it so the fundamentals-refresh
    budget prioritizes the highest-ranked stocks."""
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO watchlist (symbol, sector, rank, active) VALUES (:symbol, :sector, :rank, 1)
               ON CONFLICT(symbol) DO UPDATE SET sector=excluded.sector, rank=excluded.rank, active=1""",
            rows,
        )


def set_active_symbols(symbols: list[str]):
    """Marks exactly `symbols` as active=1 and everyone else active=0. A
    single IN (...) statement rather than one UPDATE per symbol — the only
    executemany() call site in this file that isn't an INSERT, so it isn't
    covered by _ConnWrapper.executemany's VALUES-batching rewrite."""
    with get_conn() as conn:
        conn.execute("UPDATE watchlist SET active = 0")
        if symbols:
            placeholders = ",".join("?" * len(symbols))
            conn.execute(f"UPDATE watchlist SET active = 1 WHERE symbol IN ({placeholders})", symbols)


def set_upstox_instrument_key(symbol: str, instrument_key: str, company_name: str | None = None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE watchlist SET upstox_instrument_key=?, company_name=? WHERE symbol=?",
            (instrument_key, company_name, symbol),
        )


def get_watchlist() -> list[Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM watchlist WHERE active=1 ORDER BY rank"
        ).fetchall()


def get_last_price_date(symbol: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(date) AS d FROM price_daily WHERE symbol=?", (symbol,)
        ).fetchone()
        return row["d"] if row and row["d"] else None


def insert_price_rows(symbol: str, rows: list[dict]):
    if not rows:
        return
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO price_daily (symbol, date, open, high, low, close, volume, delivery_pct)
               VALUES (:symbol, :date, :open, :high, :low, :close, :volume, :delivery_pct)
               ON CONFLICT(symbol, date) DO UPDATE SET
                 open=excluded.open, high=excluded.high, low=excluded.low,
                 close=excluded.close, volume=excluded.volume,
                 delivery_pct=excluded.delivery_pct""",
            [{**r, "symbol": symbol} for r in rows],
        )


def get_price_df(symbol: str) -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM price_daily WHERE symbol=? ORDER BY date", conn.raw, params=(symbol,)
        )
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    return df


def get_latest_fundamentals(symbol: str) -> Row | None:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM fundamentals_quarterly WHERE symbol=?
               ORDER BY as_of_date DESC LIMIT 1""",
            (symbol,),
        ).fetchone()


def insert_fundamentals(symbol: str, data: dict, as_of_date: str | None = None):
    as_of_date = as_of_date or date.today().isoformat()
    row = {"symbol": symbol, "as_of_date": as_of_date, **data}
    cols = ", ".join(row.keys())
    placeholders = ", ".join(f":{k}" for k in row.keys())
    with get_conn() as conn:
        conn.execute(
            f"""INSERT INTO fundamentals_quarterly ({cols}) VALUES ({placeholders})
                ON CONFLICT(symbol, as_of_date) DO NOTHING""",
            row,
        )


def create_scan_run(
    trade_date: str, symbols_scanned: int, gates_passed: int, errors: list[str], watchlist_limit: int
) -> int:
    """One row per Scan click — the history index."""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO scan_runs (scan_timestamp, trade_date, symbols_scanned, gates_passed, errors,
                                       watchlist_limit)
               VALUES (datetime('now'), ?, ?, ?, ?, ?)""",
            (trade_date, symbols_scanned, gates_passed, "; ".join(errors) if errors else None, watchlist_limit),
        )
        return cur.lastrowid


def save_factor_rows(scan_run_id: int, rows: list[dict]):
    """Append-only: every scan_run_id's rows are distinct and never
    overwritten, so past scans stay browsable via get_run_results."""
    if not rows:
        return
    tagged = [{**r, "scan_run_id": scan_run_id} for r in rows]
    cols = list(tagged[0].keys())
    col_list = ", ".join(cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    with get_conn() as conn:
        conn.executemany(
            f"INSERT INTO factor_daily ({col_list}) VALUES ({placeholders})",
            tagged,
        )


def get_latest_run_id(trade_date: str | None = None, watchlist_limit: int | None = None) -> int | None:
    """watchlist_limit, when given, restricts to runs of that exact size —
    otherwise the homepage could show a stale Top 50 result while the size
    selector reads Top 500."""
    query = "SELECT id FROM scan_runs WHERE 1=1"
    params: list = []
    if trade_date:
        query += " AND trade_date = ?"
        params.append(trade_date)
    if watchlist_limit is not None:
        query += " AND watchlist_limit = ?"
        params.append(watchlist_limit)
    query += " ORDER BY id DESC LIMIT 1"
    with get_conn() as conn:
        row = conn.execute(query, params).fetchone()
        return row["id"] if row else None


def get_run_results(scan_run_id: int) -> list[Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT f.*, w.sector FROM factor_daily f
               JOIN watchlist w ON w.symbol = f.symbol
               WHERE f.scan_run_id = ? ORDER BY (f.rank IS NULL), f.rank""",
            (scan_run_id,),
        ).fetchall()


def get_scan_results(scan_date: str, watchlist_limit: int | None = None) -> list[Row]:
    """Latest run's results for a given date (and, when given, an exact
    watchlist size) — used by the home page."""
    run_id = get_latest_run_id(trade_date=scan_date, watchlist_limit=watchlist_limit)
    return get_run_results(run_id) if run_id else []


def list_scan_runs(limit: int = 100) -> list[Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT *, datetime(scan_timestamp, '+330 minutes') AS scan_timestamp_ist
               FROM scan_runs ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()


def get_scan_run(scan_run_id: int) -> Row | None:
    with get_conn() as conn:
        return conn.execute(
            """SELECT *, datetime(scan_timestamp, '+330 minutes') AS scan_timestamp_ist
               FROM scan_runs WHERE id = ?""",
            (scan_run_id,),
        ).fetchone()


def get_last_trigger_dates() -> dict[str, str]:
    """Most recent trigger_date per symbol, across all history — used to
    enforce a cooldown so the same stock isn't re-logged as a fresh entry
    every day its trigger condition happens to stay true."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT symbol, MAX(trigger_date) AS last_date FROM triggers GROUP BY symbol"
        ).fetchall()
        return {r["symbol"]: r["last_date"] for r in rows}


def record_triggers(scan_run_id: int, trigger_date: str, rows: list[dict]):
    """rows: symbol -> entry_price for every stock whose entry_trigger_today
    was True this scan. Deduped by (symbol, trigger_date) so re-scanning the
    same day is a no-op — the first-seen entry price for that day sticks."""
    if not rows:
        return
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO triggers (symbol, trigger_date, triggered_at, entry_price, scan_run_id)
               VALUES (:symbol, :trigger_date, datetime('now'), :entry_price, :scan_run_id)
               ON CONFLICT(symbol, trigger_date) DO NOTHING""",
            [
                {"symbol": symbol, "trigger_date": trigger_date, "entry_price": entry_price,
                 "scan_run_id": scan_run_id}
                for symbol, entry_price in rows.items()
            ],
        )


def get_triggers(limit: int = 200) -> list[Row]:
    """Current price is looked up live from price_daily's latest row per
    symbol, so it always reflects the most recent scan rather than being
    frozen at trigger time. highest_since_entry / lowest_since_entry are the
    intraday high/low (not just closing prices) across every session from
    trigger_date onward."""
    with get_conn() as conn:
        return conn.execute(
            """SELECT t.symbol, t.trigger_date, t.triggered_at,
                      datetime(t.triggered_at, '+330 minutes') AS triggered_at_ist,
                      t.entry_price,
                      w.upstox_instrument_key,
                      latest.close AS current_price,
                      (SELECT MAX(p.high) FROM price_daily p
                       WHERE p.symbol = t.symbol AND p.date > t.trigger_date) AS highest_since_entry,
                      (SELECT MIN(p.low) FROM price_daily p
                       WHERE p.symbol = t.symbol AND p.date > t.trigger_date) AS lowest_since_entry
               FROM triggers t
               LEFT JOIN watchlist w ON w.symbol = t.symbol
               LEFT JOIN (
                   SELECT symbol, close, date,
                          ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                   FROM price_daily
               ) latest ON latest.symbol = t.symbol AND latest.rn = 1
               ORDER BY t.triggered_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
