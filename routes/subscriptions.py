"""HoReCa subscription routes."""

import re

from flask import Blueprint, jsonify, request

from services import subscription_service
from utils.responses import not_found, ok, validation_error

bp = Blueprint("subscriptions", __name__)


def _consumer_phone(data):
    return data.get("consumer_phone") or data.get("buyer_phone")


@bp.route("/api/subscriptions", methods=["POST"])
def create_subscription():
    data = request.get_json(silent=True) or {}
    phone = re.sub(r"\D", "", _consumer_phone(data) or "")
    try:
        qty = int(data.get("qty_kg") or 0)
    except (TypeError, ValueError):
        qty = 0
    try:
        listing_id = int(data.get("listing_id") or 0)
    except (TypeError, ValueError):
        listing_id = 0

    result, err = subscription_service.create_subscription(
        consumer_phone=phone,
        consumer_name=data.get("consumer_name") or data.get("buyer_name") or "",
        org_name=data.get("org_name") or "",
        listing_id=listing_id,
        qty_kg=qty,
        frequency=data.get("frequency") or "Weekly",
        weekdays=data.get("weekdays") or [],
        time_slot=data.get("time_slot", "6:00 AM - 8:00 AM"),
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
    )
    if err:
        return validation_error(err)
    return ok(data=result, status=201)


@bp.route("/api/subscriptions", methods=["GET"])
def list_subscriptions():
    phone = request.args.get("phone", "").strip()
    from models import subscription as sub_model
    subs = sub_model.list_subscriptions(phone or None)
    return jsonify(subs)


@bp.route("/api/subscriptions/<int:sub_id>", methods=["PUT"])
def update_subscription(sub_id):
    data = request.get_json(silent=True) or {}
    fields = {}
    if "active" in data:
        fields["active"] = 1 if data["active"] else 0
        fields["status"] = "active" if data["active"] else "paused"
    if "status" in data:
        fields["status"] = data["status"]
    if "qty_kg" in data:
        try:
            fields["qty_kg"] = int(data["qty_kg"])
        except (TypeError, ValueError):
            return validation_error("Invalid quantity")
    sub, err = subscription_service.update_subscription(sub_id, fields)
    if err:
        return not_found("Subscription not found")
    return ok(data=sub)


@bp.route("/api/subscriptions/<int:sub_id>", methods=["DELETE"])
def delete_subscription(sub_id):
    from models import subscription as sub_model
    if not sub_model.get_subscription(sub_id):
        return not_found("Subscription not found")
    subscription_service.cancel_subscription(sub_id)
    return ok(data={"cancelled": True})


@bp.route("/api/subscriptions/calendar", methods=["GET"])
def subscription_calendar():
    phone = request.args.get("phone", "").strip()
    try:
        days = int(request.args.get("days") or 30)
    except ValueError:
        days = 30
    days = max(1, min(days, 180))
    return jsonify(subscription_service.build_calendar(phone or None, days=days))
