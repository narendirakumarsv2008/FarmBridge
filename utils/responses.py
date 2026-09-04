"""
Consistent JSON API responses.

Success:
    { "success": true, "data": { ... } }

Error:
    { "success": false, "error": { "code": "...", "message": "..." } }

HTTP codes are set appropriately (200/201/400/401/403/404/409/500).
"""

from flask import jsonify

# Error codes used across the API.
VALIDATION_ERROR = "VALIDATION_ERROR"
AUTH_REQUIRED = "AUTH_REQUIRED"
AUTH_INVALID = "AUTH_INVALID"
FORBIDDEN = "FORBIDDEN"
NOT_FOUND = "NOT_FOUND"
CONFLICT = "CONFLICT"
INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
INVALID_TRANSITION = "INVALID_TRANSITION"
UPLOAD_ERROR = "UPLOAD_ERROR"
SERVER_ERROR = "SERVER_ERROR"
DB_ERROR = "DB_ERROR"


def ok(data=None, status=200, **extra):
    """Success envelope. `data` may be omitted for action-only endpoints."""
    payload = {"success": True}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return jsonify(payload), status


def created(data=None, **extra):
    return ok(data=data, status=201, **extra)


def fail(code, message, status=400, **extra):
    """Error envelope."""
    payload = {
        "success": False,
        "error": {"code": code, "message": message},
    }
    payload["error"].update(extra)
    return jsonify(payload), status


def validation_error(message, **extra):
    return fail(VALIDATION_ERROR, message, status=400, **extra)


def not_found(message="Resource not found"):
    return fail(NOT_FOUND, message, status=404)


def conflict(message, **extra):
    return fail(CONFLICT, message, status=409, **extra)
