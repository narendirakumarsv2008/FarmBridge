"""
Order service — transactional, stock-safe order placement.

Flow:
  consumer → POST /api/orders
    → validate every item
    → check available stock (server-side, never trust the frontend)
    → lock/transaction (single connection)
    → atomically reduce stock (conditional UPDATE, refuses negative)
    → create order + order_items
    → commit
    → return confirmation

Prices and totals are ALWAYS computed from the database listing price; the
frontend can only choose `listing_id` + quantity.
"""

import random
import re
from datetime import datetime

import config
from database.db import get_conn
from database.schema import (
    ORDER_FLOW,
    ORDER_STATUS_LABELS,
    ORDER_TRANSITIONS,
)


class OrderError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _row(r):
    if r is None:
        return None
    if isinstance(r, dict):
        return dict(r)
    return {k: r[k] for k in r.keys()}


def _scalar(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return next(iter(row.values()))
    return row[0]


def _now():
    return datetime.now().isoformat()


def _order_code():
    return "FB" + datetime.now().strftime("%y%m%d") + str(random.randint(1000, 9999))


def _estimate_eta(num_items):
    return 30 + 5 * num_items


def create_order(items, consumer_phone, consumer_name="", consumer_type="Individual",
                 address="", payment_method="UPI", source="individual"):
    """Place an order atomically. Raises OrderError on any failure."""
    from models import listing as listing_model
    from services import pool_service

    if not items or not isinstance(items, list):
        raise OrderError("VALIDATION_ERROR", "Cart is empty")
    phone = re.sub(r"\D", "", consumer_phone or "")
    if not phone:
        raise OrderError("VALIDATION_ERROR", "Consumer phone required")

    # Normalize + validate every item up-front.
    normalized = []
    for it in items:
        if not isinstance(it, dict):
            raise OrderError("VALIDATION_ERROR", "Invalid cart item")
        try:
            listing_id = int(it.get("listing_id"))
        except (TypeError, ValueError):
            raise OrderError("VALIDATION_ERROR", "Invalid listing id in cart")
        try:
            qty = int(it.get("qty") or it.get("quantity") or 0)
        except (TypeError, ValueError):
            qty = 0
        if qty <= 0:
            raise OrderError("VALIDATION_ERROR", "Quantity must be greater than zero")
        normalized.append({"listing_id": listing_id, "qty": qty})

    order_code = _order_code()
    eta_minutes = _estimate_eta(len(normalized))

    conn = get_conn()
    c = conn.cursor()
    try:
        subtotal = 0.0
        line_items = []

        for item in normalized:
            listing_id, qty = item["listing_id"], item["qty"]

            c.execute("SELECT * FROM listings WHERE id=?", (listing_id,))
            listing = _row(c.fetchone())
            if not listing:
                raise OrderError("NOT_FOUND", "Listing %s not found" % listing_id, status=404)

            status = listing.get("status")
            available = int(listing.get("quantity_available") or 0)
            if status in ("sold_out", "expired", "inactive") or available <= 0:
                raise OrderError("INSUFFICIENT_STOCK",
                                 "%s is no longer available" % (listing.get("crop_name") or "Item"),
                                 status=409)

            # Authoritative unit price from the database listing.
            base_price = float(listing.get("price_per_unit") or listing.get("price") or 0)
            if base_price <= 0:
                raise OrderError("VALIDATION_ERROR",
                                 "Listing %s has no valid price" % listing_id)

            # Community pool-buy: discount computed server-side.
            unit_price = base_price
            discount_pct = 0
            if source == "community":
                unit_price, discount_pct = pool_service.price_after_pool_discount(
                    listing_id, base_price)

            # Re-read current stock (authoritative, never trusts the client).
            c.execute("SELECT quantity_available FROM listings WHERE id=?",
                      (listing_id,))
            before = int(_scalar(c.fetchone()) or 0)
            if before < qty:
                raise OrderError(
                    "INSUFFICIENT_STOCK",
                    "Not enough stock for %s — only %s Kg available"
                    % (listing.get("crop_name") or "item", before),
                    status=409,
                )

            # Atomic, oversell-safe decrement. The conditional WHERE clause is
            # what guarantees we can never drive inventory negative under
            # concurrent requests (the row is locked and re-evaluated).
            c.execute(
                "UPDATE listings SET quantity_available = quantity_available - ?, "
                "sold_kg = COALESCE(sold_kg, 0) + ?, updated_at=? "
                "WHERE id=? AND quantity_available >= ?",
                (qty, qty, _now(), listing_id, qty),
            )

            # Confirm the decrement actually happened. This also covers drivers
            # / test doubles that report affected-rows as 0 for UPDATE.
            c.execute("SELECT quantity_available FROM listings WHERE id=?",
                      (listing_id,))
            after = int(_scalar(c.fetchone()) or 0)
            if after == before:
                raise OrderError(
                    "INSUFFICIENT_STOCK",
                    "Not enough stock for %s — only %s Kg available"
                    % (listing.get("crop_name") or "item", before),
                    status=409,
                )

            line_subtotal = round(unit_price * qty, 2)
            subtotal += line_subtotal
            line_items.append({
                "listing_id": listing_id,
                "crop_name": listing.get("crop_name"),
                "qty": qty,
                "price": unit_price,
                "subtotal": line_subtotal,
                "farmer_id": listing.get("farmer_id"),
                "farmer_phone": listing.get("phone"),
                "discount_pct": discount_pct,
            })

        subtotal = round(subtotal, 2)
        delivery_fee = 0 if subtotal >= config.Config.FREE_DELIVERY_ABOVE else config.Config.DEFAULT_DELIVERY_FEE
        discount = 0.0
        total = round(subtotal - discount + delivery_fee, 2)
        payment_status = "Paid" if payment_method != "COD" else "Pay on delivery"

        c.execute(
            """INSERT INTO orders
               (order_code, consumer_phone, consumer_name, consumer_type,
                subtotal, delivery_fee, discount, total, payment_method,
                payment_status, status, address, eta_minutes, source,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (order_code, phone, consumer_name, consumer_type, subtotal,
             delivery_fee, discount, total, payment_method, payment_status,
             "ORDER_PLACED", address, eta_minutes, source,
             _now(), _now()),
        )
        order_id = c.lastrowid

        for line in line_items:
            c.execute(
                """INSERT INTO order_items
                   (order_id, listing_id, crop_name_snapshot, quantity,
                    price_per_unit, subtotal, farmer_id, farmer_phone, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (order_id, line["listing_id"], line["crop_name"], line["qty"],
                 line["price"], line["subtotal"], line["farmer_id"],
                 line["farmer_phone"], _now()),
            )

        c.execute(
            "INSERT INTO delivery_tracking (order_id, status, note, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (order_id, "ORDER_PLACED", "Order received", _now(), _now()),
        )

        conn.commit()
    except OrderError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise OrderError("SERVER_ERROR", "Order could not be placed: %s" % exc, status=500)
    finally:
        conn.close()

    return {
        "id": order_id,
        "order_code": order_code,
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "discount": discount,
        "total": total,
        "eta_minutes": eta_minutes,
        "status": "ORDER_PLACED",
        "status_label": ORDER_STATUS_LABELS["ORDER_PLACED"],
        "items": line_items,
    }


def get_order_detail(order_id):
    from models import order as order_model
    order = order_model.get_order(order_id)
    if not order:
        return None
    items = order_model.list_order_items(order_id)
    from services.marketplace_service import serialize_order
    return serialize_order(order, items)


def list_orders(phone=None):
    from models import order as order_model
    orders = order_model.list_orders(phone)
    out = []
    for o in orders:
        items = order_model.list_order_items(o["id"])
        from services.marketplace_service import serialize_order
        out.append(serialize_order(o, items))
    return out


def list_farmer_orders(phone):
    from models import order as order_model
    orders = order_model.list_orders_for_farmer(phone)
    out = []
    for o in orders:
        items = order_model.list_order_items(o["id"])
        # only show the farmer's own lines
        mine = [i for i in items if (i.get("farmer_phone") == phone)]
        from services.marketplace_service import serialize_order, serialize_item
        serialized = serialize_order(o, mine)
        serialized["my_items"] = [serialize_item(i) for i in mine]
        out.append(serialized)
    return out


def advance_order(order_id):
    """Legacy/demo: move an order to the next step in the linear flow."""
    from models import order as order_model

    order = order_model.get_order(order_id)
    if not order:
        return None
    status = order.get("status") or "ORDER_PLACED"
    if status not in ORDER_FLOW:
        next_status = "ORDER_PLACED"
    else:
        idx = ORDER_FLOW.index(status)
        next_status = ORDER_FLOW[min(idx + 1, len(ORDER_FLOW) - 1)]
    order_model.update_order_status(order_id, next_status)
    _track(order_id, next_status)
    return next_status


def set_order_status(order_id, new_status, actor=None):
    """Validate a transition and apply it (with ownership check by caller)."""
    from models import order as order_model

    order = order_model.get_order(order_id)
    if not order:
        return None, "Order not found"
    current = order.get("status") or "ORDER_PLACED"
    if new_status not in ORDER_TRANSITIONS:
        return None, "Unknown status"
    if new_status != "CANCELLED" and new_status not in ORDER_TRANSITIONS.get(current, set()):
        return None, ("Cannot move order from %s to %s"
                      % (ORDER_STATUS_LABELS.get(current, current),
                         ORDER_STATUS_LABELS.get(new_status, new_status)))

    # Restore stock when an order is cancelled (so inventory isn't lost).
    if new_status == "CANCELLED" and current != "CANCELLED":
        for item in order_model.list_order_items(order_id):
            listing_id = item.get("listing_id")
            qty = int(item.get("quantity") or 0)
            if listing_id and qty:
                from models import listing as listing_model
                listing_model.restore_stock(listing_id, qty)

    order_model.update_order_status(order_id, new_status)
    _track(order_id, new_status)
    return new_status, None


def _track(order_id, status):
    from database.db import get_conn as _gc
    conn = _gc()
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO delivery_tracking (order_id, status, note, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (order_id, status, "Status changed to " + status, _now(), _now()),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()
