"""
Authentication & authorization helpers.

- Signed bearer tokens (HMAC-signed via itsdangerous, JWT-style claims).
- Mock OTP for development (production plugs into an SMS provider).
- `current_identity()` + `login_required` decorator for protected routes.

Authorization model
-------------------
Tokens carry the user's `id`, `phone`, `name` and `role`. Routes use
`g.current_user`. Ownership rules (a consumer cannot touch another's listings,
a farmer cannot read unrelated consumer data) are enforced in the route/service
layer by comparing the authenticated phone with the resource's phone.

For backward compatibility with the existing single-page frontend, when no
token is presented the request may still be identified by an explicit `phone`
field in DEVELOPMENT mode. In PRODUCTION mode a valid token is mandatory.
"""

import functools
import logging
import os
import random
import time

from flask import g, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

import config

log = logging.getLogger("farmbridge.security")

_serializer = URLSafeTimedSerializer(config.Config.SECRET_KEY)

# In-memory OTP store for development. Keyed by phone.
# Format: {phone: {"otp": str, "expires": float}}
_otp_store = {}


def make_token(user):
    """Create a signed token for a user dict (id/phone/name/role)."""
    payload = {
        "uid": user.get("id"),
        "phone": user.get("phone"),
        "name": user.get("name"),
        "role": user.get("role", "consumer"),
        "iat": int(time.time()),
    }
    return _serializer.dumps(payload)


def read_token(token):
    """Decode + validate a token. Returns payload dict or None."""
    if not token:
        return None
    try:
        return _serializer.loads(
            token, max_age=config.Config.TOKEN_TTL_SECONDS
        )
    except (BadSignature, SignatureExpired):
        return None


def issue_mock_otp(phone):
    """Development-only: mint a fixed OTP for a phone number."""
    otp = config.Config.MOCK_OTP
    _otp_store[phone] = {"otp": otp, "expires": time.time() + config.Config.OTP_TTL_SECONDS}
    return otp


def send_sms(phone, otp):
    """
    SMS provider hook.

    In production set SMS_PROVIDER to "module.path:function" — a callable
    `fn(phone, otp)` that dispatches the OTP (Twilio, MSG91, Textlocal, ...).
    Returns True if the message was dispatched, False otherwise.
    """
    provider = os.environ.get("SMS_PROVIDER", "").strip()
    if provider:
        try:
            mod_path, _, fn_name = provider.partition(":")
            module = __import__(mod_path, fromlist=[fn_name])
            fn = getattr(module, fn_name)
            fn(phone, otp)
            return True
        except Exception as exc:  # pragma: no cover
            log.error("SMS provider call failed: %s", exc)
            return False
    log.warning("No SMS provider configured — OTP for %s not sent.", phone)
    return False


def issue_otp(phone):
    """
    Issue an OTP for `phone`.

    Development: fixed mock OTP (returned + accepted).
    Production: random OTP dispatched via the SMS provider hook.
    Returns (otp, sent_bool).
    """
    if config.Config.ENVIRONMENT != "production":
        return issue_mock_otp(phone), True
    otp = "%06d" % random.randint(0, 999999)
    _otp_store[phone] = {
        "otp": otp,
        "expires": time.time() + config.Config.OTP_TTL_SECONDS,
    }
    sent = send_sms(phone, otp)
    return otp, sent


def verify_otp(phone, otp):
    """Verify an OTP. In development the mock OTP is also accepted."""
    otp = str(otp or "").strip()
    record = _otp_store.get(phone)
    if record and record["otp"] == otp and time.time() < record["expires"]:
        _otp_store.pop(phone, None)
        return True
    # Development convenience: accept the configured mock OTP directly.
    if config.Config.ENVIRONMENT != "production" and otp == config.Config.MOCK_OTP:
        return True
    return False


def _extract_token():
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):].strip()
    if header.startswith("Token "):
        return header[len("Token "):].strip()
    return None


def _phone_from_request():
    """Best-effort phone from body/query/form (used for dev fallback)."""
    data = request.get_json(silent=True) or {}
    phone = (
        data.get("phone")
        or data.get("consumer_phone")
        or data.get("buyer_phone")
        or request.args.get("phone")
        or (request.form or {}).get("phone")
    )
    return phone


def current_identity():
    """
    Resolve the authenticated user.

    Returns a user dict (id/phone/name/role) or None. Preference order:
    1. Valid bearer token.
    2. Development mode only: explicit `phone` in the request (legacy frontend).
    """
    from models.user import get_user_by_phone

    token = _extract_token()
    if token:
        payload = read_token(token)
        if payload:
            return {
                "id": payload.get("uid"),
                "phone": payload.get("phone"),
                "name": payload.get("name"),
                "role": payload.get("role", "consumer"),
            }

    if config.Config.ENVIRONMENT != "production":
        phone = _phone_from_request()
        if phone:
            user = get_user_by_phone(phone)
            if user:
                return {
                    "id": user.get("id"),
                    "phone": user.get("phone"),
                    "name": user.get("name"),
                    "role": user.get("role", "consumer"),
                }
    return None


def login_required(roles=None):
    """
    Decorator enforcing authentication (and optional roles) on a route.

    `roles` is a list/tuple/set of allowed roles; `None` means any logged-in
    user. On failure the response follows the standard error envelope.
    """
    from utils.responses import fail, AUTH_REQUIRED, AUTH_INVALID, FORBIDDEN

    allowed = set(roles) if roles else None

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_identity()
            if user is None:
                return fail(AUTH_REQUIRED, "Authentication required", status=401)
            if allowed is not None and user.get("role") not in allowed:
                return fail(FORBIDDEN, "You do not have permission for this action", status=403)
            g.current_user = user
            return fn(*args, **kwargs)

        return wrapper

    return decorator
