"""Listing routes — the farmer's produce catalogue (shared DB source of truth)."""

import logging
import re

from flask import Blueprint, g, jsonify, request

from database.schema import LISTING_STATUSES
from models import farmer as farmer_model
from models import listing as listing_model
from models import user as user_model
from services import grading_service, mandi_service
from utils import security
from utils.image_upload import save_image
from utils.responses import fail, not_found, ok, validation_error
from utils.validators import validate_name, validate_phone

bp = Blueprint("listings", __name__)
log = logging.getLogger("farmbridge.listings")


def _serialize_listing(l):
    if not l:
        return None
    out = dict(l)
    # The frontend still references `photo`; resolve it from image_url/legacy.
    out["photo"] = l.get("image_url") or l.get("photo") or ""
    out["unit"] = l.get("unit") or "Kg"
    return out


def _crop_name_from(raw):
    cleaned = re.sub(r"[^A-Za-z ]", "", (raw or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return None
    if len(cleaned.split()) > 3:
        return grading_service.extract_crop_name_smart(cleaned) or cleaned
    return cleaned


@bp.route("/api/listings", methods=["POST"])
def create_listing():
    data = request.get_json(silent=True) or {}
    log.info("Listing request: crop=%s phone=%s",
             (data.get("crop_name") or "")[:40], (data.get("phone") or "")[:12])

    required = ["crop_name", "harvest_date", "quantity", "price", "location",
                "farmer_name", "phone"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return validation_error("Missing field: %s" % missing[0])

    ok_name, msg_name = validate_name(data.get("farmer_name", ""))
    if not ok_name:
        return validation_error("Invalid farmer name: %s" % msg_name)
    ok_phone, msg_phone, digits = validate_phone(data.get("phone", ""))
    if not ok_phone:
        return validation_error("Invalid phone: %s" % msg_phone)

    # Ownership: a logged-in user may only list under their own phone.
    user = security.current_identity()
    if user and user.get("role") not in ("admin",) and user.get("phone") != digits:
        return fail("FORBIDDEN", "You can only create listings for your own account", status=403)

    crop_name = _crop_name_from(data.get("crop_name"))
    if not crop_name:
        return validation_error("Enter a valid crop name (letters only)")
    crop_name = crop_name.title()

    # Quantity → Kg (voice input like "5 quintal" is converted).
    qty_raw = str(data.get("quantity"))
    qty_kg = grading_service.extract_quantity_kg(qty_raw)
    if qty_kg is None:
        try:
            qty_kg = int(float(qty_raw))
        except (TypeError, ValueError):
            qty_kg = None
    if qty_kg is None or qty_kg <= 0:
        return validation_error("Quantity must be positive Kg")

    # Price → ₹/Kg.
    price_raw = str(data.get("price"))
    price_per_kg = grading_service.extract_price_per_kg(price_raw)
    if price_per_kg is None:
        try:
            price_per_kg = round(float(price_raw), 2)
        except (TypeError, ValueError):
            price_per_kg = None
    if price_per_kg is None or price_per_kg <= 0:
        return validation_error("Price must be positive ₹/Kg")

    # Image: save to uploads/ (validated), keep only the URL in the DB.
    image_url = ""
    raw_photo = data.get("photo") or data.get("image") or ""
    if raw_photo:
        image_url, img_err = save_image(raw_photo)
        if img_err:
            return validation_error(img_err)

    # AI grading (deterministic heuristic).
    harvest_raw = data.get("harvest_date")
    grade_info = grading_service.calculate_grade(crop_name, harvest_raw, raw_photo)

    # Mandi benchmark (clearly labeled demo data).
    mandi = mandi_service.get_mandi_quote(crop_name, data.get("location"),
                                          farmer_price=price_per_kg)

    # Ensure a user + farmer row exist (role promoted to 'farmer').
    user_row = user_model.get_or_create_user(data.get("farmer_name").strip(), digits,
                                             role="consumer")
    user_model.set_user_role(digits, "farmer")
    farmer = farmer_model.get_or_create_farmer(user_row["id"],
                                               location=data.get("location"),
                                               farm_name=data.get("farmer_name"))

    listing_id = listing_model.create_listing(
        farmer_id=farmer["id"],
        farmer_name=data.get("farmer_name").strip(),
        phone=digits,
        crop_name=crop_name,
        harvest_date=grade_info["harvest_date_parsed"],
        quantity="%d Kg" % qty_kg,
        quantity_total=qty_kg,
        quantity_available=qty_kg,
        unit="Kg",
        price=price_per_kg,
        price_per_unit=price_per_kg,
        location=(data.get("location") or "").strip(),
        city=(data.get("city") or "").strip(),
        image_url=image_url,
        photo=None,
        grade=grade_info["grade"],
        freshness_score=grade_info["freshness_score"],
        expiry_date=grade_info["expiry_date"],
        shelf_life=grade_info["shelf_life"],
        mandi_price=mandi["mandi_price"],
        platform_price=mandi["platform_price"],
        mandi_name=mandi["mandi_name"],
        status="active",
        voice_transcript=data.get("voice_transcript", ""),
        sold_kg=0,
    )

    payload = {
        "id": listing_id,
        "grade_info": grade_info,
        "mandi_price": mandi["mandi_price"],
        "platform_price": mandi["platform_price"],
        "farmer_price_per_kg": price_per_kg,
        "quantity_kg": qty_kg,
        "quantity_available": qty_kg,
        "unit": "Kg",
        "crop_name_extracted": crop_name,
        "mandi_name": mandi["mandi_name"],
        "image_url": image_url,
        "mandi_disclaimer": mandi["disclaimer"],
    }
    # `success` + top-level legacy fields for the existing frontend,
    # plus the standard `data` envelope for new clients.
    resp = {"success": True, **payload}
    resp["data"] = payload
    return jsonify(resp), 201


@bp.route("/api/listings", methods=["GET"])
def list_listings():
    rows = listing_model.list_listings()
    return jsonify([_serialize_listing(l) for l in rows])


@bp.route("/api/listings/<int:listing_id>", methods=["GET"])
def get_listing(listing_id):
    listing = listing_model.get_listing(listing_id)
    if not listing:
        return not_found("Listing not found")
    return ok(data=_serialize_listing(listing))


def _owned_listing_or_403(listing_id):
    listing = listing_model.get_listing(listing_id)
    if not listing:
        return listing, None
    user = security.current_identity()
    if not user:
        # No authenticated identity could be resolved (missing/invalid token and
        # — in development — no matching registered phone). Deny rather than
        # silently allowing an unauthenticated caller to mutate someone else's
        # listing.
        return listing, fail("AUTH_REQUIRED", "Authentication required", status=401)
    if user.get("role") != "admin" and user.get("phone") != listing.get("phone"):
        return listing, fail("FORBIDDEN", "You can only modify your own listings", status=403)
    return listing, None


@bp.route("/api/listings/<int:listing_id>", methods=["PUT"])
def update_listing(listing_id):
    listing, err = _owned_listing_or_403(listing_id)
    if err:
        return err
    if not listing:
        return not_found("Listing not found")

    data = request.get_json(silent=True) or {}
    fields = {}
    if "crop_name" in data:
        fields["crop_name"] = (_crop_name_from(data["crop_name"]) or "").title()
    if "quantity_total" in data or "quantity" in data:
        qty = grading_service.extract_quantity_kg(str(data.get("quantity_total") or data.get("quantity")))
        if qty and qty > 0:
            sold = int(listing.get("sold_kg") or 0)
            fields["quantity_total"] = qty
            fields["quantity_available"] = max(0, qty - sold)
            fields["quantity"] = "%d Kg" % qty
    if "price" in data or "price_per_unit" in data:
        price = grading_service.extract_price_per_kg(str(data.get("price_per_unit") or data.get("price")))
        if price and price > 0:
            fields["price_per_unit"] = price
            fields["price"] = price
    if "location" in data:
        fields["location"] = str(data["location"]).strip()
    if "city" in data:
        fields["city"] = str(data["city"]).strip()
    if "status" in data:
        if data["status"] not in LISTING_STATUSES:
            return validation_error("Invalid status")
        fields["status"] = data["status"]
    if "photo" in data and data["photo"]:
        image_url, img_err = save_image(data["photo"])
        if img_err:
            return validation_error(img_err)
        fields["image_url"] = image_url

    listing_model.update_listing(listing_id, **fields)
    return ok(data=_serialize_listing(listing_model.get_listing(listing_id)))


@bp.route("/api/listings/<int:listing_id>", methods=["DELETE"])
def delete_listing(listing_id):
    listing, err = _owned_listing_or_403(listing_id)
    if err:
        return err
    if not listing:
        return not_found("Listing not found")
    listing_model.delete_listing(listing_id)
    return ok(data={"deleted": True})


@bp.route("/api/listings/<int:listing_id>/status", methods=["PUT"])
def update_listing_status(listing_id):
    listing, err = _owned_listing_or_403(listing_id)
    if err:
        return err
    if not listing:
        return not_found("Listing not found")
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in LISTING_STATUSES:
        return validation_error("Invalid status")
    listing_model.update_listing(listing_id, status=new_status)
    return ok(data={"status": new_status})
