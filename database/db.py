"""
FarmBridge database layer.

All persistence goes through this module so application code never imports a
driver directly. MySQL is the production engine; SQLite is supported for local
development and tests. In production the app will NOT silently fall back to
SQLite - it fails with a clear error instead.
"""

import os
import re
import sqlite3

from config import config as DEFAULT_CONFIG

# Resolved on first use by init_db(): 'mysql' or 'sqlite'.
ENGINE = None
_CFG = DEFAULT_CONFIG


# --------------------------------------------------------------------------
# Portable schema. SQLite accepts these definitions directly; MySQL gets the
# CREATE TABLE ... ENGINE=InnoDB suffix and the placeholders are translated.
# --------------------------------------------------------------------------

SCHEMA = {
    'users': """(
        id            {pk},
        name          VARCHAR(120),
        phone         VARCHAR(20) UNIQUE,
        email         VARCHAR(190),
        role          VARCHAR(40) DEFAULT 'consumer',
        otp_code      VARCHAR(12),
        otp_expires_at VARCHAR(40),
        created_at    VARCHAR(40),
        updated_at    VARCHAR(40)
    )""",
    'farmers': """(
        id            {pk},
        user_id       INTEGER,
        farm_name     VARCHAR(190),
        location      VARCHAR(255),
        city          VARCHAR(120),
        state         VARCHAR(120),
        pincode       VARCHAR(12),
        latitude      DOUBLE,
        longitude     DOUBLE,
        created_at    VARCHAR(40),
        updated_at    VARCHAR(40)
    )""",
    'consumers': """(
        id            {pk},
        user_id       INTEGER,
        consumer_type VARCHAR(20),
        email         VARCHAR(190),
        delivery_address {text},
        landmark      VARCHAR(190),
        city          VARCHAR(120),
        state         VARCHAR(120),
        pincode       VARCHAR(12),
        latitude      DOUBLE,
        longitude     DOUBLE,
        organization_name VARCHAR(190),
        created_at    VARCHAR(40),
        updated_at    VARCHAR(40)
    )""",
    # Legacy buyers table retained for backward compatibility while the app
    # migrates to `consumers`.
    'buyers': """(
        phone      VARCHAR(20) PRIMARY KEY,
        name       VARCHAR(120),
        email      VARCHAR(190),
        address    {text},
        landmark   VARCHAR(190),
        city       VARCHAR(120),
        pincode    VARCHAR(12),
        latitude   DOUBLE,
        longitude  DOUBLE,
        buyer_type VARCHAR(20),
        org_name   VARCHAR(190),
        created_at VARCHAR(40),
        updated_at VARCHAR(40)
    )""",
    'listings': """(
        id            {pk},
        farmer_id     INTEGER,
        user_id       INTEGER,
        farmer_name   VARCHAR(120),
        phone         VARCHAR(20),
        crop_name     VARCHAR(120),
        harvest_date  VARCHAR(40),
        quantity      VARCHAR(40),
        quantity_total DOUBLE DEFAULT 0,
        quantity_available DOUBLE DEFAULT 0,
        unit          VARCHAR(20) DEFAULT 'Kg',
        price         DOUBLE,
        price_per_unit DOUBLE DEFAULT 0,
        location      VARCHAR(255),
        city          VARCHAR(120),
        photo         {longtext},
        image_url     VARCHAR(500),
        image_path    VARCHAR(500),
        grade         VARCHAR(4),
        expiry_date   VARCHAR(40),
        shelf_life    INTEGER,
        freshness_score INTEGER,
        mandi_price   DOUBLE,
        platform_price DOUBLE,
        mandi_name    VARCHAR(255),
        status        VARCHAR(60) DEFAULT 'active',
        created_at    VARCHAR(40),
        updated_at    VARCHAR(40),
        voice_transcript {text},
        sold_kg       DOUBLE DEFAULT 0
    )""",
    'orders': """(
        id           {pk},
        order_code   VARCHAR(40),
        buyer_user_id INTEGER,
        consumer_id  INTEGER,
        buyer_phone  VARCHAR(20),
        buyer_name   VARCHAR(120),
        consumer_type VARCHAR(20),
        items        {text},
        subtotal     DOUBLE,
        delivery_fee DOUBLE,
        discount     DOUBLE,
        total        DOUBLE,
        payment_method VARCHAR(40),
        payment_status VARCHAR(40),
        status       VARCHAR(60),
        address      {text},
        eta_minutes  INTEGER,
        source       VARCHAR(40),
        stock_restored INTEGER DEFAULT 0,
        created_at   VARCHAR(40),
        updated_at   VARCHAR(40)
    )""",
    'order_items': """(
        id            {pk},
        order_id      INTEGER,
        listing_id    INTEGER,
        crop_name_snapshot VARCHAR(120),
        quantity      DOUBLE,
        unit          VARCHAR(20) DEFAULT 'Kg',
        price_per_unit DOUBLE,
        subtotal      DOUBLE,
        farmer_id     INTEGER,
        created_at    VARCHAR(40)
    )""",
    'pools': """(
        id          {pk},
        crop_name   VARCHAR(120),
        listing_id  INTEGER,
        photo       {longtext},
        grade       VARCHAR(4),
        base_price  DOUBLE,
        target_kg   DOUBLE,
        seeded_kg   DOUBLE,
        ends_at     VARCHAR(40),
        location    VARCHAR(255),
        farmer_name VARCHAR(120),
        status      VARCHAR(20),
        created_at  VARCHAR(40)
    )""",
    'pool_joins': """(
        id          {pk},
        pool_id     INTEGER,
        buyer_phone VARCHAR(20),
        buyer_name  VARCHAR(120),
        org_name    VARCHAR(190),
        qty_kg      DOUBLE,
        joined_at   VARCHAR(40)
    )""",
    'subscriptions': """(
        id           {pk},
        buyer_phone  VARCHAR(20),
        buyer_name   VARCHAR(120),
        org_name     VARCHAR(190),
        crop_name    VARCHAR(120),
        listing_id   INTEGER,
        qty_kg       DOUBLE,
        price_per_kg DOUBLE,
        frequency    VARCHAR(40),
        weekdays     VARCHAR(190),
        time_slot    VARCHAR(60),
        start_date   VARCHAR(40),
        end_date     VARCHAR(40),
        active       INTEGER DEFAULT 1,
        status       VARCHAR(40) DEFAULT 'active',
        created_at   VARCHAR(40)
    )""",
    'sessions': """(
        id          {pk},
        user_id     INTEGER,
        token       VARCHAR(500),
        expires_at  VARCHAR(40),
        created_at  VARCHAR(40)
    )""",
    'delivery_tracking': """(
        id          {pk},
        order_id    INTEGER,
        status      VARCHAR(60),
        note        VARCHAR(255),
        created_at  VARCHAR(40)
    )""",
}

