"""User entity access."""

from datetime import datetime

from database.db import get_conn


def _now():
    return datetime.now().isoformat()


def get_user_by_phone(phone):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE phone=?", (phone,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id=?", (user_id,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_or_create_user(name, phone, role="consumer", email=None):
    """Return the existing user for `phone` or create a new one."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE phone=?", (phone,))
        row = c.fetchone()
        if row:
            user = dict(row)
            return user
        now = _now()
        c.execute(
            "INSERT INTO users (name, phone, email, role, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, phone, email, role, now, now),
        )
        conn.commit()
        return get_user_by_phone(phone)
    finally:
        conn.close()


def set_user_role(phone, role):
    """Promote a user's role if it is more privileged than current."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT role FROM users WHERE phone=?", (phone,))
        row = c.fetchone()
        current = (dict(row) or {}).get("role") or "consumer"
        # keep 'admin' sticky; farmer wins over consumer
        if current == "admin" or current == role:
            return
        if role == "admin" or (role == "farmer" and current == "consumer"):
            c.execute("UPDATE users SET role=?, updated_at=? WHERE phone=?",
                      (role, _now(), phone))
            conn.commit()
    finally:
        conn.close()


def update_user(phone, **fields):
    allowed = {"name", "email"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    updates["updated_at"] = _now()
    conn = get_conn()
    try:
        c = conn.cursor()
        sets = ", ".join("%s=?" % k for k in updates)  # placeholder rewritten per engine
        c.execute("UPDATE users SET %s WHERE phone=?" % sets,
                  tuple(updates.values()) + (phone,))
        conn.commit()
    finally:
        conn.close()


def count_users():
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) AS n FROM users")
        row = c.fetchone()
        return (dict(row) or {}).get("n", 0)
    finally:
        conn.close()
