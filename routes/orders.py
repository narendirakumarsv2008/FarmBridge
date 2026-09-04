"""Order routes."""

from flask import Blueprint, g, request

from services import auth_service
from services.order_service import (
    OrderError,
    advance_order,
    get_order,
    list_orders,
    place_order,
    update_order_status,
)
from utils.responses import error, success
from utils.security import auth_required

bp = Blueprint('orders', __name__, url_prefix='/api/orders')


@bp.route('', methods=['POST'])
@auth_required
def post_order():
    data = request.json or {}
    user = {'user_id': g.user_id, 'phone': g.phone}
    profile = auth_service.me(g.user_id)
    if profile:
        user['name'] = profile.get('name', '')
    if data.get('buyer_phone') is None:
        data['buyer_phone'] = g.phone
    if data.get('buyer_name') is None:
        data['buyer_name'] = user['name']
    try:
        return success(place_order(data, user), 201)
    except OrderError as e:
        return error(e.message, e.code, e.status)


@bp.route('', methods=['GET'])
@auth_required
def get_orders():
    phone = request.args.get('phone') or g.phone
    items = list_orders(phone=phone)
    return success({'items': items, 'count': len(items)})


@bp.route('/<int:order_id>', methods=['GET'])
@auth_required
def get_order_endpoint(order_id):
    order = get_order(order_id)
    if not order:
        return error('Order not found', 'NOT_FOUND', 404)
    return success(order)


@bp.route('/<int:order_id>/status', methods=['PUT'])
@auth_required
def change_order_status(order_id):
    data = request.json or {}
    try:
        order = update_order_status(order_id, data.get('status'))
        return success(order)
    except OrderError as e:
        return error(e.message, e.code, e.status)


@bp.route('/<int:order_id>/advance', methods=['PUT'])
@auth_required
def advance(order_id):
    try:
        order = advance_order(order_id)
        return success(order)
    except OrderError as e:
        return error(e.message, e.code, e.status)
