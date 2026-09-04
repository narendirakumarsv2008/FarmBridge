"""
HoReCa subscription service.

The contract rate is computed server-side from the listing price (the frontend
never sets the authoritative price). The delivery calendar is generated here
from active subscriptions (Daily / Alternate Days / Weekly / Monthly).
"""

from datetime import datetime, timedelta

import config
from models import listing as listing_model
from models import subscription as sub_model

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

VALID_FREQUENCIES = ("Daily", "Alternate Days", "Weekly", "Monthly", "Custom")


def contract_price_for_listing(listing_id):
    """−7% (HoReCa contract rate) of the listing's price, server-side."""
    listing = listing_model.get_listing(listing_id)
    if not listing:
        return None, None
    base = float(listing.get("price_per_unit") or listing.get("price") or 0)
    return round(base * config.Config.HORECA_CONTRACT_RATE, 2), listing.get("crop_name")


def create_subscription(consumer_phone, consumer_name, org_name, listing_id,
                        qty_kg, frequency, weekdays, time_slot, start_date, end_date):
    if not listing_id:
        return None, "Select produce from the live stock"
    price, crop_name = contract_price_for_listing(listing_id)
    if crop_name is None:
        return None, "Produce not found"
    if qty_kg <= 0:
        return None, "Quantity must be greater than zero"
    if frequency not in VALID_FREQUENCIES:
        return None, "Invalid frequency"
    if frequency in ("Weekly", "Custom") and not weekdays:
        return None, "Pick at least one delivery day"

    sub_id = sub_model.create_subscription(
        consumer_phone=consumer_phone, consumer_name=consumer_name, org_name=org_name,
        crop_name=crop_name, listing_id=listing_id, qty_kg=qty_kg,
        price_per_kg=price, frequency=frequency, weekdays=weekdays,
        time_slot=time_slot, start_date=start_date, end_date=end_date,
        status="active",
    )
    return {"id": sub_id, "crop_name": crop_name, "price_per_kg": price}, None


def update_subscription(sub_id, fields):
    sub = sub_model.get_subscription(sub_id)
    if not sub:
        return None, "Subscription not found"
    sub_model.update_subscription(sub_id, **fields)
    return sub_model.get_subscription(sub_id), None


def cancel_subscription(sub_id):
    sub_model.update_subscription(sub_id, active=0, status="cancelled")
    return True


def build_calendar(phone=None, days=30):
    """Expand active subscriptions into a per-day delivery schedule."""
    subs = sub_model.list_active_subscriptions(phone)
    schedule = {}
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for sub in subs:
        wd = sub.get("weekdays") or []
        try:
            start = datetime.strptime(sub.get("start_date") or "", "%Y-%m-%d")
        except Exception:
            start = today
        try:
            end = datetime.strptime(sub.get("end_date"), "%Y-%m-%d") if sub.get("end_date") else None
        except Exception:
            end = None

        for i in range(days):
            day = today + timedelta(days=i)
            if day < start or (end and day > end):
                continue
            name = WEEKDAY_NAMES[day.weekday()]
            freq = sub.get("frequency")
            hit = False
            if freq == "Daily":
                hit = True
            elif freq in ("Weekly", "Custom"):
                hit = name in wd
            elif freq == "Alternate Days":
                hit = ((day - start).days % 2) == 0
            elif freq == "Monthly":
                hit = day.day == start.day
            if hit:
                key = day.strftime("%Y-%m-%d")
                schedule.setdefault(key, []).append({
                    "sub_id": sub.get("id"),
                    "crop_name": sub.get("crop_name"),
                    "qty_kg": sub.get("qty_kg"),
                    "price_per_kg": sub.get("price_per_kg"),
                    "time_slot": sub.get("time_slot"),
                    "amount": round(float(sub.get("qty_kg") or 0) *
                                    float(sub.get("price_per_kg") or 0), 2),
                })

    total_kg = sum(d["qty_kg"] for v in schedule.values() for d in v)
    total_amt = sum(d["amount"] for v in schedule.values() for d in v)
    return {
        "schedule": schedule,
        "days": days,
        "total_kg": total_kg,
        "total_amount": round(total_amt, 2),
        "delivery_count": sum(len(v) for v in schedule.values()),
    }
