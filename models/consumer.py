"""Consumer model helper (replaces the old Buyer terminology)."""


def serialize(row):
    if not row:
        return None
    return {
        'id': row.get('id'),
        'user_id': row.get('user_id'),
        'consumer_type': row.get('consumer_type', ''),
        'email': row.get('email', ''),
        'delivery_address': row.get('delivery_address', ''),
        'landmark': row.get('landmark', ''),
        'city': row.get('city', ''),
        'state': row.get('state', ''),
        'pincode': row.get('pincode', ''),
        'latitude': row.get('latitude'),
        'longitude': row.get('longitude'),
        'organization_name': row.get('organization_name', ''),
    }
