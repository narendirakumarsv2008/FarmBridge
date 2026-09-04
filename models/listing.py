"""Listing entity access."""

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


def create_listing(**fields):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(
            """INSERT INTO listings
               (farmer_id, farmer_name, phone, crop_name, harvest_date,
                quantity, quantity_total, quantity_available, unit, price,
                price_per_unit, location, city, image_url, photo, grade,
                freshness_score, expiry_date, shelf_life, mandi_price,
                platform_price, mandi_name, status, voice_transcript, sold_kg,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (fields.get("farmer_id"), fields.get("farmer_name"), fields.get("phone"),
             fields.get("crop_name"), fields.get("harvest_date"),
             fields.get("quantity"), fields.get("quantity_total"),
             fields.get("quantity_available"), fields.get("unit"),
             fields.get("price"), fields.get("price_per_unit"),
             fields.get("location"), fields.get("city"), fields.get("image_url"),
             fields.get("photo"), fields.get("grade"),
             fields.get("freshness_score"), fields.get("expiry_date"),
             fields.get("shelf_life"), fields.get("mandi_price"),
             fields.get("platform_price"), fields.get("mandi_name"),
             fields.get("status", "active"), fields.get("voice_transcript"),
             fields.get("sold_kg", 0), _now(), _now()),
        )
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def get_listing(listing_id):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM listings WHERE id=?", (listing_id,))
        return _dictify(c.fetchone())
    finally:
        conn.close()


def list_listings(order="created_at DESC", where=None, params=()):
    conn = get_conn()
    try:
        c = conn.cursor()
        sql = "SELECT * FROM listings"
        if where:
            sql += " WHERE " + where
        sql += " ORDER BY " + order
        c.execute(sql, params)
        return [_dictify(r) for r in c.fetchall()]
    finally:
        conn.close()


def list_listings_by_phone(phone):
    return list_listings(where="phone=?", params=(phone,))


def update_listing(listing_id, **fields):
    allowed = {
        "crop_name", "harvest_date", "quantity", "quantity_total",
        "quantity_available", "unit", "price", "price_per_unit", "location",
        "city", "image_url", "grade", "freshness_score", "expiry_date",
        "shelf_life", "status",
    }
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    updates["updated_at"] = _now()
    conn = get_conn()
    try:
        c = conn.cursor()
        sets = ", ".join("%s=?" % k for k in updates)
        c.execute("UPDATE listings SET %s WHERE id=?" % sets,
                  tuple(updates.values()) + (listing_id,))
        conn.commit()
    finally:
        conn.close()


def delete_listing(listing_id):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM listings WHERE id=?", (listing_id,))
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()


def decrement_stock(listing_id, qty):
    """
    Atomically reduce available stock, refusing to go negative.

    Returns True if the decrement succeeded (enough stock), False otherwise.
    """
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(
            "UPDATE listings SET quantity_available = quantity_available - ?, "
            "sold_kg = COALESCE(sold_kg, 0) + ?, updated_at=? "
            "WHERE id=? AND quantity_available >= ?",
            (qty, qty, _now(), listing_id, qty),
        )
        conn.commit()
        return c.rowcount == 1
    finally:
        conn.close()


def restore_stock(listing_id, qty):
    """Restore stock (used when an order is cancelled)."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(
            "UPDATE listings SET quantity_available = quantity_available + ?, "
            "sold_kg = MAX(COALESCE(sold_kg, 0) - ?, 0), updated_at=? "
            "WHERE id=?",
            (qty, qty, _now(), listing_id),
        )
        conn.commit()
    finally:
        conn.close()
