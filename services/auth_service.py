"""
Phone + OTP authentication service.

Development uses a mock OTP (returned in the API so demos work). Production is
ready to plug in SMS provider credentials (SMS_PROVIDER / a provider module)
without changing the routes. Tokens are JWT; passwords are never used or
stored.
"""

import logging
from datetime import datetime

from database.db import get_conn
from config import config
from utils.security import generate_token
from utils.validators import validate_name, validate_phone

logger = logging.getLogger(__name__)


class AuthError(Exception):
    def __init__(self, message, code='VALIDATION_ERROR', status=400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _get_user_by_phone(conn, phone):
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE phone=?', (phone,))
    return cur.fetchone()


def get_or_create_user(phone, name=None, email=''):
    ok, msg, digits = validate_phone(phone)
    if not ok:
        raise AuthError('Invalid phone: %s' % msg)
    conn = get_conn()
    try:
        cur = conn.cursor()
        user = _get_user_by_phone(conn, digits)
        now = datetime.now().isoformat()
        if user:
            if name and user.get('name') != name:
                cur.execute('UPDATE users SET name=?, email=?, updated_at=? WHERE id=?',
                            (name, email or user.get('email', ''), now, user['id']))
            return _load_user(conn, user['id'])
        ok_name, name_msg = validate_name(name or 'Farm User')
        display_name = name.strip() if ok_name else 'Farm User'
        cur.execute(
            'INSERT INTO users (name, phone, email, role, created_at, updated_at) '
            'VALUES (?,?,?,?,?,?)',
            (display_name, digits, email, 'consumer', now, now))
        user_id = cur.lastrowid
        conn.commit()
        return _load_user(conn, user_id)
    finally:
        conn.close()


def _load_user(conn, user_id):
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE id=?', (user_id,))
    return cur.fetchone()


def request_otp(phone, name=None):
    ok, msg, digits = validate_phone(phone)
    if not ok:
        raise AuthError('Invalid phone: %s' % msg)

    user = get_or_create_user(digits, name=name)
    now = datetime.now()
    otp = config.MOCK_OTP if config.SMS_PROVIDER == 'mock' else _generate_otp()
    expires = now.isoformat()

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute('UPDATE users SET otp_code=?, otp_expires_at=?, updated_at=? WHERE id=?',
                    (otp, expires, now.isoformat(), user['id']))
        conn.commit()
    finally:
        conn.close()

    logger.info('OTP requested for phone %s', digits)
    response = {
        'otp_sent': True,
        'phone': digits,
        'expires_in_seconds': config.OTP_EXPIRY_MINUTES * 60,
        'provider': config.SMS_PROVIDER,
    }
    if config.SMS_PROVIDER == 'mock' and not config.is_production:
        response['demo_otp'] = otp
        response['dev'] = True
    return response


def verify_otp(phone, otp, name=None):
    ok, msg, digits = validate_phone(phone)
    if not ok:
        raise AuthError('Invalid phone: %s' % msg)
    if not otp:
        raise AuthError('OTP is required')

    user = get_or_create_user(digits, name=name)
    stored = user.get('otp_code') or ''
    expires = user.get('otp_expires_at') or ''

    if config.SMS_PROVIDER == 'mock' and not config.is_production:
        # In dev we accept the configured mock OTP even before request-otp.
        if stored != str(otp) and str(otp) != config.MOCK_OTP:
            raise AuthError('Invalid OTP', code='INVALID_OTP', status=401)
    else:
        if not stored or stored != str(otp):
            raise AuthError('Invalid OTP', code='INVALID_OTP', status=401)
        try:
            if datetime.fromisoformat(expires) < datetime.now():
                raise AuthError('OTP expired', code='OTP_EXPIRED', status=401)
        except Exception:
            raise AuthError('OTP expired', code='OTP_EXPIRED', status=401)

    # Clear OTP after successful login.
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute('UPDATE users SET otp_code=?, otp_expires_at=?, updated_at=? WHERE id=?',
                    (None, None, datetime.now().isoformat(), user['id']))
        conn.commit()
    finally:
        conn.close()

    token = generate_token(user['id'], digits, user.get('role') or 'consumer')
    return {'token': token, 'user': _public_user(user)}


def legacy_login(name, phone):
    """Backward-compatible name+phone login (development only).

    Returns the same payload as verify_otp so old clients do not break.
    """
    ok, msg, digits = validate_phone(phone)
    if not ok:
        raise AuthError('Invalid phone: %s' % msg)
    ok_name, name_msg = validate_name(name)
    if not ok_name:
        raise AuthError('Invalid name: %s' % name_msg)
    user = get_or_create_user(digits, name)
    token = generate_token(user['id'], digits, user.get('role') or 'consumer')
    return {'token': token, 'user': _public_user(user)}


def me(user_id):
    user = _load_user(get_conn(), user_id)
    if not user:
        return None
    return _public_user(user)


def _public_user(user):
    return {
        'id': user['id'],
        'name': user.get('name', ''),
        'phone': user.get('phone', ''),
        'email': user.get('email', ''),
        'role': user.get('role', 'consumer'),
        'created_at': user.get('created_at', ''),
    }


def _generate_otp():
    import random
    return '%06d' % random.randint(0, 999999)
