"""
Order placement and status service.

Orders are created inside a database transaction. Stock is validated against
the authoritative `quantity_available` column and decremented atomically, so a
consumer can never oversell a farmer's listing. Totals are computed by the
backend from listing prices (and pool prices for community purchases) - the
frontend's price field is never trusted.
"""

import json
import random
from datetime import datetime

from database.db import begin, get_conn

ORDER_STATUS_CODE = {
    'ORDER_PLACED': 'Order Placed',
    'FARMER_CONFIRMED': 'Farmer Confirmed',
    'HARVEST_PACKED': 'Harvest Packed',
    'OUT_FOR_DELIVERY': 'Out for Delivery',
    'DELIVERED': 'Delivered',
    'CANCELLED': 'Cancelled',
}

FLOW_CODES = [
    'ORDER_PLACED',
    'FARMER_CONFIRMED',
    'HARVEST_PACKED',
    'OUT_FOR_DELIVERY',
    'DELIVERED',
]

VALID_TRANSITIONS = {
    'ORDER_PLACED': ['FARMER_CONFIRMED', 'CANCELLED'],
    'FARMER_CONFIRMED': ['HARVEST_PACKED', 'CANCELLED'],
    'HARVEST_PACKED': ['OUT_FOR_DELIVERY', 'CANCELLED'],
    'OUT_FOR_DELIVERY': ['DELIVERED'],
    'DELIVERED': [],
    'CANCELLED': [],
}


