"""Order and order item model helpers."""

from services.order_service import FLOW_CODES, ORDER_STATUS_CODE

VALID_STATUS_CODES = tuple(FLOW_CODES) + ('CANCELLED',)


def display_status(code):
    return ORDER_STATUS_CODE.get(code, code)


def step_index(code):
    if code in FLOW_CODES:
        return FLOW_CODES.index(code)
    return 0


def serialize(row):
    if not row:
        return None
    return {
        'id': row.get('id'),
        'order_code': row.get('order_code', ''),
        'buyer_phone': row.get('buyer_phone', ''),
        'buyer_name': row.get('buyer_name', ''),
        'consumer_type': row.get('consumer_type', ''),
        'subtotal': row.get('subtotal', 0),
        'delivery_fee': row.get('delivery_fee', 0),
        'discount': row.get('discount', 0),
        'total': row.get('total', 0),
        'payment_method': row.get('payment_method', ''),
        'payment_status': row.get('payment_status', ''),
        'status_code': row.get('status', ''),
        'status': display_status(row.get('status', '')),
        'address': row.get('address', ''),
        'source': row.get('source', ''),
        'created_at': row.get('created_at', ''),
    }