_TYPES = {
    'mysql': {
        'pk': 'INTEGER PRIMARY KEY AUTO_INCREMENT',
        'text': 'TEXT',
        'longtext': 'LONGTEXT',
        'double': 'DOUBLE',
        'bool': 'TINYINT(1)',
    },
    'sqlite': {
        'pk': 'INTEGER PRIMARY KEY AUTOINCREMENT',
        'text': 'TEXT',
        'longtext': 'TEXT',
        'double': 'REAL',
        'bool': 'INTEGER',
    },
}

# Columns added to existing tables so an old farmbridge.db / MySQL schema can
# be upgraded in place. Each value is a portable, engine-safe column DDL.
_COLUMN_MIGRATIONS = {
    'listings': {
        'farmer_id': 'farmer_id INTEGER',
        'user_id': 'user_id INTEGER',
        'quantity_total': 'DOUBLE DEFAULT 0',
        'quantity_available': 'DOUBLE DEFAULT 0',
        'unit': "VARCHAR(20) DEFAULT 'Kg'",
        'price_per_unit': 'DOUBLE DEFAULT 0',
        'city': 'VARCHAR(120)',
        'image_url': 'VARCHAR(500)',
        'image_path': 'VARCHAR(500)',
        'updated_at': 'VARCHAR(40)',
        'status': "VARCHAR(60) DEFAULT 'active'",
    },
    'users': {
        'email': 'VARCHAR(190)',
        'role': "VARCHAR(40) DEFAULT 'consumer'",
        'otp_code': 'VARCHAR(12)',
        'otp_expires_at': 'VARCHAR(40)',
        'updated_at': 'VARCHAR(40)',
    },
    'orders': {
        'buyer_user_id': 'INTEGER',
        'consumer_id': 'INTEGER',
        'consumer_type': 'VARCHAR(20)',
        'updated_at': 'VARCHAR(40)',
        'stock_restored': 'INTEGER DEFAULT 0',
    },
    'pool_joins': {
        'consumer_id': 'INTEGER',
    },
    'subscriptions': {
        'status': "VARCHAR(40) DEFAULT 'active'",
    },
}


