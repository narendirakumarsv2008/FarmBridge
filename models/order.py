"""Order + order_items entity access."""

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


def create_order(**fields):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(
            """INSERT INTO orders
               (order_code, consumer_phone, consumer_name, consumer_type,
                subtotal, delivery_fee, discount, total, payment_method,
                payment_status, status, address, eta_minutes, source,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (fields.get("order_code"), fields.get("consumer_phone"),
             fields.get("consumer_name"), fields.get("consumer_type"),
             fields.get("subtotal"), fields.get("delivery_fee"),
             fields.get("discount"), fields.get("total"),
             fields.get("payment_method", "UPI"),
             fields.get("payment_status", "Paid"),
             fields.get("status", "ORDER_PLACED"), fields.get("address"),
             fields.get("eta_minutes"), fields.get("source", "individual"),
             _now(), _now()),
        )
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def add_order_item(**fields):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(
            """INSERT INTO order_items
               (order_id, listing_id, crop_name_snapshot, quantity,
                price_per_unit, subtotal, farmer_id, farmer_phone, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (fields.get("order_id"), fields.get("listing_id"),
             fields.get("crop_name_snapshot"), fields.get("quantity"),
             fields.get("price_per_unit"), fields.get("subtotal"),
             fields.get("farmer_id"), fields.get("farmer_phone"), _now()),
        )
        conn.commit()
    finally:
        conn.close()


def get_order(order_id):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        return _dictify(c.fetchone())
    finally:
        conn.close()


def list_orders(phone=None):
    conn = get_conn()
    try:
        c = conn.cursor()
        if phone:
            c.execute("SELECT * FROM orders WHERE consumer_phone=? ORDER BY id DESC",
                      (phone,))
        else:
            c.execute("SELECT * FROM orders ORDER BY id DESC")
        return [_dictify(r) for r in c.fetchall()]
    finally:
        conn.close()


def list_order_items(order_id):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY id ASC",
                  (order_id,))
        return [_dictify(r) for r in c.fetchall()]
    finally:
        conn.close()


def list_orders_for_farmer(phone):
    """Orders that include at least one item whose listing belongs to `phone`."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT DISTINCT o.* FROM orders o "
            "JOIN order_items oi ON oi.order_id = o.id "
            "WHERE oi.farmer_phone=? ORDER BY o.id DESC",
            (phone,),
        )
        return [_dictify(r) for r in c.fetchall()]
    finally:
        conn.close()


def update_order_status(order_id, status):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("UPDATE orders SET status=?, updated_at=? WHERE id=?",
                  (status, _now(), order_id))
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()


def set_order_payment_status(order_id, payment_status):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("UPDATE orders SET payment_status=?, updated_at=? WHERE id=?",
                  (payment_status, _now(), order_id))
        conn.commit()
    finally:
        conn.close()
