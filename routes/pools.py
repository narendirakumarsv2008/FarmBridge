"""Community pool-buy routes."""

import re

from flask import Blueprint, jsonify, request

from services import pool_service
from utils.responses import ok, validation_error

bp = Blueprint("pools", __name__)


@bp.route("/api/pools", methods=["GET"])
def get_pools():
    return jsonify(pool_service.get_pools())


@bp.route("/api/pools/<int:pool_id>/join", methods=["POST"])
def join_pool(pool_id):
    data = request.get_json(silent=True) or {}
    try:
        qty = int(data.get("qty_kg") or 0)
    except (TypeError, ValueError):
        qty = 0
    if qty <= 0:
        return validation_error("Enter quantity in Kg to pool")

    phone = re.sub(r"\D", "",
                   str(data.get("consumer_phone") or data.get("buyer_phone") or ""))
    name = data.get("consumer_name") or data.get("buyer_name") or ""
    org = data.get("org_name") or ""

    pool, err = pool_service.join_pool(pool_id, phone, name, org, qty)
    if err:
        return validation_error(err)
    return ok(data={"pool": pool})
