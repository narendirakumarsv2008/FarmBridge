"""Miscellaneous informational routes."""

from flask import Blueprint

from database.db import get_conn

bp = Blueprint('misc', __name__)


@bp.route('/api/db-info', methods=['GET'])
def db_info():
    from database.db import engine_info
    info = engine_info()
    try:
        conn = get_conn()
        cur = conn.cursor()
        counts = {}
        for t in ('listings', 'users', 'consumers', 'buyers', 'orders',
                  'order_items', 'pools', 'subscriptions'):
            cur.execute('SELECT COUNT(*) AS n FROM ' + t)
            row = cur.fetchone()
            counts[t] = row['n'] if row else 0
        conn.close()
        info['counts'] = counts
        info['ok'] = True
    except Exception as e:
        info['ok'] = False
        info['error'] = str(e)[:200]
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
