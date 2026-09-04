"""Legacy compatibility routes.

Kept temporarily so the original frontend and any tests that still call
`POST /api/login` keep working while terminology and auth move to Consumer.
"""

from flask import Blueprint, request

from services import auth_service
from utils.responses import error, success

bp = Blueprint('legacy', __name__)


@bp.route('/api/login', methods=['POST'])
def legacy_login():
    data = request.json or {}
    try:
        result = auth_service.legacy_login(data.get('name', ''), data.get('phone', ''))
        return success(result, 200)
    except auth_service.AuthError as e:
        return error(e.message, e.code, e.status)
