"""Community pool-buy service.

Pools are generated from real farmer listings so they always point to central
database inventory. The pool itself is a demo/community feature: when a
consumer confirms participation, the quantity is stored in pool_joins and an
actual order (with real stock reduction) is placed separately by the frontend.
"""

import random
from datetime import datetime, timedelta

from database.db import get_conn

POOL_TIERS = [
    (0, 0, 'Base price'),
    (25, 4, 'Early pool bonus'),
    (50, 8, 'Half batch unlocked'),
    (75, 12, 'Bulk rate unlocked'),
    (100, 18, 'Full wholesale price'),
]

DEMO_LABEL = 'Demo Pool'
REAL_LABEL = 'Community Pool'


def pool_discount(pct_filled):
    disc, label = 0, 'Base price'
    for threshold, d, lbl in POOL_TIERS:
        if pct_filled >= threshold:
            disc, label = d, lbl
    return disc, label


def next_tier(pct_filled):
    for threshold, d, lbl in POOL_TIERS:
        if pct_filled < threshold:
            return {'at_pct': threshold, 'discount': d, 'label': lbl}
    return None


def _row_dict(r):
    if r is None:
        return None
    if isinstance(r, dict):
        return dict(r)
    return {k: r[k] for k in r.keys()}


def _daily_seed(key):
    today = datetime.now().strftime('%Y-%m-%d')
    return random.Random('%s-%s' % (key, today))


def seed_pools_if_needed():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS n FROM pools WHERE status='open'")
        if (cur.fetchone() or {}).get('n', 0) >= 3:
            return
        cur.execute('SELECT * FROM listings ORDER BY created_at DESC LIMIT 6')
        listings = cur.fetchall()
        for l in listings:
            cur.execute("SELECT COUNT(*) AS n FROM pools WHERE listing_id=? AND status='open'",
                        (l['id'],))
            if (cur.fetchone() or {}).get('n'):
                continue
            rnd = _daily_seed('pool-%s' % l['id'])
            target = rnd.choice([300, 500, 750, 1000])
            ends = datetime.now() + timedelta(hours=rnd.randint(6, 36))
            cur.execute(
                """INSERT INTO pools
                (crop_name,listing_id,photo,grade,base_price,target_kg,seeded_kg,ends_at,
                 location,farmer_name,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (l['crop_name'], l['id'], l.get('image_url') or l.get('photo', ''),
                 l.get('grade', 'A'), float(l.get('price_per_unit') or l.get('price') or 20),
                 target, 0, ends.isoformat(), l.get('location', ''), l.get('farmer_name', ''),
                 'open', datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()


def get_pools():
    seed_pools_if_needed()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM pools WHERE status='open' ORDER BY id DESC")
        pools = cur.fetchall()
        out = []
        for p in pools:
            cur.execute('SELECT COALESCE(SUM(qty_kg),0) AS n FROM pool_joins WHERE pool_id=?',
                        (p['id'],))
            joined = float((cur.fetchone() or {}).get('n') or 0)
            cur.execute('SELECT COUNT(DISTINCT buyer_phone) AS n FROM pool_joins WHERE pool_id=?',
                        (p['id'],))
            members = int((cur.fetchone() or {}).get('n') or 0)
            current = int(p['seeded_kg']) + int(joined)
            target = int(p['target_kg'] or 0)
            pct = min(100, round(current / target * 100)) if target else 0
            disc, label = pool_discount(pct)
            base = float(p['base_price'])
            price_now = round(base * (1 - disc / 100), 2)
            try:
                ends = datetime.fromisoformat(p['ends_at'])
            except Exception:
                ends = datetime.now() + timedelta(hours=12)
            secs_left = max(0, int((ends - datetime.now()).total_seconds()))
            nt = next_tier(pct)
            kg_to_next = 0
            if nt:
                kg_to_next = max(0, int(target * nt['at_pct'] / 100) - current)
            p.update({
                'current_kg': current,
                'members': members,
                'pct': pct,
                'discount_pct': disc,
                'tier_label': label,
                'price_now': price_now,
                'base_price': base,
                'seconds_left': secs_left,
                'hours_left': round(secs_left / 3600, 1),
                'unlocked': pct >= 100,
                'next_tier': nt,
                'kg_to_next_tier': kg_to_next,
                'tiers': [{'at_pct': t[0], 'discount': t[1], 'label': t[2],
                           'price': round(base * (1 - t[1] / 100), 2)} for t in POOL_TIERS],
                'is_demo': True,
                'data_source': DEMO_LABEL,
            })
            out.append(p)
        return out
    finally:
        conn.close()


def join_pool(pool_id, payload):
    try:
        qty = int(payload.get('qty_kg') or 0)
    except (TypeError, ValueError):
        return None, 'Quantity must be a number'
    if qty <= 0:
        return None, 'Enter quantity in Kg to pool'
    phone = (payload.get('buyer_phone') or '').strip()

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM pools WHERE id=? AND status=?', (pool_id, 'open'))
        pool = cur.fetchone()
        if not pool:
            return None, 'Pool not found or closed'
        cur.execute(
            """INSERT INTO pool_joins (pool_id,buyer_phone,buyer_name,org_name,qty_kg,joined_at)
               VALUES (?,?,?,?,?,?)""",
            (pool_id, phone, payload.get('buyer_name', ''),
             payload.get('org_name', ''), qty, datetime.now().isoformat()))
        conn.commit()
        return {'success': True, 'pool_id': pool_id, 'qty_kg': qty}, None
    finally:
        conn.close()
