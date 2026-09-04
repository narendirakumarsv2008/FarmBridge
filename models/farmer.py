"""Farmer entity access."""

from datetime import datetime

from database.db import get_conn


def _now():
    return datetime.now().isoformat()


def get_farmer_by_user_id(user_id):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM farmers WHERE user_id=?", (user_id,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_farmer_by_phone(phone):
    """Resolve a farmer row via the user's phone."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT f.* FROM farmers f JOIN users u ON u.id = f.user_id "
            "WHERE u.phone=?",
            (phone,),
        )
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_or_create_farmer(user_id, location=None, farm_name=None):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM farmers WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if row:
            return dict(row)
        now = _now()
        c.execute(
            "INSERT INTO farmers (user_id, farm_name, location, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, farm_name, location, now, now),
        )
        conn.commit()
        c.execute("SELECT * FROM farmers WHERE user_id=?", (user_id,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def upsert_farmer(user_id, **fields):
    """Create or update a farmer profile row for a user."""
    allowed = {
        "farm_name", "location", "city", "state", "pincode",
        "latitude", "longitude",
    }
    data = {k: fields.get(k) for k in allowed if fields.get(k) is not None}
    now = _now()

    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT id FROM farmers WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if not row:
            c.execute(
                "INSERT INTO farmers (user_id, farm_name, location, city, state, "
                "pincode, latitude, longitude, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, data.get("farm_name"), data.get("location"),
                 data.get("city"), data.get("state"), data.get("pincode"),
                 data.get("latitude"), data.get("longitude"), now, now),
            )
        else:
            sets = ", ".join("%s=?" % k for k in data)
            if sets:
                c.execute("UPDATE farmers SET %s, updated_at=? WHERE user_id=?"
                          % sets,
                          tuple(data.values()) + (now, user_id))
        conn.commit()
    finally:
        conn.close()
    return get_farmer_by_user_id(user_id)
