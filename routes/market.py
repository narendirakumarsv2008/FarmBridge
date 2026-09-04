"""Consumer marketplace routes."""

from datetime import datetime

from flask import Blueprint

from services.marketplace_service import get_market_items
from utils.responses import success

bp = Blueprint('market', __name__, url_prefix='/api')


@bp.route('/market', methods=['GET'])
def market():
    items = get_market_items()
    return success({
        'items': items,
        'count': len(items),
        'updated_at': datetime.now().isoformat(),
    })
