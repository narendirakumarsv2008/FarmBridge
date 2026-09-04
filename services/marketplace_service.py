"""Shared Farmer -> Consumer marketplace service.

This is the single source of truth for crop listings. Farmer listing creation
writes here; the consumer marketplace reads here. No frontend-only or
localStorage marketplace data is used.
"""

from datetime import datetime, timedelta

from database.db import begin, get_conn
from services.crop_parser import clean_crop_name, extract_price_per_kg, extract_quantity_kg
from services.grading_service import calculate_grade
from services.mandi_service import mandi_service
from utils.responses import conflict, validation_error
from utils.uploads import save_base64_image

VALID_LISTING_STATUSES = ('active', 'low_stock', 'sold_out', 'expired', 'inactive')


def _row_dict(r):
    if r is None:
        return None
    if isinstance(r, dict):
        return {k: v for k, v in r.items()}
    return {k: r[k] for k in r.keys()}


def _to_float(v, default=0.0):
    try:
        val = round(float(v), 2)
    except (TypeError, ValueError):
        return default
    if abs(val - round(val)) < 1e-9 and abs(val) < 1e9:
        return int(val)
    return val


def row_to_listing(row):
    listing = _row_dict(row) or {}
    listing['quantity_total'] = _to_float(
        listing.get('quantity_total') or listing.get('quantity'), 0)
    if listing['quantity_total'] <= 0:
        import re
        digits = re.sub(r'\D', '', str(listing.get('quantity') or ''))
        listing['quantity_total'] = _to_float(digits, 0)
    listing['quantity_available'] = _to_float(
        listing.get('quantity_available'), listing['quantity_total'])
    listing['price_per_unit'] = _to_float(
        listing.get('price_per_unit') or listing.get('price') or listing.get('platform_price'), 0)
    listing['sold_kg'] = _to_float(listing.get('sold_kg'), 0)
    listing['mandi_price'] = _to_float(listing.get('mandi_price'), 0)
    listing['photo'] = listing.get('image_url') or listing.get('photo') or ''
    listing['unit'] = listing.get('unit') or 'Kg'
    listing['status'] = (listing.get('status') or 'active').strip().lower()
    return listing


def enrich_listing(l):
    listing = row_to_listing(l)
    base = listing.get('price_per_unit') or 0
    live = round(base, 2)
    avail = max(0, listing.get('quantity_available') or 0)
    total = max(0, listing.get('quantity_total') or 0)
    if total < avail:
        total = avail

    harvest = listing.get('harvest_date') or ''
    try:
        hd = datetime.strptime(str(harvest)[:10], '%Y-%m-%d')
        age_days = max(0, (datetime.now() - hd).days)
        harvest_display = hd.strftime('%d %b %Y')
    except Exception:
        age_days = 0
        harvest_display = harvest

    if age_days <= 0:
        freshness_label = 'Harvested today'
    elif age_days == 1:
        freshness_label = 'Harvested yesterday'
    else:
        freshness_label = 'Harvested %d days ago' % age_days

    mandi = listing.get('mandi_price') or 0
    listing.update({
        'live_price': live,
        'price_change_pct': 0.0,  # no fake daily drift; authoritative price only
        'available_kg': avail,
        'total_kg': total,
        'stock_pct': round((avail / total) * 100) if total else 0,
        'harvest_display': harvest_display,
        'harvest_age_days': age_days,
        'freshness_label': freshness_label,
        'mandi_price': mandi,
        'savings_vs_mandi': round(mandi - live, 2) if mandi else 0,
        'unit': listing.get('unit') or 'Kg',
        'sold_out': avail <= 0,
        'low_stock': avail > 0 and total > 0 and (avail / total) < 0.25,
    })
    return listing


def get_market_items(limit=None, offset=0):
    conn = get_conn()
    try:
        cur = conn.cursor()
        params = []
        where = "status NOT IN ('inactive','expired')"
        sql = "SELECT * FROM listings WHERE %s ORDER BY created_at DESC" % where
        if limit is not None:
            sql += ' LIMIT ? OFFSET ?'
            params.extend([limit, offset])
        cur.execute(sql, params)
        rows = cur.fetchall()
        return [enrich_listing(r) for r in rows]
    finally:
        conn.close()


def count_market_items():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS n FROM listings WHERE status NOT IN ('inactive','expired')")
        return (cur.fetchone() or {}).get('n', 0) or 0
    finally:
        conn.close()


