"""Stocks Screener API — kept separate from the BuyTheDip scanner routes.

GET /screener/snapshot[?since=<version>]
    Whole-universe snapshot; the frontend filters and sorts client-side.
    Pass the last `version` you received as `since` to get a tiny
    {"unchanged": true} reply when nothing new has been fetched.
"""

from flask import Blueprint, jsonify, request

from . import engine

screener_bp = Blueprint("screener", __name__, url_prefix="/screener")


@screener_bp.route("/snapshot")
def snapshot():
    since = request.args.get("since", type=int)
    payload = engine.get_snapshot(since)
    status = 503 if payload["status"] == "error" else 200
    resp = jsonify(payload)
    resp.headers["Cache-Control"] = "no-store"
    return resp, status
