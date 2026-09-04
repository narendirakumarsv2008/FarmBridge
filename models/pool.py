"""Community pool-buy entity access."""

from datetime import datetime

from database.db import get_conn


def _now():
    return datetime.now().isoformat()


def _dictify(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    return {k: row[k] for k in row.keys()}


def get_pools(status="open"):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM pools WHERE status=? ORDER BY id DESC", (status,))
        return [_dictify(r) for r in c.fetchall()]
    finally:
        conn.close()


def get_pool(pool_id):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM pools WHERE id=?", (pool_id,))
        return _dictify(c.fetchone())
    finally:
        conn.close()


def get_open_pool_for_listing(listing_id):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM pools WHERE listing_id=? AND status='open' "
                  "ORDER BY id DESC LIMIT 1", (listing_id,))
        return _dictify(c.fetchone())
    finally:
        conn.close()


def create_pool(**fields):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(
            """INSERT INTO pools
               (crop_name, listing_id, photo, grade, base_price, target_kg,
                seeded_kg, ends_at, location, farmer_name, status, is_demo,
                created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (fields.get("crop_name"), fields.get("listing_id"),
             fields.get("photo"), fields.get("grade"), fields.get("base_price"),
             fields.get("target_kg"), fields.get("seeded_kg", 0),
             fields.get("ends_at"), fields.get("location"),
             fields.get("farmer_name"), fields.get("status", "open"),
             fields.get("is_demo", 1), _now()),
        )
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def count_open_pools():
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) AS n FROM pools WHERE status='open'")
        return (dict(c.fetchone()) or {}).get("n", 0)
    finally:
        conn.close()


def add_pool_join(pool_id, consumer_phone, consumer_name, org_name, qty_kg):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO pool_joins (pool_id, consumer_phone, consumer_name, "
            "org_name, qty_kg, joined_at) VALUES (?, ?, ?, ?, ?, ?)",
            (pool_id, consumer_phone, consumer_name, org_name, qty_kg, _now()),
        )
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def pool_join_stats(pool_id):
    """(total joined kg, distinct members) for a pool."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT COALESCE(SUM(qty_kg),0) AS kg FROM pool_joins WHERE pool_id=?",
                  (pool_id,))
        kg = (dict(c.fetchone()) or {}).get("kg", 0) or 0
        c.execute("SELECT COUNT(DISTINCT consumer_phone) AS n FROM pool_joins "
                  "WHERE pool_id=?", (pool_id,))
        members = (dict(c.fetchone()) or {}).get("n", 0) or 0
        return int(kg), int(members)
    finally:
        conn.close()
