"""Farmer listing routes."""

from datetime import datetime

from flask import Blueprint, g, request

from database.db import get_conn
from services.crop_parser import clean_crop_name, extract_price_per_kg, extract_quantity_kg
from services.grading_service import calculate_grade
from config import config
from services.marketplace_service import (
    count_market_items,
    create_listing,
    get_listing,
    get_market_items,
)
from services.mandi_service import mandi_service
from utils.responses import error, forbidden, not_found, success, validation_error
from utils.security import auth_required

bp = Blueprint('listings', __name__, url_prefix='/api/listings')


def _owns_listing(conn, listing_id, user):
    cur = conn.cursor()
    cur.execute('SELECT * FROM listings WHERE id=?', (listing_id,))
    listing = cur.fetchone()
    if not listing:
        return None, None
    user_id = user.get('user_id')
    phone = user.get('phone')
    if listing.get('user_id') == user_id or (phone and listing.get('phone') == phone):
        return True, listing
    if user_id:
        cur.execute('SELECT id FROM farmers WHERE user_id=?', (user_id,))
        for r in cur.fetchall():
            if r['id'] == listing.get('farmer_id'):
                return True, listing
    return False, listing


@bp.route('', methods=['POST'])
@auth_required
def post_listing():
    data = request.json or {}
    user = {'user_id': g.get('user_id'), 'phone': g.get('phone'), 'name': ''}
    from services.auth_service import me as get_me
    profile = get_me(user['user_id'])
    if profile:
        user['name'] = profile.get('name', '')
    result = create_listing(data, user['user_id'], user['phone'], user['name'])
    if isinstance(result, tuple) and isinstance(result[1], int):
        return result
    # create_listing returns either a response tuple or a dict.
    if result.get('success'):
        return success(result, 201)
    if 'error' in result:
        return validation_error(result['error'])
    return error('Could not create listing', 'SERVER_ERROR', 500)


@bp.route('', methods=['GET'])
def get_listings():
    try:
        limit = max(1, min(500, int(request.args.get('limit', config.MARKET_PAGE_SIZE))))
    except ValueError:
        limit = config.MARKET_PAGE_SIZE
    try:
        offset = max(0, int(request.args.get('offset', 0)))
    except ValueError:
        offset = 0
    items = get_market_items(limit=limit, offset=offset)
    total = count_market_items()
    return success({
        'items': items,
        'count': len(items),
        'total': total,
        'has_more': offset + len(items) < total,
    })


@bp.route('/<int:listing_id>', methods=['GET'])
def get_listing_endpoint(listing_id):
    listing = get_listing(listing_id)
    if not listing:
        return not_found('Listing not found')
    return success(listing)


@bp.route('/<int:listing_id>', methods=['PUT'])
@auth_required
def update_listing(listing_id):
    data = request.json or {}
    conn = get_conn()
    try:
        ok, listing = _owns_listing(conn, listing_id, {'user_id': g.user_id, 'phone': g.phone})
        if ok is None:
            return not_found('Listing not found')
        if not ok:
            return forbidden('You cannot modify another farmer\'s listing')
        cur = conn.cursor()
        fields = []
        params = []

        if data.get('crop_name') is not None:
            crop = clean_crop_name(data.get('crop_name'))
            if not crop:
                return validation_error('Invalid crop name')
            fields.append('crop_name=?')
            params.append(crop)
        if data.get('quantity') is not None:
            qty = extract_quantity_kg(str(data.get('quantity')))
            if qty is None or qty <= 0:
                return validation_error('Quantity must be positive Kg')
            fields.append('quantity=?')
            fields.append('quantity_total=?')
            fields.append('quantity_available=?')
            params.extend(['%d Kg' % qty, qty, qty])
        if data.get('price') is not None:
            price = extract_price_per_kg(str(data.get('price')))
            if price is None or price <= 0:
                return validation_error('Price must be positive Rs/Kg')
            fields.append('price=?')
            fields.append('price_per_unit=?')
            fields.append('platform_price=?')
            params.extend([price, price, price])
        if data.get('location') is not None:
            fields.append('location=?')
            params.append(data.get('location'))
        if data.get('status') is not None:
            status = (data.get('status') or '').strip().lower()
            if status not in ('active', 'low_stock', 'sold_out', 'expired', 'inactive'):
                return validation_error('Invalid listing status')
            fields.append('status=?')
            params.append(status)
        if data.get('harvest_date'):
            grade = calculate_grade(listing.get('crop_name'), data.get('harvest_date'),
                                    listing.get('photo'))
            fields.append('harvest_date=?')
            fields.append('expiry_date=?')
            fields.append('shelf_life=?')
            fields.append('freshness_score=?')
            fields.extend([grade['harvest_date_parsed'], grade['expiry_date'],
                           grade['shelf_life'], grade['freshness_score']])

        if not fields:
            return validation_error('Nothing to update')
        fields.append('updated_at=?')
        params.append(datetime.now().isoformat())
        params.append(listing_id)
        cur.execute('UPDATE listings SET %s WHERE id=?' % ', '.join(fields), params)
        conn.commit()
    finally:
        conn.close()
    return success({'id': listing_id, 'updated': True})


@bp.route('/<int:listing_id>', methods=['DELETE'])
@auth_required
def delete_listing(listing_id):
    conn = get_conn()
    try:
        ok, listing = _owns_listing(conn, listing_id, {'user_id': g.user_id, 'phone': g.phone})
        if ok is None:
            return not_found('Listing not found')
        if not ok:
            return forbidden('You cannot delete another farmer\'s listing')
        cur = conn.cursor()
        cur.execute('UPDATE listings SET status=? WHERE id=?', ('inactive', listing_id))
        conn.commit()
    finally:
        conn.close()
    return success({'id': listing_id, 'deleted': True})


@bp.route('/<int:listing_id>/status', methods=['PUT'])
@auth_required
def update_listing_status(listing_id):
    data = request.json or {}
    conn = get_conn()
    try:
        ok, listing = _owns_listing(conn, listing_id, {'user_id': g.user_id, 'phone': g.phone})
        if ok is None:
            return not_found('Listing not found')
        if not ok:
            return forbidden('You cannot modify another farmer\'s listing')
        status = (data.get('status') or '').strip().lower()
        if status not in ('active', 'low_stock', 'sold_out', 'expired', 'inactive'):
            return validation_error('Invalid listing status')
        cur = conn.cursor()
        cur.execute('UPDATE listings SET status=?, updated_at=? WHERE id=?',
                    (status, datetime.now().isoformat(), listing_id))
        conn.commit()
    finally:
        conn.close()
    return success({'id': listing_id, 'status': status})
