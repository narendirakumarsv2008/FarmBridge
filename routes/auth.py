"""Authentication routes: login (phone + OTP), verify OTP, me, logout."""

import logging

from flask import Blueprint, g, request

import config
from models import user as user_model
from utils import security
from utils.responses import fail, ok, validation_error
from utils.validators import validate_name, validate_phone

bp = Blueprint("auth", __name__)
log = logging.getLogger("farmbridge.auth")


def _login_flow(name, phone, otp=None):
    """Shared login logic. Returns (payload, status_code) or raises via fail."""
    ok_name, msg_name = validate_name(name)
    if not ok_name:
        return validation_error("Invalid name: %s" % msg_name)
    ok_phone, msg_phone, digits = validate_phone(phone)
    if not ok_phone:
        return validation_error("Invalid phone: %s" % msg_phone)

    user = user_model.get_or_create_user(name.strip(), digits, role="consumer")
    user = dict(user)

    is_dev = config.Config.ENVIRONMENT != "production"

    # OTP was supplied → verify it.
    if otp is not None and str(otp).strip():
        if not security.verify_otp(digits, otp):
            return fail("AUTH_INVALID", "Invalid or expired OTP", status=401)
        token = security.make_token(user)
        return ok(data={"token": token, "user": _public_user(user)})

    # No OTP yet.
    if is_dev:
        # Development: issue the mock OTP and (for demo convenience) return a
        # signed token right away. The OTP is included for transparency.
        mock_otp = security.issue_mock_otp(digits)
        token = security.make_token(user)
        return ok(data={
            "token": token,
            "user": _public_user(user),
            "otp": mock_otp,
            "otp_required": False,
            "note": "Development mode: mock OTP auto-accepted.",
        })
    # Production: dispatch a real OTP via the SMS provider, then require the
    # client to call /api/auth/verify-otp with the code.
    _otp, sent = security.issue_otp(digits)
    if not sent:
        return fail(
            "AUTH_REQUIRED",
            "SMS provider not configured — production login requires OTP via SMS",
            status=503,
        )
    return ok(data={"otp_required": True, "otp_sent": True}, status=202)


def _public_user(user):
    return {
        "id": user.get("id"),
        "name": user.get("name"),
        "phone": user.get("phone"),
        "role": user.get("role", "consumer"),
    }


@bp.route("/api/auth/login", methods=["POST"])
@bp.route("/api/login", methods=["POST"])  # legacy alias
def login():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")
    phone = data.get("phone", "")
    otp = data.get("otp")
    return _login_flow(name, phone, otp)


@bp.route("/api/auth/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json(silent=True) or {}
    phone = data.get("phone", "")
    otp = data.get("otp", "")
    ok_phone, msg_phone, digits = validate_phone(phone)
    if not ok_phone:
        return validation_error("Invalid phone: %s" % msg_phone)
    if not security.verify_otp(digits, otp):
        return fail("AUTH_INVALID", "Invalid or expired OTP", status=401)
    user = user_model.get_user_by_phone(digits)
    if not user:
        return fail("AUTH_INVALID", "User not found", status=404)
    token = security.make_token(dict(user))
    return ok(data={"token": token, "user": _public_user(dict(user))})


@bp.route("/api/auth/me", methods=["GET"])
@security.login_required()
def me():
    user = user_model.get_user_by_phone(g.current_user["phone"])
    if not user:
        return fail("AUTH_INVALID", "User not found", status=404)
    return ok(data=_public_user(dict(user)))


@bp.route("/api/auth/logout", methods=["POST"])
def logout():
    # Stateless tokens: the client discards its token.
    return ok(data={"logged_out": True})
