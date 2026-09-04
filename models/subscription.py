"""HoReCa subscription entity access."""

import json
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


def create_subscription(**fields):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(
            """INSERT INTO subscriptions
               (consumer_phone, consumer_name, org_name, crop_name, listing_id,
                qty_kg, price_per_kg, frequency, weekdays, time_slot,
                start_date, end_date, active, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (fields.get("consumer_phone"), fields.get("consumer_name"),
             fields.get("org_name"), fields.get("crop_name"),
             fields.get("listing_id"), fields.get("qty_kg"),
             fields.get("price_per_kg"), fields.get("frequency"),
             json.dumps(fields.get("weekdays") or []),
             fields.get("time_slot", "6:00 AM - 8:00 AM"),
             fields.get("start_date") or datetime.now().strftime("%Y-%m-%d"),
             fields.get("end_date") or "", 1,
             fields.get("status", "active"), _now(), _now()),
        )
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def get_subscription(sub_id):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM subscriptions WHERE id=?", (sub_id,))
        return _dictify(c.fetchone())
    finally:
        conn.close()


def list_subscriptions(phone=None):
    conn = get_conn()
    try:
        c = conn.cursor()
        if phone:
            c.execute("SELECT * FROM subscriptions WHERE consumer_phone=? "
                      "ORDER BY id DESC", (phone,))
        else:
            c.execute("SELECT * FROM subscriptions ORDER BY id DESC")
        rows = [_dictify(r) for r in c.fetchall()]
        for r in rows:
            try:
                r["weekdays"] = json.loads(r.get("weekdays") or "[]")
            except Exception:
                r["weekdays"] = []
        return rows
    finally:
        conn.close()


def update_subscription(sub_id, **fields):
    allowed = {"qty_kg", "price_per_kg", "active", "status", "time_slot",
               "frequency", "weekdays", "start_date", "end_date"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    if "weekdays" in updates:
        updates["weekdays"] = json.dumps(updates["weekdays"] or [])
    if "active" in updates:
        updates["active"] = 1 if updates["active"] else 0
    updates["updated_at"] = _now()
    conn = get_conn()
    try:
        c = conn.cursor()
        sets = ", ".join("%s=?" % k for k in updates)
        c.execute("UPDATE subscriptions SET %s WHERE id=?" % sets,
                  tuple(updates.values()) + (sub_id,))
        conn.commit()
    finally:
        conn.close()


def delete_subscription(sub_id):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM subscriptions WHERE id=?", (sub_id,))
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()


def list_active_subscriptions(phone=None):
    conn = get_conn()
    try:
        c = conn.cursor()
        if phone:
            c.execute("SELECT * FROM subscriptions WHERE consumer_phone=? AND active=1",
                      (phone,))
        else:
            c.execute("SELECT * FROM subscriptions WHERE active=1")
        rows = [_dictify(r) for r in c.fetchall()]
        for r in rows:
            try:
                r["weekdays"] = json.loads(r.get("weekdays") or "[]")
            except Exception:
                r["weekdays"] = []
        return rows
    finally:
        conn.close()
