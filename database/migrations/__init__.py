"""
Database migrations.

Each migration is a (version, description, function(conn)) triple. Versions are
monotonic and applied exactly once (tracked in `schema_migrations`).

These migrations upgrade databases created by earlier versions of Farm Bridge
(e.g. the `buyers` table, string `quantity`, `items` JSON on orders) to the
current schema without losing data.
"""

import json
import logging
import re
from datetime import datetime

log = logging.getLogger("farmbridge.migrations")


def _scalar(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return next(iter(row.values()))
    return row[0]


def _rows(conn, sql, params=()):
    c = conn.cursor()
    c.execute(sql, params)
    return [dict(r) if isinstance(r, dict) else {k: r[k] for k in r.keys()}
            for r in c.fetchall()]


def _parse_quantity(value):
    """'100 Kg' / 100 / '5 quintal' → integer Kg."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value)
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return 0
    num = float(m.group(1))
    low = s.lower()
    if "quintal" in low or "qtl" in low:
        return int(round(num * 100))
    if "ton" in low:
        return int(round(num * 1000))
    return int(round(num))


def _migration_1_buyers_to_consumers(conn):
    """Migrate the legacy `buyers` table to `consumers`."""
    from database.db import add_column, table_exists

    if not table_exists(conn, "buyers"):
        return

    c = conn.cursor()
    buyers = _rows(conn, "SELECT * FROM buyers")
    # Ensure consumers has the superset of columns we need.
    add_column(conn, "consumers", "name", "VARCHAR(120)")
    add_column(conn, "consumers", "email", "VARCHAR(190)")
    add_column(conn, "consumers", "landmark", "VARCHAR(190)")
    add_column(conn, "consumers", "created_at", "VARCHAR(40)")

    existing = {r["phone"] for r in _rows(conn, "SELECT phone FROM consumers")}
    now = datetime.now().isoformat()
    for b in buyers:
        phone = b.get("phone")
        if not phone or phone in existing:
            continue
        c.execute(
            """INSERT INTO consumers
               (phone, name, email, consumer_type, delivery_address, landmark,
                organization_name, city, state, pincode, latitude, longitude,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                phone,
                b.get("name"),
                b.get("email"),
                (b.get("buyer_type") or "").lower(),
                b.get("address"),
                b.get("landmark"),
                b.get("org_name"),
                b.get("city"),
                b.get("state") or "",
                b.get("pincode"),
                b.get("latitude"),
                b.get("longitude"),
                b.get("created_at") or now,
                b.get("updated_at") or now,
            ),
        )
        existing.add(phone)

    # Drop the legacy table (its data now lives in consumers).
    try:
        c.execute("DROP TABLE buyers")
    except Exception as exc:  # pragma: no cover - safety net
        log.warning("Could not drop legacy `buyers` table: %s", exc)


def _migration_2_listing_inventory(conn):
    """Add numeric inventory columns to listings and backfill them."""
    from database.db import add_column

    add_column(conn, "listings", "farmer_id", "INTEGER")
    add_column(conn, "listings", "quantity_total", "INTEGER")
    add_column(conn, "listings", "quantity_available", "INTEGER")
    add_column(conn, "listings", "unit", "VARCHAR(20)")
    add_column(conn, "listings", "city", "VARCHAR(120)")
    add_column(conn, "listings", "image_url", "VARCHAR(500)")
    add_column(conn, "listings", "price_per_unit", "DOUBLE")
    add_column(conn, "listings", "updated_at", "VARCHAR(40)")

    c = conn.cursor()
    listings = _rows(conn, "SELECT * FROM listings")
    for l in listings:
        total = l.get("quantity_total")
        if total is None:
            total = _parse_quantity(l.get("quantity"))
        sold = int(l.get("sold_kg") or 0)
        available = max(0, total - sold)
        price = l.get("price_per_unit")
        if price is None:
            price = l.get("price")
        c.execute(
            """UPDATE listings SET
                 quantity_total=?, quantity_available=?, unit=?,
                 price_per_unit=?, status=?
               WHERE id=?""",
            (
                total,
                available,
                l.get("unit") or "Kg",
                price,
                _normalize_listing_status(l, available),
                l.get("id"),
            ),
        )


def _normalize_listing_status(listing, available):
    """Map a legacy listing status to the canonical set."""
    if available <= 0:
        return "sold_out"
    try:
        if listing.get("expiry_date") and listing["expiry_date"] < datetime.now().strftime("%Y-%m-%d"):
            return "expired"
    except Exception:
        pass
    return "active"


def _migration_3_legacy_order_items(conn):
    """Split legacy `orders.items` JSON into `order_items` rows."""
    from database.db import column_exists

    if not column_exists(conn, "orders", "items"):
        return

    c = conn.cursor()
    orders = _rows(conn, "SELECT * FROM orders")
    now = datetime.now().isoformat()
    for o in orders:
        items = o.get("items")
        if items is None:
            continue
        if isinstance(items, str):
            try:
                items = json.loads(items)
            except Exception:
                items = []
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            qty = int(it.get("qty") or it.get("quantity") or 0)
            price = float(it.get("price") or 0)
            listing_id = it.get("listing_id")
            c.execute(
                """INSERT INTO order_items
                   (order_id, listing_id, crop_name_snapshot, quantity,
                    price_per_unit, subtotal, farmer_id, farmer_phone, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    o.get("id"),
                    listing_id,
                    it.get("crop_name") or "",
                    qty,
                    price,
                    round(qty * price, 2),
                    it.get("farmer_id"),
                    it.get("farmer_phone") or "",
                    now,
                ),
            )


# (version, description, function) — applied in order.
MIGRATIONS = [
    (1, "buyers -> consumers", _migration_1_buyers_to_consumers),
    (2, "listings numeric inventory", _migration_2_listing_inventory),
    (3, "orders.items -> order_items", _migration_3_legacy_order_items),
]
