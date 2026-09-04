"""Consumer entity access (formerly "buyers")."""

from datetime import datetime

from database.db import get_conn


def _now():
    return datetime.now().isoformat()


def get_consumer(phone):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM consumers WHERE phone=?", (phone,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_consumer_by_id(consumer_id):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM consumers WHERE id=?", (consumer_id,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def upsert_consumer(phone, **fields):
    """Insert or update a consumer profile. `phone` is the unique key."""
    now = _now()
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT id FROM consumers WHERE phone=?", (phone,))
        row = c.fetchone()
        if not row:
            c.execute(
                """INSERT INTO consumers
                   (phone, name, email, consumer_type, delivery_address, landmark,
                    organization_name, city, state, pincode, latitude, longitude,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (phone, fields.get("name"), fields.get("email"),
                 fields.get("consumer_type"), fields.get("delivery_address"),
                 fields.get("landmark"), fields.get("organization_name"),
                 fields.get("city"), fields.get("state"), fields.get("pincode"),
                 fields.get("latitude"), fields.get("longitude"), now, now),
            )
        else:
            sets = []
            values = []
            for k in ("name", "email", "consumer_type", "delivery_address",
                      "landmark", "organization_name", "city", "state",
                      "pincode", "latitude", "longitude"):
                if k in fields and fields[k] is not None:
                    sets.append("%s=?" % k)
                    values.append(fields[k])
            if sets:
                sets.append("updated_at=?")
                values.append(now)
                c.execute("UPDATE consumers SET %s WHERE phone=?" % ", ".join(sets),
                          tuple(values) + (phone,))
        conn.commit()
    finally:
        conn.close()
    return get_consumer(phone)


def count_consumers():
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) AS n FROM consumers")
        return (dict(c.fetchone()) or {}).get("n", 0)
    finally:
        conn.close()