def _to_mysql(sql):
    sql = sql.replace('?', '%s')
    if 'ON CONFLICT' in sql:
        sql = re.sub(
            r'ON CONFLICT\s*\([^)]*\)\s*DO UPDATE SET',
            'ON DUPLICATE KEY UPDATE',
            sql,
            flags=re.I,
        )
        sql = re.sub(r'\bexcluded\.', 'VALUES(', sql, flags=re.I)
        sql = re.sub(r'VALUES\((\w+)', r'VALUES(\1)', sql)
    return sql


class Cursor:
    def __init__(self, cur, engine):
        self._cur = cur
        self._engine = engine
        self._last_insert_table = None

    def execute(self, sql, params=()):
        m = re.match(r'\s*INSERT\s+INTO\s+`?(\w+)`?', sql, re.I)
        if m:
            self._last_insert_table = m.group(1)
        if self._engine == 'mysql':
            sql = _to_mysql(sql)
        self._cur.execute(sql, params)
        return self

    def fetchone(self):
        return _row_to_dict(self._cur.fetchone())

    def fetchall(self):
        return [_row_to_dict(r) for r in self._cur.fetchall()]

    @property
    def lastrowid(self):
        rid = self._cur.lastrowid
        if rid:
            return int(rid)
        if self._engine == 'mysql' and self._last_insert_table:
            for probe in (
                'SELECT LAST_INSERT_ID() AS id',
                'SELECT MAX(id) AS id FROM ' + self._last_insert_table,
            ):
                try:
                    self._cur.execute(probe)
                    row = self._cur.fetchone()
                    if row and row.get('id'):
                        return int(row['id'])
                except Exception:
                    continue
        return rid if rid is not None else 0

    @property
    def rowcount(self):
        return self._cur.rowcount

    def close(self):
        self._cur.close()


def _row_to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    return {k: row[k] for k in row.keys()}


class Connection:
    def __init__(self, raw, engine):
        self._raw = raw
        self.engine = engine

    def cursor(self):
        if self.engine == 'mysql':
            import pymysql.cursors
            return Cursor(self._raw.cursor(pymysql.cursors.DictCursor), 'mysql')
        return Cursor(self._raw.cursor(), 'sqlite')

    def commit(self):
        self._raw.commit()

    def rollback(self):
        try:
            self._raw.rollback()
        except Exception:
            pass

    def close(self):
        try:
            self._raw.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            try:
                self.commit()
            except Exception:
                try:
                    self.rollback()
                except Exception:
                    pass
        else:
            self.rollback()
        self.close()
        return False


def _sqlite_conn(path=None):
    raw = sqlite3.connect(path or _CFG.SQLITE_PATH)
    raw.row_factory = sqlite3.Row
    # isolation_level=None puts SQLite into manual-transaction mode so callers
    # can use BEGIN IMMEDIATE for stock operations.
    raw.isolation_level = None
    return Connection(raw, 'sqlite')


def begin(conn):
    """Start an explicit transaction when the engine does not do it itself."""
    if conn.engine == 'sqlite':
        conn.cursor().execute('BEGIN IMMEDIATE')


def _mysql_conn(db=None):
    import pymysql
    cfg = dict(
        host=_CFG.MYSQL_HOST,
        port=_CFG.MYSQL_PORT,
        user=_CFG.MYSQL_USER,
        password=_CFG.MYSQL_PASSWORD,
        database=_CFG.MYSQL_DB if db is None else db,
        charset='utf8mb4',
        autocommit=False,
        connect_timeout=5,
    )
    if db is not None and not db:
        cfg.pop('database', None)
    raw = pymysql.connect(**cfg)
    return Connection(raw, 'mysql')


