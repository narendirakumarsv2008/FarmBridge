"""Farmer profile and farmer order-management routes."""

from flask import Blueprint, g, request

from models import farmer as farmer_model
from models import user as user_model
from services import order_service
from utils import security
from utils.responses import fail, ok, validation_error
from utils.validators import validate_phone

bp = Blueprint("farmer", __name__)


def _public(farmer):
    if not farmer:
        return None
    return {
        "id": farmer.get("id"),
        "user_id": farmer.get("user_id"),
        "farm_name": farmer.get("farm_name"),
        "location": farmer.get("location"),
        "city": farmer.get("city"),
        "state": farmer.get("state"),
        "pincode": farmer.get("pincode"),
        "latitude": farmer.get("latitude"),
        "longitude": farmer.get("longitude"),
    }


def _resolve_phone():
    """Phone from auth token, or (dev fallback) the request."""
    user = security.current_identity()
    if user and user.get("phone"):
        return user["phone"]
    return None


@bp.route("/api/farmer/profile", methods=["GET"])
@security.login_required()
def get_profile():
    phone = _resolve_phone()
    user = user_model.get_user_by_phone(phone) if phone else None
    farmer = farmer_model.get_farmer_by_user_id(user["id"]) if user else None
    return ok(data={"profile": _public(farmer)})


@bp.route("/api/farmer/profile", methods=["PUT"])
@security.login_required()
def save_profile():
    phone = _resolve_phone()
    user = user_model.get_user_by_phone(phone)
    if not user:
        return fail("AUTH_INVALID", "User not found", status=404)

    data = request.get_json(silent=True) or {}
    farmer = farmer_model.upsert_farmer(
        user["id"],
        farm_name=data.get("farm_name"),
        location=data.get("location"),
        city=data.get("city"),
        state=data.get("state"),
        pincode=data.get("pincode"),
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
    )
    return ok(data={"profile": _public(farmer)})


@bp.route("/api/farmer/orders", methods=["GET"])
@security.login_required()
def farmer_orders():
    """Orders that involve this farmer's listings."""
    phone = request.args.get("phone") or _resolve_phone()
    if not phone:
        return validation_error("phone required")
    ok_phone, msg, digits = validate_phone(phone)
    if not ok_phone:
        return validation_error("Invalid phone: %s" % msg)

    user = security.current_identity()
    if user and user.get("role") not in ("admin",) and user.get("phone") != digits:
        return fail("FORBIDDEN", "You can only view your own orders", status=403)

    orders = order_service.list_farmer_orders(digits)
    return ok(data=orders)
