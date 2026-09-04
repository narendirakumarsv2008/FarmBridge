"""Listing model helper."""

ALLOWED_STATUSES = ('active', 'low_stock', 'sold_out', 'expired', 'inactive')


def serialize(row):
    if not row:
        return None
    return {
        'id': row.get('id'),
        'farmer_id': row.get('farmer_id'),
        'user_id': row.get('user_id'),
        'farmer_name': row.get('farmer_name', ''),
        'phone': row.get('phone', ''),
        'crop_name': row.get('crop_name', ''),
        'harvest_date': row.get('harvest_date', ''),
        'quantity_total': row.get('quantity_total', 0),
        'quantity_available': row.get('quantity_available', 0),
        'unit': row.get('unit', 'Kg'),
        'price_per_unit': row.get('price_per_unit', 0),
        'location': row.get('location', ''),
        'city': row.get('city', ''),
        'image_url': row.get('image_url', ''),
        'grade': row.get('grade', ''),
        'freshness_score': row.get('freshness_score', 0),
        'expiry_date': row.get('expiry_date', ''),
        'shelf_life': row.get('shelf_life', 0),
        'mandi_price': row.get('mandi_price', 0),
        'status': row.get('status', 'active'),
        'created_at': row.get('created_at', ''),
    }
