"""Miscellaneous routes: marketplace, mandi, grading, stats, health, db-info."""

from flask import Blueprint, jsonify, request

import config
from database import db
from models import listing as listing_model
from models import user as user_model
from models import consumer as consumer_model
from services import grading_service, mandi_service, marketplace_service
from utils.responses import ok, validation_error

bp = Blueprint("misc", __name__)


@bp.route("/api/market", methods=["GET"])
def market():
    """The consumer marketplace — always read from the central database."""
    return jsonify(marketplace_service.get_market())


@bp.route("/api/mandi-price", methods=["GET"])
def mandi_price():
    crop = request.args.get("crop", "").strip()
    location = request.args.get("location", "")
    farmer_price = request.args.get("farmer_price")
    try:
        farmer_price = float(farmer_price) if farmer_price else None
    except (TypeError, ValueError):
        farmer_price = None
    quote = mandi_service.get_mandi_quote(crop, location, farmer_price=farmer_price)
    return jsonify(quote)


@bp.route("/api/grade", methods=["POST"])
def grade_api():
    data = request.get_json(silent=True) or {}
    crop_name = data.get("crop_name", "")
    harvest_date = data.get("harvest_date", "")
    photo = data.get("photo")
    if not crop_name or not harvest_date:
        return validation_error("crop_name and harvest_date required")
    smart = grading_service.extract_crop_name_smart(crop_name)
    if smart:
        crop_name = smart
    result = grading_service.calculate_grade(crop_name, harvest_date, photo)
    result["success"] = True
    return jsonify(result)


@bp.route("/api/stats", methods=["GET"])
def stats():
    listings = listing_model.list_listings()
    total = len(listings)
    grade_a = sum(1 for l in listings if l.get("grade") == "A")
    total_value = round(
        sum((float(l.get("price_per_unit") or l.get("price") or 0) *
             int(l.get("quantity_available") or 0)) for l in listings), 2
    )
    return ok(data={
        "total_listings": total,
        "grade_a_count": grade_a,
        "total_value": total_value,
        "farmers": len({l.get("phone") for l in listings if l.get("phone")}),
        "consumers": consumer_model.count_consumers(),
    })


@bp.route("/api/db-info", methods=["GET"])
def db_info():
    info = db.engine_info()
    try:
        conn = db.get_conn()
        c = conn.cursor()
        counts = {}
        for t in ("listings", "consumers", "orders", "pools", "subscriptions"):
            c.execute("SELECT COUNT(*) AS n FROM " + t)
            row = c.fetchone()
            counts[t] = (dict(row) or {}).get("n", 0)
        conn.close()
        info["counts"] = counts
        info["ok"] = True
    except Exception as exc:
        info["ok"] = False
        info["error"] = str(exc)[:200]
    info["environment"] = config.Config.ENVIRONMENT
    return jsonify(info)


@bp.route("/api/health", methods=["GET"])
def health():
    return ok(data={
        "status": "ok",
        "environment": config.Config.ENVIRONMENT,
        "engine": db.ENGINE,
    })
