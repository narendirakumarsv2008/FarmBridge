"""Consumer profile service.

Writes to the primary `consumers` table. A compatibility copy is also written
to the legacy `buyers` table so any older frontend/client route that still
reads `/api/buyer/profile` keeps working during migration.
"""

from datetime import datetime

from database.db import begin, get_conn
from utils.validators import validate_consumer_type, validate_email, validate_name, validate_phone


class ConsumerError(Exception):
    def __init__(self, message, code='VALIDATION_ERROR', status=400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _row_dict(r):
    if r is None:
        return None
    if isinstance(r, dict):
        return dict(r)
    return {k: r[k] for k in r.keys()}


def get_consumer_by_phone(phone):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM consumers WHERE user_id IN '
                    '(SELECT id FROM users WHERE phone=?) ORDER BY id DESC LIMIT 1', (phone,))
        row = cur.fetchone()
        if not row:
            # legacy buyers table fallback
            cur.execute('SELECT * FROM buyers WHERE phone=?', (phone,))
            legacy = cur.fetchone()
            if not legacy:
                return None
            return {
                'id': None,
                'user_id': None,
                'phone': legacy.get('phone'),
                'name': legacy.get('name'),
                'email': legacy.get('email'),
                'delivery_address': legacy.get('address'),
                'landmark': legacy.get('landmark'),
                'city': legacy.get('city'),
                'pincode': legacy.get('pincode'),
                'latitude': legacy.get('latitude'),
                'longitude': legacy.get('longitude'),
                'consumer_type': legacy.get('buyer_type', '').lower(),
                'organization_name': legacy.get('org_name'),
                'legacy': True,
            }
        return _row_dict(row)
    finally:
        conn.close()


def save_consumer_profile(payload, user):
    name = (payload.get('name') or '').strip()
    phone = (payload.get('phone') or '').strip()
    email = (payload.get('email') or '').strip()
    address = (payload.get('address') or payload.get('delivery_address') or '').strip()
    consumer_type_raw = (payload.get('consumer_type') or payload.get('buyer_type') or '').strip()

    if not name or not phone:
        raise ConsumerError('Name and phone come from login and are required')

    ok, msg, digits = validate_phone(phone)
    if not ok:
        raise ConsumerError('Invalid phone: %s' % msg)
    ok, msg = validate_email(email)
    if not ok:
        raise ConsumerError(msg)
    if len(address) < 8:
        raise ConsumerError('Home address must be at least 8 characters')
    ok, msg = validate_consumer_type(consumer_type_raw)
    if not ok:
        raise ConsumerError(msg)

    consumer_type = consumer_type_raw.lower()
    now = datetime.now().isoformat()
    user_id = user.get('user_id')
    # Ensure the user row matches the submitted identity.
    conn = get_conn()
    try:
        begin(conn)
        cur = conn.cursor()
        if user_id:
            cur.execute('UPDATE users SET name=?, email=?, phone=?, updated_at=? WHERE id=?',
                        (name, email, digits, now, user_id))
        # Consumers (primary)
        cur.execute('SELECT * FROM consumers WHERE user_id=? ORDER BY id DESC LIMIT 1',
                    (user_id,))
        consumer = cur.fetchone()
        if consumer:
            cur.execute(
                """UPDATE consumers SET consumer_type=?, email=?, delivery_address=?,
                   landmark=?, city=?, state=?, pincode=?, latitude=?, longitude=?,
                   organization_name=?, updated_at=? WHERE id=?""",
                (consumer_type, email, address, payload.get('landmark', ''),
                 payload.get('city', ''), payload.get('state', ''), payload.get('pincode', ''),
                 payload.get('latitude'), payload.get('longitude'),
                 payload.get('org_name') or payload.get('organization_name', ''),
                 now, consumer['id']))
            consumer_id = consumer['id']
        else:
            cur.execute(
                """INSERT INTO consumers
                (user_id,consumer_type,email,delivery_address,landmark,city,state,pincode,
                 latitude,longitude,organization_name,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (user_id, consumer_type, email, address, payload.get('landmark', ''),
                 payload.get('city', ''), payload.get('state', ''), payload.get('pincode', ''),
                 payload.get('latitude'), payload.get('longitude'),
                 payload.get('org_name') or payload.get('organization_name', ''),
                 now, now))
            consumer_id = cur.lastrowid

        # Legacy buyers compatibility copy.
        cur.execute(
            """INSERT INTO buyers
            (phone,name,email,address,landmark,city,pincode,latitude,longitude,buyer_type,
             org_name,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(phone) DO UPDATE SET
              name=excluded.name, email=excluded.email, address=excluded.address,
              landmark=excluded.landmark, city=excluded.city, pincode=excluded.pincode,
              latitude=excluded.latitude, longitude=excluded.longitude,
              buyer_type=excluded.buyer_type, org_name=excluded.org_name,
              updated_at=excluded.updated_at""",
            (digits, name, email, address, payload.get('landmark', ''),
             payload.get('city', ''), payload.get('pincode', ''),
             payload.get('latitude'), payload.get('longitude'),
             consumer_type.capitalize(),
             payload.get('org_name') or payload.get('organization_name', ''), now, now))
        conn.commit()
    finally:
        conn.close()

    return {
        'phone': digits,
        'name': name,
        'email': email,
        'address': address,
        'delivery_address': address,
        'consumer_type': consumer_type,
        'buyer_type': consumer_type.capitalize(),
        'org_name': payload.get('org_name') or payload.get('organization_name', ''),
        'organization_name': payload.get('org_name') or payload.get('organization_name', ''),
    }