def get_listing(listing_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM listings WHERE id=?', (listing_id,))
        row = cur.fetchone()
        return row_to_listing(row) if row else None
    finally:
        conn.close()


def _ensure_farmer(conn, user_id, payload):
    cur = conn.cursor()
    cur.execute('SELECT * FROM farmers WHERE user_id=? ORDER BY id DESC LIMIT 1', (user_id,))
    farmer = cur.fetchone()
    if farmer:
        cur.execute(
            'UPDATE farmers SET farm_name=?, location=?, city=?, updated_at=? WHERE id=?',
            (payload.get('farm_name') or farmer.get('farm_name'),
             payload.get('location') or farmer.get('location'),
             payload.get('city') or farmer.get('city'),
             datetime.now().isoformat(), farmer['id']))
        return farmer['id']
    cur.execute(
        'INSERT INTO farmers (user_id, farm_name, location, city, state, pincode, '
        'latitude, longitude, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
        (user_id, payload.get('farm_name') or '',
         payload.get('location') or '', payload.get('city') or '',
         payload.get('state') or '', payload.get('pincode') or '',
         payload.get('latitude'), payload.get('longitude'),
         datetime.now().isoformat(), datetime.now().isoformat()))
    return cur.lastrowid


def create_listing(payload, user_id, user_phone, user_name):
    required = ['crop_name', 'harvest_date', 'quantity', 'price', 'location']
    for field in required:
        if not payload.get(field):
            return validation_error('Missing field: %s' % field)

    crop_name = clean_crop_name(payload.get('crop_name'))
    if not crop_name:
        return validation_error('Enter a valid crop name (letters only)')

    qty_kg = None
    if payload.get('quantity') is not None:
        qty_kg = extract_quantity_kg(str(payload.get('quantity')))
    if qty_kg is None:
        try:
            qty_kg = int(float(payload.get('quantity')))
        except (TypeError, ValueError):
            return validation_error('Quantity must be in Kg only (e.g. 500 Kg)')
    if qty_kg <= 0:
        return validation_error('Quantity must be positive Kg')

    price_per_kg = extract_price_per_kg(str(payload.get('price')))
    if price_per_kg is None:
        try:
            price_per_kg = round(float(payload.get('price')), 2)
        except (TypeError, ValueError):
            return validation_error('Price must be in Rs/Kg only (e.g. 25 Rs/Kg)')
    if price_per_kg <= 0:
        return validation_error('Price must be positive Rs/Kg')

    grade_info = calculate_grade(crop_name, payload.get('harvest_date'), payload.get('photo'))
    mandi = mandi_service.get_comparison(crop_name, payload.get('location', ''))

    # Store image locally (development) instead of stuffing huge base64 into DB.
    photo_ok, image_url, image_path, photo_err = save_base64_image(payload.get('photo') or '')
    if not photo_ok:
        return validation_error(photo_err or 'Invalid image')

    now = datetime.now().isoformat()
    conn = get_conn()
    try:
        begin(conn)
        farmer_id = _ensure_farmer(conn, user_id, {
            'location': payload.get('location', ''),
            'city': payload.get('city', ''),
            'farm_name': payload.get('farm_name', ''),
        })
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO listings
            (farmer_id,user_id,farmer_name,phone,crop_name,harvest_date,quantity,
             quantity_total,quantity_available,unit,price,price_per_unit,location,city,
             photo,image_url,image_path,grade,expiry_date,shelf_life,freshness_score,
             mandi_price,platform_price,mandi_name,status,created_at,updated_at,voice_transcript,sold_kg)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (farmer_id, user_id, user_name, user_phone, crop_name,
             grade_info['harvest_date_parsed'],
             '%d Kg' % qty_kg, qty_kg, qty_kg, 'Kg', price_per_kg, price_per_kg,
             payload.get('location', ''), payload.get('city', ''),
             image_url or '', image_url or '', image_path or '',
             grade_info['grade'], grade_info['expiry_date'], grade_info['shelf_life'],
             grade_info['freshness_score'], mandi['mandi_price'], price_per_kg,
             mandi['mandi_name'], 'active', now, now,
             payload.get('voice_transcript', ''), 0))
        listing_id = cur.lastrowid
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        'success': True,
        'id': listing_id,
        'grade_info': grade_info,
        'mandi_price': mandi['mandi_price'],
        'mandi_name': mandi['mandi_name'],
        'platform_price': price_per_kg,
        'farmer_price_per_kg': price_per_kg,
        'quantity_kg': qty_kg,
        'crop_name_extracted': crop_name,
        'image_url': image_url or '',
    }


def get_farmer_listings(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT * FROM listings WHERE user_id=? OR farmer_id IN '
            '(SELECT id FROM farmers WHERE user_id=?) ORDER BY created_at DESC',
            (user_id, user_id))
        return [row_to_listing(r) for r in cur.fetchall()]
    finally:
        conn.close()
