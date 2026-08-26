from datetime import date, datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db, pipeline, upstox_client
from app.config import BASE_DIR
from app.watchlist import get_watchlist_selection, is_valid_selection, watchlist_selection_options

app = FastAPI(title="NSE Screener")
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


@app.on_event("startup")
def _startup():
    db.init_db()


@app.get("/")
def index(request: Request, limit: str | None = None):
    if limit is not None and not is_valid_selection(limit):
        raise HTTPException(status_code=400, detail=f"limit must be one of {[v for v, _ in watchlist_selection_options()]}")
    authenticated = upstox_client.is_authenticated()

    # `limit` reflects the size selector on screen — passed explicitly via
    # ?limit= when the user changes the dropdown without scanning, so results
    # are always scoped to the size actually shown rather than falling back
    # to whatever size was most recently scanned.
    watchlist_limit = limit if limit is not None else get_watchlist_selection()

    today = date.today().isoformat()
    results = db.get_scan_results(today, watchlist_limit=watchlist_limit) if authenticated else []
    scan_timestamp_ist = None
    if results:
        run_id = db.get_latest_run_id(trade_date=today, watchlist_limit=watchlist_limit)
        run = db.get_scan_run(run_id) if run_id else None
        scan_timestamp_ist = run["scan_timestamp_ist"] if run else None
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "authenticated": authenticated,
            "results": results,
            "scan_date": today if results else None,
            "scan_timestamp_ist": scan_timestamp_ist,
            "watchlist_limit": watchlist_limit,
            "watchlist_limit_options": watchlist_selection_options(),
        },
    )


@app.get("/history")
def history(request: Request):
    authenticated = upstox_client.is_authenticated()
    runs = db.list_scan_runs() if authenticated else []
    return templates.TemplateResponse(
        request, "history.html", {"runs": runs, "authenticated": authenticated}
    )


@app.get("/history/{scan_run_id}")
def history_detail(request: Request, scan_run_id: int):
    authenticated = upstox_client.is_authenticated()
    run, results = None, []
    if authenticated:
        run = db.get_scan_run(scan_run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Scan run not found")
        results = db.get_run_results(scan_run_id)
    return templates.TemplateResponse(
        request,
        "history_detail.html",
        {"run": run, "results": results, "authenticated": authenticated},
    )


@app.get("/all-pass")
def all_pass(request: Request):
    authenticated = upstox_client.is_authenticated()
    rows = []
    live_prices_stale = True
    if authenticated:
        rows = [dict(r) for r in db.get_triggers()]
        if rows:
            client = upstox_client.get_client()
            try:
                live_prices = upstox_client.get_ltp(client, [r["symbol"] for r in rows])
                for r in rows:
                    if r["symbol"] in live_prices:
                        r["current_price"] = live_prices[r["symbol"]]
                live_prices_stale = False
            except Exception:
                pass  # fall back to each row's last-scan cached price

            # db.get_triggers() only counts daily OHLC from the day AFTER the
            # trigger day onward (date > trigger_date) — the trigger day
            # itself is excluded there because a plain daily bar can't tell
            # us whether its high/low happened before or after the exact
            # trigger moment. That day's own post-entry action still needs
            # to count, so it's filled in here from a live intraday-candle
            # call and merged with the post-trigger-day daily extremes
            # rather than replacing them.
            for r in rows:
                if r["upstox_instrument_key"] is None:
                    continue
                try:
                    trigger_day = datetime.strptime(r["trigger_date"], "%Y-%m-%d").date()
                    after_time = datetime.strptime(r["triggered_at_ist"], "%Y-%m-%d %H:%M:%S")
                    same_day_high, same_day_low = upstox_client.fetch_same_day_extremes_since(
                        client, r["upstox_instrument_key"], trigger_day, after_time
                    )
                    candidates_high = [v for v in (r["highest_since_entry"], same_day_high) if v is not None]
                    candidates_low = [v for v in (r["lowest_since_entry"], same_day_low) if v is not None]
                    r["highest_since_entry"] = max(candidates_high) if candidates_high else None
                    r["lowest_since_entry"] = min(candidates_low) if candidates_low else None
                except Exception:
                    pass  # leave whatever db.get_triggers() already gave us
    return templates.TemplateResponse(
        request,
        "all_pass.html",
        {
            "triggers": rows,
            "live_prices_stale": live_prices_stale,
            "authenticated": authenticated,
        },
    )


@app.post("/scan")
async def scan(request: Request, limit: str | None = None):
    if limit is not None and not is_valid_selection(limit):
        raise HTTPException(status_code=400, detail=f"limit must be one of {[v for v, _ in watchlist_selection_options()]}")
    outcome = await pipeline.run_scan(limit)

    if outcome["status"] == "auth_required":
        return templates.TemplateResponse(
            request,
            "_results.html",
            {"auth_required": True},
        )

    if outcome["status"] == "cancelled":
        return templates.TemplateResponse(
            request,
            "_results.html",
            {
                "cancelled": True,
                "errors": outcome.get("errors", []),
                "timing": outcome.get("timing", {}),
            },
        )

    return templates.TemplateResponse(
        request,
        "_results.html",
        {
            "results": outcome.get("results", []),
            "scan_date": outcome.get("date"),
            "scan_timestamp_ist": outcome.get("scan_timestamp_ist"),
            "errors": outcome.get("errors", []),
            "timing": outcome.get("timing", {}),
        },
    )


@app.post("/scan/cancel")
def scan_cancel():
    pipeline.request_cancel()
    return {"status": "cancel_requested"}
