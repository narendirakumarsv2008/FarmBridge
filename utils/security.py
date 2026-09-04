"""Authentication / authorization helpers (JWT + decorators)."""

import functools
from datetime import datetime, timedelta, timezone

import jwt
from flask import g, request

from config import config
from utils.responses import forbidden, unauth


def generate_token(user_id, phone, role='consumer', extra=None):
    now = datetime.now(timezone.utc)
    payload = {
        'sub': str(user_id),
        'phone': phone,
        'role': role,
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(hours=config.JWT_EXPIRES_HOURS)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def decode_token(token):
    try:
        return jwt.decode(token, config.SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def bearer_token():
    header = request.headers.get('Authorization', '')
    if header.startswith('Bearer '):
        return header[7:].strip()
    return request.args.get('token') or request.headers.get('X-Auth-Token')


def current_token_payload():
    token = bearer_token()
    if not token:
        return None
    return decode_token(token)


def auth_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        payload = current_token_payload()
        if not payload:
            return unauth()
        g.auth = payload
        g.user_id = int(payload.get('sub', 0) or 0)
        g.phone = payload.get('phone')
        g.role = payload.get('role', 'consumer')
        return fn(*args, **kwargs)
    return wrapper


def roles_required(*roles):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            payload = current_token_payload()
            if not payload:
                return unauth()
            g.auth = payload
            g.user_id = int(payload.get('sub', 0) or 0)
            g.phone = payload.get('phone')
            g.role = payload.get('role', 'consumer')
            if g.role not in roles:
                return forbidden('Your account does not have access to this resource')
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def login_optional(fn):
    """Resolve auth when a token is present, but allow anonymous access."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        payload = current_token_payload()
        if payload:
            g.auth = payload
            g.user_id = int(payload.get('sub', 0) or 0)
            g.phone = payload.get('phone')
            g.role = payload.get('role', 'consumer')
        return fn(*args, **kwargs)
    return wrapper
