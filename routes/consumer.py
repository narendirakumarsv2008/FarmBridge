"""Consumer profile routes (Consumer Portal).

`/api/buyer/profile` is retained as a deprecated compatibility alias so older
frontends continue working while the app migrates to Consumer naming.
"""

from flask import Blueprint, g, request

from services.consumer_service import ConsumerError, get_consumer_by_phone, save_consumer_profile
from utils.responses import error, success
from utils.security import auth_required

bp = Blueprint('consumer', __name__, url_prefix='/api/consumer')


def _profile_payload(data):
    # Accept both consumer and legacy buyer field names during migration.
    payload = dict(data or {})
    if 'delivery_address' in payload and 'address' not in payload:
        payload['address'] = payload['delivery_address']
    if 'consumer_type' not in payload and 'buyer_type' in payload:
        payload['consumer_type'] = payload['buyer_type']
    return payload


@bp.route('/profile', methods=['GET'])
@auth_required
def get_profile():
    phone = (request.args.get('phone') or g.get('phone') or '').strip()
    if not phone:
        return error('phone required', 'VALIDATION_ERROR', 400)
    profile = get_consumer_by_phone(phone)
    if not profile:
        return success({'found': False})
    return success({'found': True, 'profile': profile})


@bp.route('/profile', methods=['POST'])
@auth_required
def post_profile():
    data = _profile_payload(request.json or {})
    user = {'user_id': g.get('user_id')}
    try:
        profile = save_consumer_profile(data, user)
        return success({'profile': profile}, 201)
    except ConsumerError as e:
        return error(e.message, e.code, e.status)


@bp.route('/profile', methods=['PUT'])
@auth_required
def put_profile():
    return post_profile()


# ---- Deprecated compatibility alias ----

alias_bp = Blueprint('consumer_alias', __name__, url_prefix='/api/buyer')


@alias_bp.route('/profile', methods=['GET'])
def get_buyer_profile():
    phone = (request.args.get('phone') or '').strip()
    if not phone:
        return error('phone required', 'VALIDATION_ERROR', 400)
    profile = get_consumer_by_phone(phone)
    if not profile:
        return success({'found': False})
    # Legacy shape expected by older frontends.
    legacy = dict(profile)
    legacy['buyer_type'] = (profile.get('consumer_type') or '').capitalize()
    return success({'found': True, 'profile': legacy})


@alias_bp.route('/profile', methods=['POST'])
@auth_required
def post_buyer_profile():
    data = _profile_payload(request.json or {})
    user = {'user_id': g.get('user_id')}
    try:
        profile = save_consumer_profile(data, user)
        legacy = dict(profile)
        legacy['buyer_type'] = (profile.get('consumer_type') or '').capitalize()
        return success({'profile': legacy}, 201)
    except ConsumerError as e:
        return error(e.message, e.code, e.status)
