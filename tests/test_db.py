import pytest

from database.db import engine_info, get_conn


def test_production_requires_mysql(tmp_path):
    """In production the app must fail instead of silently using SQLite."""
    from app import create_app
    from config import config as global_config

    old_env = global_config.ENVIRONMENT
    old_engine = global_config.DB_ENGINE
    try:
        with pytest.raises(RuntimeError):
            create_app({
                'ENVIRONMENT': 'production',
                'DB_ENGINE': 'mysql',
                'MYSQL_HOST': '127.0.0.1',
                'MYSQL_PORT': 1,
                'MYSQL_DB': 'farmbridge',
            })
    finally:
        global_config.ENVIRONMENT = old_env
        global_config.DB_ENGINE = old_engine


def test_db_tables_created(app):
    info = engine_info()
    assert info['engine'] == 'sqlite'
    conn = get_conn()
    try:
        cur = conn.cursor()
        for table in ('users', 'farmers', 'consumers', 'listings', 'orders',
                      'order_items', 'pools', 'pool_joins', 'subscriptions'):
            cur.execute("SELECT COUNT(*) AS n FROM " + table)
            row = cur.fetchone()
            assert row is not None
    finally:
        conn.close()


def test_db_info_endpoint(client):
    r = client.get('/api/db-info')
    assert r.status_code == 200
    assert 'counts' in r.json
    assert 'consumers' in r.json['counts']
