"""
FarmBridge database layer.

Farmer listings (and every other record) are stored in MySQL when it is
configured, so the Buyer Portal loads its catalogue straight out of the
shared database. If no MySQL server is reachable the module transparently
falls back to the bundled SQLite file, which keeps local dev and this
sandbox working without a server install.

Configure MySQL with environment variables:

    DB_ENGINE=mysql
    MYSQL_HOST=localhost
    MYSQL_PORT=3306
    MYSQL_USER=farmbridge
    MYSQL_PASSWORD=secret
    MYSQL_DB=farmbridge

Everything else in the app talks to this module and never imports a
driver directly.
"""

import os
import re
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_PATH = os.path.join(BASE_DIR, 'farmbridge.db')

MYSQL_CONFIG = {
    'host': os.environ.get('MYSQL_HOST', '127.0.0.1'),
    'port': int(os.environ.get('MYSQL_PORT', 3306)),
    'user': os.environ.get('MYSQL_USER', 'root'),
    'password': os.environ.get('MYSQL_PASSWORD', ''),
    'database': os.environ.get('MYSQL_DB', 'farmbridge'),
}

# Resolved on first use by init_db(): either 'mysql' or 'sqlite'.
ENGINE = None
_REQUESTED = os.environ.get('DB_ENGINE', 'mysql').lower()


# --------------------------------------------------------------------------
# Schema — written once in portable form and translated per engine.
# --------------------------------------------------------------------------

SCHEMA = {
    'listings': """(
        id            {pk},
        farmer_name   VARCHAR(120),
        phone         VARCHAR(20),
        crop_name     VARCHAR(120),
        harvest_date  VARCHAR(40),
        quantity      VARCHAR(40),
        price         DOUBLE,
        location      VARCHAR(255),
        photo         {longtext},
        grade         VARCHAR(4),
        expiry_date   VARCHAR(40),
        shelf_life    INTEGER,
        freshness_score INTEGER,
        mandi_price   DOUBLE,
        platform_price DOUBLE,
        mandi_name    VARCHAR(255),
        status        VARCHAR(60),
        created_at    VARCHAR(40),
        voice_transcript {text},
        sold_kg       INTEGER DEFAULT 0
    )""",
    'users': """(
        id         {pk},
        name       VARCHAR(120),
        phone      VARCHAR(20),
        role       VARCHAR(40),
        created_at VARCHAR(40)
    )""",
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
    'orders': """(
        id           {pk},
        order_code   VARCHAR(40),
        buyer_phone  VARCHAR(20),
        buyer_name   VARCHAR(120),
        buyer_type   VARCHAR(20),
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
        created_at   VARCHAR(40)
    )""",
    'pools': """(
        id          {pk},
        crop_name   VARCHAR(120),
        listing_id  INTEGER,
        photo       {longtext},
        grade       VARCHAR(4),
        base_price  DOUBLE,
        target_kg   INTEGER,
        seeded_kg   INTEGER,
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
        qty_kg      INTEGER,
        joined_at   VARCHAR(40)
    )""",
    'subscriptions': """(
        id           {pk},
        buyer_phone  VARCHAR(20),
        buyer_name   VARCHAR(120),
        org_name     VARCHAR(190),
        crop_name    VARCHAR(120),
        listing_id   INTEGER,
        qty_kg       INTEGER,
        price_per_kg DOUBLE,
        frequency    VARCHAR(40),
        weekdays     VARCHAR(190),
        time_slot    VARCHAR(60),
        start_date   VARCHAR(40),
        end_date     VARCHAR(40),
        active       INTEGER DEFAULT 1,
        created_at   VARCHAR(40)
    )""",
}

_TYPES = {
    'mysql': {'pk': 'INTEGER PRIMARY KEY AUTO_INCREMENT',
              'text': 'TEXT', 'longtext': 'LONGTEXT'},
    'sqlite': {'pk': 'INTEGER PRIMARY KEY AUTOINCREMENT',
               'text': 'TEXT', 'longtext': 'TEXT'},
}


