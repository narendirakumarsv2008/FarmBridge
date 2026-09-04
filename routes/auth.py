"""Authentication routes: phone + OTP (with legacy name+phone alias)."""

from flask import Blueprint, g, request

from services import auth_service
from utils.responses import error, success
from utils.security import auth_required

bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@bp.route('/request-otp', methods=['POST'])
def request_otp():
    data = request.json or {}
    try:
        result = auth_service.request_otp(data.get('phone'), data.get('name'))
        return success(result, 200)
    except auth_service.AuthError as e:
        return error(e.message, e.code, e.status)


@bp.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    try:
        result = auth_service.verify_otp(data.get('phone'), data.get('otp'), data.get('name'))
        return success(result, 200)
    except auth_service.AuthError as e:
        return error(e.message, e.code, e.status)


@bp.route('/logout', methods=['POST'])
@auth_required
def logout():
    # JWT is stateless; clients discard the token. This endpoint is kept so the
    # UI can call a real logout and future server-side session revocation can
    # hook in.
    return success({'message': 'Logged out'})


@bp.route('/me', methods=['GET'])
@auth_required
def me():
    user = auth_service.me(g.get('user_id'))
    if not user:
        return error('User not found', 'NOT_FOUND', 404)
    return success(user)
