"""Community pool routes."""

from flask import Blueprint, request

from services.pool_service import get_pools, join_pool
from utils.responses import error, success
from utils.security import auth_required

bp = Blueprint('pools', __name__, url_prefix='/api/pools')


@bp.route('', methods=['GET'])
def pools():
    return success({'items': get_pools()})


@bp.route('/<int:pool_id>/join', methods=['POST'])
@auth_required
def join_pool_endpoint(pool_id):
    result, msg = join_pool(pool_id, request.json or {})
    if msg:
        return error(msg, 'VALIDATION_ERROR', 400)
    return success(result, 201)
