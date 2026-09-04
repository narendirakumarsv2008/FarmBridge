"""Consumer marketplace routes."""

from datetime import datetime

from flask import Blueprint, request

from config import config
from services.marketplace_service import count_market_items, get_market_items
from utils.responses import success

bp = Blueprint('market', __name__, url_prefix='/api')


@bp.route('/market', methods=['GET'])
def market():
    try:
        limit = max(1, min(500, int(request.args.get('limit', config.MARKET_PAGE_SIZE))))
    except ValueError:
        limit = config.MARKET_PAGE_SIZE
    try:
        offset = max(0, int(request.args.get('offset', 0)))
    except ValueError:
        offset = 0

    items = get_market_items(limit=limit, offset=offset)
    total = count_market_items()
    return success({
        'items': items,
        'count': len(items),
        'total': total,
        'limit': limit,
        'offset': offset,
        'has_more': offset + len(items) < total,
        'updated_at': datetime.now().isoformat(),
    })
