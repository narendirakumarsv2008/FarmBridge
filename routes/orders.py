"""Order routes: placement, listing, status transitions, tracking."""

from flask import Blueprint, g, jsonify, request

from database.schema import ORDER_FLOW, ORDER_STATUS_LABELS, ORDER_STATUSES
from models import order as order_model
from services import order_service
from utils import security
from utils.responses import fail, not_found, ok, validation_error

bp = Blueprint("orders", __name__)


def _consumer_phone(data):
    return data.get("consumer_phone") or data.get("buyer_phone") or data.get("phone")


@bp.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json(silent=True) or {}
    try:
        result = order_service.create_order(
            items=data.get("items") or [],
            consumer_phone=_consumer_phone(data),
            consumer_name=data.get("consumer_name") or data.get("buyer_name") or "",
            consumer_type=data.get("consumer_type") or data.get("buyer_type") or "Individual",
            address=data.get("address") or "",
            payment_method=data.get("payment_method", "UPI"),
            source=data.get("source", "individual"),
        )
    except order_service.OrderError as exc:
        return fail(exc.code, exc.message, status=exc.status)

    resp = {"success": True, **result}
    resp["data"] = result
    return jsonify(resp), 201


@bp.route("/api/orders", methods=["GET"])
def list_orders():
    phone = request.args.get("phone", "").strip()
    orders = order_service.list_orders(phone or None)
    return jsonify(orders)


@bp.route("/api/orders/<int:order_id>", methods=["GET"])
def get_order(order_id):
    detail = order_service.get_order_detail(order_id)
    if not detail:
        return not_found("Order not found")
    return ok(data=detail)


@bp.route("/api/orders/<int:order_id>/status", methods=["PUT"])
@security.login_required()
def set_status(order_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in ORDER_STATUSES:
        return validation_error("Invalid status")

    order = order_model.get_order(order_id)
    if not order:
        return not_found("Order not found")

    actor = security.current_identity()
    is_admin = actor.get("role") == "admin"

    # Farmers may only move orders that contain their own listings.
    if not is_admin:
        items = order_model.list_order_items(order_id)
        owns = any(i.get("farmer_phone") == actor.get("phone") for i in items)
        is_consumer_owner = order.get("consumer_phone") == actor.get("phone")
        # A consumer may only cancel their own order.
        if new_status == "CANCELLED" and is_consumer_owner:
            owns = True
        if not owns:
            return fail("FORBIDDEN", "You cannot modify this order", status=403)

    new_status, err = order_service.set_order_status(order_id, new_status)
    if err:
        return fail("INVALID_TRANSITION", err, status=409)

    detail = order_service.get_order_detail(order_id)
    return ok(data={
        "status": new_status,
        "status_label": ORDER_STATUS_LABELS.get(new_status, new_status),
        "flow": [ORDER_STATUS_LABELS[s] for s in ORDER_FLOW],
        "step_index": ORDER_FLOW.index(new_status) if new_status in ORDER_FLOW else 0,
        "order": detail,
    })


@bp.route("/api/orders/<int:order_id>/advance", methods=["PUT"])
def advance_order(order_id):
    """Legacy/demo endpoint: advance an order to the next linear step."""
    next_status = order_service.advance_order(order_id)
    if next_status is None:
        return not_found("Order not found")
    return jsonify({
        "success": True,
        "status": next_status,
        "status_label": ORDER_STATUS_LABELS.get(next_status, next_status),
        "step_index": ORDER_FLOW.index(next_status) if next_status in ORDER_FLOW else 0,
        "flow": [ORDER_STATUS_LABELS[s] for s in ORDER_FLOW],
    })