class Cursor:
    """Cursor wrapper that rewrites `?` placeholders for MySQL and always
    returns rows as dicts, so callers work identically on both engines."""

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
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    @property
    def lastrowid(self):
        rid = self._cur.lastrowid
        if rid:
            return rid
        # Real MySQL always reports lastrowid. Some MySQL-compatible servers
        # (and our sandbox test double) do not, so fall back to the id we can
        # read back from the table itself.
        if self._engine == 'mysql' and self._last_insert_table:
            for probe in ('SELECT LAST_INSERT_ID() AS id',
                          'SELECT MAX(id) AS id FROM ' + self._last_insert_table):
                try:
                    self._cur.execute(probe)
                    row = self._cur.fetchone()
                    if row:
                        v = row['id'] if isinstance(row, dict) else row[0]
                        if v:
                            return int(v)
                except Exception:
                    continue
        return rid

    @property
    def rowcount(self):
        return self._cur.rowcount

    def close(self):
        self._cur.close()


class Connection:
    """Thin wrapper so `with get_conn() as conn` works on both drivers."""

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
                pass
        self.close()
        return False


def _to_mysql(sql):
    """Translate the SQLite dialect used in app.py into MySQL."""
    sql = sql.replace('?', '%s')
    # SQLite upsert -> MySQL upsert
    if 'ON CONFLICT' in sql:
        sql = re.sub(r'ON CONFLICT\s*\([^)]*\)\s*DO UPDATE SET',
                     'ON DUPLICATE KEY UPDATE', sql, flags=re.I)
        sql = re.sub(r'\bexcluded\.', 'VALUES(', sql, flags=re.I)
        # close the VALUES( we just opened on each assignment
        sql = re.sub(r'VALUES\((\w+)', r'VALUES(\1)', sql)
    return sql


def _sqlite_conn():
    raw = sqlite3.connect(SQLITE_PATH)
    raw.row_factory = sqlite3.Row
    return Connection(raw, 'sqlite')


def _mysql_conn(db=None):
    import pymysql
    cfg = dict(MYSQL_CONFIG)
    if db is not None:
        cfg['database'] = db
    elif not cfg['database']:
        cfg.pop('database', None)
    raw = pymysql.connect(
        host=cfg['host'], port=cfg['port'], user=cfg['user'],
        password=cfg['password'],
        database=cfg.get('database'),
        charset='utf8mb4', autocommit=False, connect_timeout=5)
    return Connection(raw, 'mysql')


def get_conn():
    """Open a connection using the engine chosen at startup."""
    if ENGINE == 'mysql':
        return _mysql_conn()
    return _sqlite_conn()


def _try_mysql():
    """Return True if we can reach MySQL and ensure the database exists."""
    try:
        import pymysql  # noqa: F401
    except ImportError:
        print('[db] pymysql not installed — falling back to SQLite')
        return False
    try:
        # connect without a database first so we can CREATE DATABASE
        conn = _mysql_conn(db='')
        cur = conn.cursor()
        cur.execute('CREATE DATABASE IF NOT EXISTS `%s` '
                    'CHARACTER SET utf8mb4' % MYSQL_CONFIG['database'])
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print('[db] MySQL unavailable (%s) — falling back to SQLite' %
              str(e).split('\n')[0][:110])
        return False


def init_db():
    """Pick an engine, create every table, and report which one is live."""
    global ENGINE
    if _REQUESTED == 'mysql' and _try_mysql():
        ENGINE = 'mysql'
    else:
        ENGINE = 'sqlite'

    t = _TYPES[ENGINE]
    conn = get_conn()
    cur = conn.cursor()
    for table, body in SCHEMA.items():
        ddl = 'CREATE TABLE IF NOT EXISTS %s %s' % (table, body.format(**t))
        if ENGINE == 'mysql':
            ddl += ' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4'
        cur.execute(ddl)
    # older SQLite files may predate sold_kg
    if ENGINE == 'sqlite':
        try:
            cur.execute('ALTER TABLE listings ADD COLUMN sold_kg INTEGER DEFAULT 0')
        except Exception:
            pass
    conn.commit()
    conn.close()

    where = ('MySQL %s@%s:%s/%s' % (MYSQL_CONFIG['user'], MYSQL_CONFIG['host'],
                                    MYSQL_CONFIG['port'], MYSQL_CONFIG['database'])
             if ENGINE == 'mysql' else 'SQLite %s' % SQLITE_PATH)
    print('[db] storage engine: %s -> %s' % (ENGINE.upper(), where))
    return ENGINE


def engine_info():
    return {
        'engine': ENGINE,
        'target': ('%s:%s/%s' % (MYSQL_CONFIG['host'], MYSQL_CONFIG['port'],
                                 MYSQL_CONFIG['database'])
                   if ENGINE == 'mysql' else SQLITE_PATH),
    }
