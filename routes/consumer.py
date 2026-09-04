"""Consumer profile routes (the old "/api/buyer/*" paths remain as aliases)."""

import re

from flask import Blueprint, g, request

from models import consumer as consumer_model
from utils import security
from utils.responses import ok, validation_error
from utils.validators import (
    validate_address,
    validate_consumer_type,
    validate_email,
    validate_name,
    validate_phone,
    validate_pincode,
)

bp = Blueprint("consumer", __name__)


def _public(profile):
    if not profile:
        return None
    return {
        "id": profile.get("id"),
        "phone": profile.get("phone"),
        "name": profile.get("name"),
        "email": profile.get("email"),
        "consumer_type": profile.get("consumer_type"),
        "delivery_address": profile.get("delivery_address"),
        "landmark": profile.get("landmark"),
        "organization_name": profile.get("organization_name"),
        "city": profile.get("city"),
        "state": profile.get("state"),
        "pincode": profile.get("pincode"),
        "latitude": profile.get("latitude"),
        "longitude": profile.get("longitude"),
    }


def _normalize_payload(data):
    """Accept both consumer_* and legacy buyer_* keys."""
    return {
        "name": data.get("name"),
        "phone": re.sub(r"\D", "", str(data.get("phone") or "")),
        "email": data.get("email"),
        "consumer_type": data.get("consumer_type") or data.get("buyer_type"),
        "delivery_address": data.get("delivery_address") or data.get("address"),
        "landmark": data.get("landmark"),
        "organization_name": data.get("organization_name") or data.get("org_name"),
        "city": data.get("city"),
        "state": data.get("state"),
        "pincode": data.get("pincode"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
    }


def _validate_profile(d):
    ok, msg = validate_name(d.get("name") or "")
    if not ok:
        return validation_error(msg)
    ok, msg, digits = validate_phone(d.get("phone"))
    if not ok:
        return validation_error(msg)
    d["phone"] = digits
    ok, msg = validate_email(d.get("email") or "")
    if not ok:
        return validation_error(msg)
    ok, msg = validate_address(d.get("delivery_address") or "")
    if not ok:
        return validation_error(msg)
    ok, msg = validate_consumer_type(d.get("consumer_type") or "")
    if not ok:
        return validation_error(msg)
    d["consumer_type"] = msg
    ok, msg = validate_pincode(d.get("pincode"))
    if not ok:
        return validation_error(msg)
    return None


@bp.route("/api/consumer/profile", methods=["GET"])
@bp.route("/api/buyer/profile", methods=["GET"])  # deprecated alias
def get_profile():
    phone = (request.args.get("phone") or "").strip()
    if not phone:
        return validation_error("phone required")
    profile = consumer_model.get_consumer(re.sub(r"\D", "", phone))
    if not profile:
        return ok(data={"found": False, "profile": None})
    return ok(data={"found": True, "profile": _public(profile)})


@bp.route("/api/consumer/profile", methods=["POST"])
@bp.route("/api/buyer/profile", methods=["POST"])  # deprecated alias
def save_profile():
    data = request.get_json(silent=True) or {}
    d = _normalize_payload(data)
    if not d["name"] or not d["phone"]:
        return validation_error("Name and phone come from login and are required")
    err = _validate_profile(d)
    if err:
        return err

    # Optional ownership check: a logged-in user may only write their own profile.
    user = security.current_identity()
    if user and user.get("role") not in ("admin",) and user.get("phone") != d["phone"]:
        return fail_forbidden()

    profile = consumer_model.upsert_consumer(
        d["phone"],
        name=d["name"],
        email=d["email"],
        consumer_type=d["consumer_type"],
        delivery_address=d["delivery_address"],
        landmark=d["landmark"],
        organization_name=d["organization_name"],
        city=d["city"],
        state=d["state"],
        pincode=d["pincode"],
        latitude=d["latitude"],
        longitude=d["longitude"],
    )
    return ok(data={"profile": _public(profile)})


@bp.route("/api/consumer/profile", methods=["PUT"])
def update_profile():
    data = request.get_json(silent=True) or {}
    d = _normalize_payload(data)
    if not d["phone"]:
        return validation_error("phone required")
    user = security.current_identity()
    if user and user.get("role") not in ("admin",) and user.get("phone") != d["phone"]:
        return fail_forbidden()
    existing = consumer_model.get_consumer(d["phone"])
    if not existing:
        return fail_not_found()
    # merge: keep existing values for fields not provided
    merged = {
        "name": d.get("name") or existing.get("name"),
        "email": d.get("email") or existing.get("email"),
        "consumer_type": d.get("consumer_type") or existing.get("consumer_type"),
        "delivery_address": d.get("delivery_address") or existing.get("delivery_address"),
        "landmark": d.get("landmark") if d.get("landmark") is not None else existing.get("landmark"),
        "organization_name": d.get("organization_name") if d.get("organization_name") is not None else existing.get("organization_name"),
        "city": d.get("city") if d.get("city") is not None else existing.get("city"),
        "state": d.get("state") if d.get("state") is not None else existing.get("state"),
        "pincode": d.get("pincode") if d.get("pincode") is not None else existing.get("pincode"),
        "latitude": d.get("latitude") if d.get("latitude") is not None else existing.get("latitude"),
        "longitude": d.get("longitude") if d.get("longitude") is not None else existing.get("longitude"),
    }
    err = _validate_profile({"phone": d["phone"], **merged})
    if err:
        return err
    profile = consumer_model.upsert_consumer(d["phone"], **merged)
    return ok(data={"profile": _public(profile)})


def fail_forbidden():
    from utils.responses import fail, FORBIDDEN
    return fail(FORBIDDEN, "You can only modify your own profile", status=403)


def fail_not_found():
    from utils.responses import fail, NOT_FOUND
    return fail(NOT_FOUND, "Consumer profile not found", status=404)
