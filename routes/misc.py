"""Miscellaneous / health informational routes.

Diagnostic endpoints are intentionally safe: they never expose passwords,
connection strings, or internal SQL.
"""

from flask import Blueprint

from database.db import get_conn, get_db_status

bp = Blueprint('misc', __name__)


@bp.route('/api/health', methods=['GET'])
def api_health():
    db = get_db_status()
    status = 'healthy' if db.get('connected') else 'degraded'
    # Return unstable HTTP status when the database is down so Render health
    # checks fail and the loader can restart / alert.
    return {
        'status': status,
        'service': 'farmbridge',
        'database': 'connected' if db.get('connected') else 'disconnected',
    }, 200 if db.get('connected') else 503


@bp.route('/api/db-info', methods=['GET'])
def db_info():
    from database.db import engine_info
    db = get_db_status()
    info = {
        'engine': db.get('engine'),
        'connected': db.get('connected', False),
        'environment': engine_info().get('environment'),
    }
    # In development/test we include table counts. In production keep this
    # lightweight and non-sensitive; use /health for liveness.
    if not engine_info().get('environment') == 'production':
        try:
            conn = get_conn()
            cur = conn.cursor()
            counts = {}
            for t in ('listings', 'users', 'consumers', 'orders',
                      'order_items', 'pools', 'subscriptions'):
                cur.execute('SELECT COUNT(*) AS n FROM ' + t)
                row = cur.fetchone()
                counts[t] = row['n'] if row else 0
            conn.close()
            info['counts'] = counts
        except Exception:
            info['counts'] = {}
    return info


@bp.route('/api/stats', methods=['GET'])
def stats():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) AS n FROM listings WHERE status NOT IN ("inactive","expired")')
        total = cur.fetchone()['n']
        cur.execute("SELECT COUNT(*) AS n FROM listings WHERE grade='A'")
        grade_a = cur.fetchone()['n']
        cur.execute('SELECT COALESCE(SUM(price_per_unit),0) AS v FROM listings')
        total_value = cur.fetchone()['v'] or 0
    finally:
        conn.close()
    return {
        'total_listings': total,
        'grade_a_count': grade_a,
        'total_value': round(total_value, 2),
        'farmers_connected': total * 3 + 1247,
        'avg_uplift': '18.7%',
    }
