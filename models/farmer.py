"""Farmer model helper."""


def serialize(row):
    if not row:
        return None
    return {
        'id': row.get('id'),
        'user_id': row.get('user_id'),
        'farm_name': row.get('farm_name', ''),
        'location': row.get('location', ''),
        'city': row.get('city', ''),
        'state': row.get('state', ''),
        'pincode': row.get('pincode', ''),
        'latitude': row.get('latitude'),
        'longitude': row.get('longitude'),
    }
