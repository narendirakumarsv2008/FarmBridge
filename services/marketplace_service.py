"""
Marketplace service — the consumer-facing catalogue.

The marketplace is **read straight from the central database**: it is the same
`listings` table the Farmer Portal writes to. There is no hardcoded product
list, no localStorage source of truth, and no per-device data.

Enrichment here only ADDS display metadata (freshness label, stock percentage,
grade colors). It no longer mutates prices or stock — the price a farmer sets
and the quantity available in the database are exactly what consumers see.
"""

from datetime import datetime, timedelta

from database.schema import ORDER_STATUS_LABELS
from models import listing as listing_model


def _harvest_label(harvest_date):
    harvest = harvest_date or ""
    try:
        hd = datetime.strptime(harvest, "%Y-%m-%d")
        age_days = (datetime.now() - hd).days
        display = hd.strftime("%d %b %Y")
    except Exception:
        age_days = 0
        display = harvest
    if age_days <= 0:
        label = "Harvested today"
    elif age_days == 1:
        label = "Harvested yesterday"
    else:
        label = "Harvested %d days ago" % age_days
    return age_days, display, label


def listing_status_for(l, available, today=None):
    """Derive the canonical listing status from inventory + expiry."""
    today = today or datetime.now().strftime("%Y-%m-%d")
    if l.get("status") == "inactive":
        return "inactive"
    if available <= 0:
        return "sold_out"
    try:
        if l.get("expiry_date") and l["expiry_date"] < today:
            return "expired"
    except Exception:
        pass
    total = l.get("quantity_total") or 0
    if total and available / total < 0.25:
        return "low_stock"
    return "active"


def enrich_listing(l):
    """Attach honest, derived display fields to a listing row."""
    total = int(l.get("quantity_total") or 0)
    available = int(l.get("quantity_available") or 0)
    price = float(l.get("price_per_unit") or l.get("price") or 0)
    mandi = float(l.get("mandi_price") or 0)

    age_days, harvest_display, freshness_label = _harvest_label(l.get("harvest_date"))
    status = listing_status_for(l, available)
    sold_out = status in ("sold_out", "expired", "inactive")

    photo = l.get("image_url") or l.get("photo") or ""

    return dict(l, **{
        # The real price & stock — nothing is fabricated here.
        "live_price": round(price, 2),
        "price_change_pct": 0.0,
        "available_kg": available,
        "total_kg": total,
        "stock_pct": round((available / total) * 100) if total else 0,
        "unit": l.get("unit") or "Kg",
        "status": status,
        "sold_out": sold_out,
        "photo": photo,
        # Display metadata.
        "harvest_display": harvest_display,
        "harvest_age_days": age_days,
        "freshness_label": freshness_label,
        "mandi_price": mandi,
        "savings_vs_mandi": round(mandi - price, 2) if mandi and price else 0,
    })


def get_market():
    """Return the full marketplace catalogue with metadata."""
    listings = listing_model.list_listings()
    items = [enrich_listing(l) for l in listings]
    return {
        "items": items,
        "count": len(items),
        "updated_at": datetime.now().isoformat(),
        "next_price_refresh": (datetime.now().replace(hour=0, minute=0, second=0)
                               + timedelta(days=1)).isoformat(),
        "source": "database",
    }


def serialize_item(item):
    """Frontend-friendly shape of an order_item row."""
    return {
        "listing_id": item.get("listing_id"),
        "crop_name": item.get("crop_name_snapshot"),
        "qty": item.get("quantity"),
        "price": item.get("price_per_unit"),
        "subtotal": item.get("subtotal"),
        "farmer_id": item.get("farmer_id"),
        "farmer_phone": item.get("farmer_phone"),
    }


def serialize_order(order, items):
    """Serialize an order for the frontend (items come from order_items)."""
    from database.schema import ORDER_FLOW, ORDER_STATUS_LABELS

    status = order.get("status") or "ORDER_PLACED"
    step_index = ORDER_FLOW.index(status) if status in ORDER_FLOW else 0
    return dict(order, **{
        "items": [serialize_item(i) for i in items],
        "flow": [ORDER_STATUS_LABELS[s] for s in ORDER_FLOW],
        "step_index": step_index,
        "status_label": ORDER_STATUS_LABELS.get(status, status),
    })