class OrderError(Exception):
    def __init__(self, message, code='VALIDATION_ERROR', status=400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _row_dict(r):
    if r is None:
        return None
    if isinstance(r, dict):
        return dict(r)
    return {k: r[k] for k in r.keys()}


def _display_order(row):
    if not row:
        return None
    d = _row_dict(row)
    d['status_code'] = d.get('status')
    d['status'] = ORDER_STATUS_CODE.get(d.get('status'), d.get('status'))
    try:
        d['items'] = json.loads(d.get('items') or '[]')
    except Exception:
        d['items'] = []
    d['flow'] = [ORDER_STATUS_CODE.get(c, c) for c in FLOW_CODES]
    d['step_index'] = FLOW_CODES.index(d['status_code']) if d['status_code'] in FLOW_CODES else 0
    return d


def _select_for_update(cur, listing_id):
    if cur._engine == 'mysql':
        cur.execute('SELECT * FROM listings WHERE id=? FOR UPDATE', (listing_id,))
    else:
        cur.execute('SELECT * FROM listings WHERE id=?', (listing_id,))
    return cur.fetchone()


def _pool_unit_price(conn, pool_id, fallback):
    cur = conn.cursor()
    cur.execute('SELECT * FROM pools WHERE id=?', (pool_id,))
    pool = cur.fetchone()
    if not pool:
        return fallback
    cur.execute('SELECT COALESCE(SUM(qty_kg),0) AS n FROM pool_joins WHERE pool_id=?', (pool_id,))
    joined = float(cur.fetchone()['n'] or 0)
    total = float(pool.get('seeded_kg') or 0) + joined
    target = float(pool.get('target_kg') or 0)
    if target > 0:
        pct = min(100, round(total / target * 100))
    else:
        pct = 0
    # Pool tiers: 25% -> 4%, 50% -> 8%, 75% -> 12%, 100% -> 18%.
    discount = 0
    for threshold, d in ((25, 4), (50, 8), (75, 12), (100, 18)):
        if pct >= threshold:
            discount = d
    base = float(pool.get('base_price') or fallback)
    return round(base * (1 - discount / 100.0), 2)


def place_order(payload, user):
    items_raw = payload.get('items') or []
    if not items_raw or not isinstance(items_raw, list):
        raise OrderError('Cart is empty', 'VALIDATION_ERROR')

    phone = (payload.get('buyer_phone') or '').strip() or (user or {}).get('phone', '')
    name = (payload.get('buyer_name') or '').strip() or (user or {}).get('name', '')
    if not phone:
        raise OrderError('Buyer phone required', 'VALIDATION_ERROR')

    source = (payload.get('source') or 'individual').strip().lower()
    address = payload.get('address') or ''
    payment_method = payload.get('payment_method') or 'UPI'

    conn = get_conn()
    try:
        begin(conn)
        cur = conn.cursor()
        order_items = []
        subtotal = 0.0

        # Ensure consumer profile exists so farmers can see who ordered.
        cur.execute('SELECT * FROM consumers WHERE user_id=? ORDER BY id DESC LIMIT 1',
                    (user.get('user_id'),))
        consumer = cur.fetchone()
        consumer_id = consumer['id'] if consumer else None
        consumer_type = (consumer or {}).get('consumer_type') or 'individual'

        for item in items_raw:
            try:
                listing_id = int(item.get('listing_id') or 0)
                qty = float(item.get('qty') or item.get('quantity') or 0)
            except (TypeError, ValueError):
                raise OrderError('Invalid item in cart', 'VALIDATION_ERROR')
            if listing_id <= 0:
                raise OrderError('Invalid listing in cart', 'VALIDATION_ERROR')
            if qty <= 0:
                raise OrderError('Quantity must be greater than zero', 'VALIDATION_ERROR')

            listing = _select_for_update(cur, listing_id)
            if not listing:
                raise OrderError('A product in your cart is no longer available', 'NOT_FOUND', 404)
            if listing.get('status') in ('inactive', 'expired', 'sold_out'):
                raise OrderError(
                    '%s is no longer available for sale' % listing.get('crop_name'),
                    'CONFLICT', 409)
            price = float(listing.get('price_per_unit') or listing.get('price') or 0)
            if price <= 0:
                raise OrderError('Invalid price for %s' % listing.get('crop_name'), 'CONFLICT', 409)

            pool_id = item.get('pool_id')
            if source == 'community' and pool_id:
                price = _pool_unit_price(conn, int(pool_id), price)

            qty_check = cur.execute(
                """UPDATE listings
                   SET quantity_available = quantity_available - ?,
                       sold_kg = COALESCE(sold_kg, 0) + ?,
                       status = CASE WHEN quantity_available - ? <= 0 THEN 'sold_out' ELSE status END
                   WHERE id = ? AND quantity_available >= ?""",
                (qty, qty, qty, listing_id, qty))
            if cur.rowcount != 1:
                raise OrderError(
                    'Only %s Kg of %s is available' % (
                        listing.get('quantity_available'), listing.get('crop_name')),
                    'CONFLICT', 409)

            crop_snapshot = listing.get('crop_name') or item.get('crop_name') or ''
            subtotal_item = round(price * qty, 2)
            subtotal += subtotal_item
            order_items.append({
                'listing_id': listing_id,
                'crop_name': crop_snapshot,
                'qty': qty,
                'unit': 'Kg',
                'price': price,
                'subtotal': subtotal_item,
                'farmer_id': listing.get('farmer_id'),
                'pool_id': pool_id,
                'photo': listing.get('image_url') or listing.get('photo') or '',
                'grade': listing.get('grade'),
                'farmer_name': listing.get('farmer_name'),
            })

        subtotal = round(subtotal, 2)
        delivery_fee = 0.0 if subtotal >= 500 else 25.0
        discount = 0.0
        if source == 'community':
            discount = round(float(payload.get('discount') or 0), 2)
            discount = max(0, min(discount, 0.18 * subtotal))
        total = round(subtotal - discount + delivery_fee, 2)

        order_code = 'FB' + datetime.now().strftime('%y%m%d') + str(random.randint(1000, 9999))
        eta = random.randint(12, 25)
        now = datetime.now().isoformat()

        cur.execute(
            """INSERT INTO orders
            (order_code,buyer_user_id,consumer_id,buyer_phone,buyer_name,consumer_type,
             items,subtotal,delivery_fee,discount,total,payment_method,payment_status,
             status,address,eta_minutes,source,stock_restored,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (order_code, user.get('user_id'), consumer_id, phone, name, consumer_type,
             json.dumps(order_items), subtotal, delivery_fee, discount, total,
             payment_method,
             'Paid' if payment_method != 'COD' else 'Pay on delivery',
             'ORDER_PLACED', address, eta, source, 0, now, now))
        order_id = cur.lastrowid

        for it in order_items:
            cur.execute(
                """INSERT INTO order_items
                (order_id,listing_id,crop_name_snapshot,quantity,unit,price_per_unit,
                 subtotal,farmer_id,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (order_id, it['listing_id'], it['crop_name'], it['qty'], 'Kg',
                 it['price'], it['subtotal'], it.get('farmer_id'), now))

        cur.execute(
            'INSERT INTO delivery_tracking (order_id,status,note,created_at) '
            'VALUES (?,?,?,?)', (order_id, 'ORDER_PLACED', 'Order placed', now))

        conn.commit()
        return {
            'id': order_id,
            'order_code': order_code,
            'subtotal': subtotal,
            'delivery_fee': delivery_fee,
            'discount': discount,
            'total': total,
            'eta_minutes': eta,
            'status_code': 'ORDER_PLACED',
            'status': 'Order Placed',
            'items': order_items,
        }
    except OrderError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _get_order_row(order_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM orders WHERE id=?', (order_id,))
        return cur.fetchone()
    finally:
        conn.close()


def list_orders(phone=None, user_id=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        if phone:
            cur.execute('SELECT * FROM orders WHERE buyer_phone=? ORDER BY id DESC', (phone,))
        elif user_id:
            cur.execute('SELECT * FROM orders WHERE buyer_user_id=? ORDER BY id DESC', (user_id,))
        else:
            cur.execute('SELECT * FROM orders ORDER BY id DESC')
        return [_display_order(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_order(order_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM orders WHERE id=?', (order_id,))
        row = cur.fetchone()
        rown = dict(row or {})
        # Attach order_items for a clean API response.
        cur.execute('SELECT * FROM order_items WHERE order_id=?', (order_id,))
        rown['order_items'] = cur.fetchall()
        return _display_order(rown)
    finally:
        conn.close()


def advance_order(order_id):
    conn = get_conn()
    try:
        begin(conn)
        cur = conn.cursor()
        cur.execute('SELECT * FROM orders WHERE id=?', (order_id,))
        row = cur.fetchone()
        if not row:
            raise OrderError('Order not found', 'NOT_FOUND', 404)
        current = row.get('status')
        current_idx = FLOW_CODES.index(current) if current in FLOW_CODES else 0
        nxt = FLOW_CODES[min(current_idx + 1, len(FLOW_CODES) - 1)]
        if nxt == current:
            raise OrderError('Order is already complete', 'CONFLICT', 409)
        _transition_order(conn, order_id, row, nxt)
        conn.commit()
        return _display_order(cur.fetchone() if False else _get_order_row(order_id))
    except OrderError:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_order_status(order_id, requested_status):
    conn = get_conn()
    try:
        begin(conn)
        cur = conn.cursor()
        cur.execute('SELECT * FROM orders WHERE id=?', (order_id,))
        row = cur.fetchone()
        if not row:
            raise OrderError('Order not found', 'NOT_FOUND', 404)

        code = (requested_status or '').strip().upper()
        # Accept display labels too.
        for k, v in ORDER_STATUS_CODE.items():
            if requested_status and requested_status.strip() == v:
                code = k
                break
        if code not in ORDER_STATUS_CODE:
            raise OrderError('Invalid order status', 'VALIDATION_ERROR')

        _transition_order(conn, order_id, row, code)
        conn.commit()
        return _display_order(_get_order_row(order_id))
    except OrderError:
        conn.rollback()
        raise
    finally:
        conn.close()


def _transition_order(conn, order_id, row, new_code):
    current = row.get('status') or 'ORDER_PLACED'
    if new_code not in VALID_TRANSITIONS.get(current, []):
        raise OrderError(
            'Invalid status transition from %s to %s' % (
                ORDER_STATUS_CODE.get(current, current),
                ORDER_STATUS_CODE.get(new_code, new_code)),
            'CONFLICT', 409)

    # Restore stock when a non-delivered order is cancelled.
    if new_code == 'CANCELLED' and current != 'CANCELLED' and not int(row.get('stock_restored') or 0):
        cur = conn.cursor()
        cur.execute('SELECT * FROM order_items WHERE order_id=?', (order_id,))
        for item in cur.fetchall():
            cur.execute(
                """UPDATE listings
                   SET quantity_available = quantity_available + ?,
                       sold_kg = MAX(0, COALESCE(sold_kg,0) - ?),
                       status = CASE WHEN status='sold_out' THEN 'active' ELSE status END
                   WHERE id=?""",
                (float(item.get('quantity') or 0), float(item.get('quantity') or 0),
                 item.get('listing_id')))
        cur.execute('UPDATE orders SET stock_restored=1 WHERE id=?', (order_id,))

    cur = conn.cursor()
    now = datetime.now().isoformat()
    cur.execute('UPDATE orders SET status=?, updated_at=? WHERE id=?', (new_code, now, order_id))
    cur.execute(
        'INSERT INTO delivery_tracking (order_id,status,note,created_at) VALUES (?,?,?,?)',
        (order_id, new_code, 'Status changed to %s' % ORDER_STATUS_CODE.get(new_code, new_code), now))


def list_farmer_orders(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT DISTINCT f.id AS farmer_id FROM farmers f
               WHERE f.user_id=?
               UNION
               SELECT DISTINCT l.farmer_id AS farmer_id FROM listings l
               WHERE l.user_id=? OR l.farmer_id IN (
                   SELECT id FROM farmers WHERE user_id=?
               )""", (user_id, user_id, user_id))
        farmer_ids = [r['farmer_id'] for r in cur.fetchall() if r.get('farmer_id')]

        cur.execute(
            """SELECT DISTINCT o.* FROM orders o
               JOIN order_items oi ON oi.order_id = o.id
               WHERE oi.farmer_id IN ({})
               ORDER BY o.id DESC""".format(','.join(['?'] * len(farmer_ids))) if farmer_ids
            else 'SELECT * FROM orders WHERE 0=1',
            tuple(farmer_ids) if farmer_ids else ())
        rows = cur.fetchall()
        out = []
        for row in rows:
            order = _display_order(row)
            cur.execute(
                'SELECT oi.*, l.crop_name AS current_crop_name, l.location AS listing_location '
                'FROM order_items oi LEFT JOIN listings l ON l.id=oi.listing_id '
                'WHERE oi.order_id=?', (row['id'],))
            order['order_items'] = cur.fetchall()
            order['farmer_items'] = [
                i for i in order['order_items'] if i.get('farmer_id') in farmer_ids
            ]
            out.append(order)
        return out
    finally:
        conn.close()
