"""HoReCa subscription routes."""

from flask import Blueprint, request

from services.subscription_service import (
    SubscriptionError,
    create_subscription,
    delete_subscription,
    list_subscriptions,
    subscription_calendar,
    update_subscription,
)
from utils.responses import error, success
from utils.security import auth_required

bp = Blueprint('subscriptions', __name__, url_prefix='/api/subscriptions')


@bp.route('', methods=['POST'])
@auth_required
def post_subscription():
    try:
        result = create_subscription(request.json or {})
        return success(result, 201)
    except SubscriptionError as e:
        return error(e.message, e.code, e.status)


@bp.route('', methods=['GET'])
@auth_required
def get_subscriptions():
    phone = request.args.get('phone') or request.headers.get('X-Phone', '')
    items = list_subscriptions(phone=phone)
    return success({'items': items, 'count': len(items)})


@bp.route('/<int:sub_id>', methods=['PUT'])
@auth_required
def put_subscription(sub_id):
    try:
        update_subscription(sub_id, request.json or {})
        return success({'id': sub_id, 'updated': True})
    except SubscriptionError as e:
        return error(e.message, e.code, e.status)


@bp.route('/<int:sub_id>', methods=['DELETE'])
@auth_required
def delete_subscription_endpoint(sub_id):
    delete_subscription(sub_id)
    return success({'id': sub_id, 'deleted': True})


@bp.route('/calendar', methods=['GET'])
@auth_required
def calendar():
    phone = request.args.get('phone') or request.headers.get('X-Phone', '')
    try:
        days = min(365, max(1, int(request.args.get('days') or 30)))
    except ValueError:
        days = 30
    data = subscription_calendar(phone=phone, days=days)
    return success(data)
