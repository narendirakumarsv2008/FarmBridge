"""HoReCa recurring procurement subscription service."""

import json
from datetime import datetime, timedelta

from database.db import get_conn

WEEKDAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
VALID_FREQUENCIES = ('Daily', 'Alternate Days', 'Weekly', 'Monthly', 'Custom')


class SubscriptionError(Exception):
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


def create_subscription(payload):
    phone = (payload.get('buyer_phone') or '').strip()
    crop = (payload.get('crop_name') or '').strip()
    try:
        qty = float(payload.get('qty_kg') or 0)
    except (TypeError, ValueError):
        raise SubscriptionError('Quantity must be a number')
    freq = payload.get('frequency') or 'Weekly'
    weekdays = payload.get('weekdays') or []

    if not phone or not crop or qty <= 0:
        raise SubscriptionError('Crop, quantity (Kg) and buyer are required')
    if freq not in VALID_FREQUENCIES:
        raise SubscriptionError('Invalid frequency')
    if freq in ('Weekly', 'Custom') and not weekdays:
        raise SubscriptionError('Pick at least one delivery day')

    price = 0.0
    try:
        price = float(payload.get('price_per_kg') or 0)
    except (TypeError, ValueError):
        pass
    listing_id = payload.get('listing_id')

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO subscriptions
            (buyer_phone,buyer_name,org_name,crop_name,listing_id,qty_kg,price_per_kg,
             frequency,weekdays,time_slot,start_date,end_date,active,status,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (phone, payload.get('buyer_name', ''), payload.get('org_name', ''), crop,
             listing_id, qty, price, freq, json.dumps(weekdays),
             payload.get('time_slot', '6:00 AM - 8:00 AM'),
             payload.get('start_date') or datetime.now().strftime('%Y-%m-%d'),
             payload.get('end_date', ''), 1, 'active', datetime.now().isoformat()))
        sid = cur.lastrowid
        conn.commit()
        return {'id': sid, 'success': True}
    finally:
        conn.close()


def list_subscriptions(phone=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        if phone:
            cur.execute('SELECT * FROM subscriptions WHERE buyer_phone=? ORDER BY id DESC',
                        (phone,))
        else:
            cur.execute('SELECT * FROM subscriptions ORDER BY id DESC')
        rows = cur.fetchall()
        out = []
        for r in rows:
            d = _row_dict(r)
            try:
                d['weekdays'] = json.loads(d.get('weekdays') or '[]')
            except Exception:
                d['weekdays'] = []
            out.append(d)
        return out
    finally:
        conn.close()


def update_subscription(sub_id, payload):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM subscriptions WHERE id=?', (sub_id,))
        if not cur.fetchone():
            raise SubscriptionError('Subscription not found', code='NOT_FOUND', status=404)
        if 'active' in payload:
            cur.execute('UPDATE subscriptions SET active=?, status=? WHERE id=?',
                        (1 if payload['active'] else 0,
                         'active' if payload['active'] else 'paused', sub_id))
        if 'qty_kg' in payload:
            qty = float(payload['qty_kg'])
            if qty <= 0:
                raise SubscriptionError('Quantity must be greater than zero')
            cur.execute('UPDATE subscriptions SET qty_kg=? WHERE id=?', (qty, sub_id))
        conn.commit()
        return True
    finally:
        conn.close()


def delete_subscription(sub_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM subscriptions WHERE id=?', (sub_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def subscription_calendar(phone=None, days=30):
    conn = get_conn()
    try:
        cur = conn.cursor()
        if phone:
            cur.execute('SELECT * FROM subscriptions WHERE buyer_phone=? AND active=1',
                        (phone,))
        else:
            cur.execute('SELECT * FROM subscriptions WHERE active=1')
        subs = cur.fetchall()
    finally:
        conn.close()

    schedule = {}
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    for sub in subs:
        try:
            wd = json.loads(sub.get('weekdays') or '[]')
        except Exception:
            wd = []
        try:
            start = datetime.strptime(sub['start_date'], '%Y-%m-%d')
        except Exception:
            start = today
        for i in range(days):
            day = today + timedelta(days=i)
            if day < start:
                continue
            name = WEEKDAY_NAMES[day.weekday()]
            hit = False
            if sub['frequency'] == 'Daily':
                hit = True
            elif sub['frequency'] in ('Weekly', 'Custom'):
                hit = name in wd
            elif sub['frequency'] == 'Alternate Days':
                hit = ((day - start).days % 2) == 0
            elif sub['frequency'] == 'Monthly':
                hit = day.day == start.day
            if hit:
                key = day.strftime('%Y-%m-%d')
                schedule.setdefault(key, []).append({
                    'sub_id': sub['id'], 'crop_name': sub['crop_name'],
                    'qty_kg': sub['qty_kg'], 'price_per_kg': sub['price_per_kg'],
                    'time_slot': sub['time_slot'],
                    'amount': round(float(sub['qty_kg']) * float(sub['price_per_kg'] or 0), 2),
                })
    total_kg = sum(d['qty_kg'] for v in schedule.values() for d in v)
    total_amt = sum(d['amount'] for v in schedule.values() for d in v)
    return {
        'schedule': schedule,
        'days': days,
        'total_kg': total_kg,
        'total_amount': round(total_amt, 2),
        'delivery_count': sum(len(v) for v in schedule.values()),
    }
