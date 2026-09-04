"""Farmer portal routes."""

from datetime import datetime

from flask import Blueprint, g, request

from database.db import get_conn
from services.marketplace_service import get_farmer_listings
from services.order_service import OrderError, list_farmer_orders, update_order_status
from utils.responses import error, not_found, success, validation_error
from utils.security import auth_required

bp = Blueprint('farmer', __name__, url_prefix='/api/farmer')


@bp.route('/profile', methods=['GET'])
@auth_required
def get_farmer_profile():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM farmers WHERE user_id=? ORDER BY id DESC LIMIT 1',
                    (g.user_id,))
        row = cur.fetchone()
        if not row:
            cur.execute('SELECT * FROM users WHERE id=?', (g.user_id,))
            user = cur.fetchone()
            return success({'found': False, 'user': user or {}})
        return success({'found': True, 'profile': row})
    finally:
        conn.close()


@bp.route('/profile', methods=['PUT', 'POST'])
@auth_required
def save_farmer_profile():
    data = request.json or {}
    farm_name = (data.get('farm_name') or '').strip()
    location = (data.get('location') or '').strip()
    if not farm_name:
        return validation_error('Farm name is required')
    conn = get_conn()
    try:
        cur = conn.cursor()
        now = datetime.now().isoformat()
        cur.execute('SELECT * FROM farmers WHERE user_id=? ORDER BY id DESC LIMIT 1',
                    (g.user_id,))
        row = cur.fetchone()
        if row:
            cur.execute(
                """UPDATE farmers SET farm_name=?, location=?, city=?, state=?, pincode=?,
                   latitude=?, longitude=?, updated_at=? WHERE id=?""",
                (farm_name, location, data.get('city', ''), data.get('state', ''),
                 data.get('pincode', ''), data.get('latitude'), data.get('longitude'),
                 now, row['id']))
            fid = row['id']
        else:
            cur.execute(
                """INSERT INTO farmers
                (user_id,farm_name,location,city,state,pincode,latitude,longitude,
                 created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (g.user_id, farm_name, location, data.get('city', ''), data.get('state', ''),
                 data.get('pincode', ''), data.get('latitude'), data.get('longitude'),
                 now, now))
            fid = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return success({'farm_id': fid, 'farm_name': farm_name, 'location': location}, 201)


@bp.route('/listings', methods=['GET'])
@auth_required
def farmer_listings():
    return success({'items': get_farmer_listings(g.user_id)})


@bp.route('/orders', methods=['GET'])
@auth_required
def farmer_orders():
    orders = list_farmer_orders(g.user_id)
    return success({'items': orders, 'count': len(orders)})
