"""User model helper."""


def public_user(row):
    if not row:
        return None
    return {
        'id': row.get('id'),
        'name': row.get('name', ''),
        'phone': row.get('phone', ''),
        'email': row.get('email', ''),
        'role': row.get('role', 'consumer'),
        'created_at': row.get('created_at', ''),
    }