def get_conn():
    if ENGINE == 'mysql':
        return _mysql_conn()
    return _sqlite_conn()


def _try_mysql(cfg):
    try:
        import pymysql  # noqa: F401
    except ImportError:
        if not cfg.allow_sqlite_fallback:
            raise RuntimeError('PyMySQL is required for production MySQL mode')
        return False
    try:
        conn = _mysql_conn(db='')
        cur = conn.cursor()
        cur.execute('CREATE DATABASE IF NOT EXISTS `%s` '
                    'CHARACTER SET utf8mb4' % cfg.MYSQL_DB)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        msg = str(e).split('\n')[0][:160]
        if not cfg.allow_sqlite_fallback:
            raise RuntimeError(
                'Production requires a reachable MySQL database: %s' % msg
            )
        print('[db] MySQL unavailable (%s)' % msg)
        return False


def _engine_type(engine):
    return _TYPES[engine]


def _table_columns(conn, table):
    cur = conn.cursor()
    if conn.engine == 'sqlite':
        cur.execute('PRAGMA table_info("%s")' % table)
        rows = cur.fetchall()
        return [r['name'] for r in rows]
    cur.execute(
        "SELECT COLUMN_NAME AS name FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ?", (table,))
    return [r['name'] for r in cur.fetchall()]


def _ensure_column(conn, table, col, definition):
    try:
        existing = _table_columns(conn, table)
    except Exception:
        return
    if col in existing:
        return
    cur = conn.cursor()
    cur.execute('ALTER TABLE %s ADD COLUMN %s %s' % (table, col, definition))


def _apply_column_migrations(conn):
    for table, cols in _COLUMN_MIGRATIONS.items():
        for col, definition in cols.items():
            _ensure_column(conn, table, col, definition)


def init_db(cfg=None):
    global ENGINE, _CFG
    _CFG = cfg or DEFAULT_CONFIG
    if ENGINE:
        # Allow tests to re-init against a different sqlite file.
        if _CFG.is_test and _CFG.DB_ENGINE == 'sqlite':
            ENGINE = None
        elif ENGINE == _CFG.DB_ENGINE and _CFG.ENVIRONMENT == 'development':
            # Same dev engine already initialised; no need to reconnect.
            return ENGINE
        else:
            # Config changed (or production MySQL validation required): force
            # re-init so the app never silently uses a stale engine.
            ENGINE = None

    if _CFG.DB_ENGINE == 'mysql' and _try_mysql(_CFG):
        ENGINE = 'mysql'
    elif _CFG.allow_sqlite_fallback:
        ENGINE = 'sqlite'
    else:
        # Production must fail loudly instead of silently degrading.
        raise RuntimeError(
            'Database engine %s is not available. Check ENVIRONMENT / '
            'DB_ENGINE / MySQL credentials.' % _CFG.DB_ENGINE
        )

    t = _engine_type(ENGINE)
    conn = get_conn()
    try:
        cur = conn.cursor()
        for table, body in SCHEMA.items():
            ddl = 'CREATE TABLE IF NOT EXISTS %s %s' % (table, body.format(**t))
            if ENGINE == 'mysql':
                ddl += ' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4'
            cur.execute(ddl)
        _apply_column_migrations(conn)
        conn.commit()
    finally:
        conn.close()

    where = ('MySQL %s@%s:%s/%s' % (
        _CFG.MYSQL_USER, _CFG.MYSQL_HOST, _CFG.MYSQL_PORT, _CFG.MYSQL_DB)
        if ENGINE == 'mysql' else 'SQLite %s' % _CFG.SQLITE_PATH)
    print('[db] storage engine: %s -> %s' % (ENGINE.upper(), where))
    return ENGINE


def engine_info(cfg=None):
    c = cfg or _CFG
    target = ('%s:%s/%s' % (c.MYSQL_HOST, c.MYSQL_PORT, c.MYSQL_DB)
              if ENGINE == 'mysql' else c.SQLITE_PATH)
    return {
        'engine': ENGINE,
        'target': target,
        'environment': c.ENVIRONMENT,
    }
