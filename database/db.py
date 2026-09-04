"""
Farm Bridge database layer.

Responsibilities:
  * choose the storage engine (MySQL or SQLite) at startup,
  * create the schema (portable across engines),
  * run migrations,
  * provide short-lived connections whose cursors always return dict rows and
    accept `?` placeholders (translated to `%s` for MySQL).

Production rule: when ENVIRONMENT=production and DB_ENGINE=mysql, a MySQL
failure is FATAL (the app refuses to start) — it never silently degrades to a
local SQLite file. In development/testing, SQLite fallback is allowed so demos
never block.

All application code talks to this module; nothing else imports a driver.
"""

import logging
import os
import re
import sqlite3
import time
from datetime import datetime

import config

log = logging.getLogger("farmbridge.db")

BASE_DIR = config.Config.__dict__.get("BASE_DIR") or config.BASE_DIR

# Resolved on first use by init_db(): 'mysql' or 'sqlite'.
ENGINE = None

_TYPES = {
    "mysql": {"pk": "INTEGER PRIMARY KEY AUTO_INCREMENT",
              "text": "TEXT", "longtext": "LONGTEXT"},
    "sqlite": {"pk": "INTEGER PRIMARY KEY AUTOINCREMENT",
               "text": "TEXT", "longtext": "TEXT"},
}


# --------------------------------------------------------------------------
# Dialect helpers
# --------------------------------------------------------------------------

def _to_mysql(sql):
    """Translate the SQLite dialect used in app code into MySQL."""
    sql = sql.replace("?", "%s")
    if "ON CONFLICT" in sql:
        sql = re.sub(r"ON CONFLICT\s*\([^)]*\)\s*DO UPDATE SET",
                     "ON DUPLICATE KEY UPDATE", sql, flags=re.I)
        sql = re.sub(r"\bexcluded\.", "VALUES(", sql, flags=re.I)
    return sql


# --------------------------------------------------------------------------
# Cursor / Connection wrappers
# --------------------------------------------------------------------------

class Cursor:
    """Cursor wrapper: `?` placeholders and dict rows on both engines."""

    def __init__(self, cur, engine):
        self._cur = cur
        self._engine = engine
        self._last_insert_table = None

    def execute(self, sql, params=()):
        m = re.match(r"\s*INSERT\s+INTO\s+`?(\w+)`?", sql, re.I)
        if m:
            self._last_insert_table = m.group(1)
        if self._engine == "mysql":
            sql = _to_mysql(sql)
        self._cur.execute(sql, params)
        return self

    def executemany(self, sql, params):
        if self._engine == "mysql":
            sql = _to_mysql(sql)
        self._cur.executemany(sql, params)
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
        if self._engine == "mysql" and self._last_insert_table:
            for probe in ("SELECT LAST_INSERT_ID() AS id",
                          "SELECT MAX(id) AS id FROM " + self._last_insert_table):
                try:
                    self._cur.execute(probe)
                    row = self._cur.fetchone()
                    if row:
                        v = row["id"] if isinstance(row, dict) else row[0]
                        if v:
                            return int(v)
                except Exception:
                    continue
        return rid

    @property
    def rowcount(self):
        return self._cur.rowcount

    def close(self):
        try:
            self._cur.close()
        except Exception:
            pass


class Connection:
    """Thin wrapper enabling `with get_conn() as conn` on both drivers."""

    def __init__(self, raw, engine):
        self._raw = raw
        self.engine = engine

    def cursor(self):
        if self.engine == "mysql":
            import pymysql.cursors
            return Cursor(self._raw.cursor(pymysql.cursors.DictCursor), "mysql")
        return Cursor(self._raw.cursor(), "sqlite")

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
                pass
        else:
            self.rollback()
        self.close()
        return False


# --------------------------------------------------------------------------
# Connection factories
# --------------------------------------------------------------------------

def _sqlite_conn():
    path = config.Config.SQLITE_PATH
    if path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    raw = sqlite3.connect(path, timeout=30)
    raw.row_factory = sqlite3.Row
    return Connection(raw, "sqlite")


def _mysql_conn(db=None):
    import pymysql
    cfg = {
        "host": config.Config.MYSQL_HOST,
        "port": config.Config.MYSQL_PORT,
        "user": config.Config.MYSQL_USER,
        "password": config.Config.MYSQL_PASSWORD,
        "database": config.Config.MYSQL_DB if db is None else db,
        "charset": "utf8mb4",
        "autocommit": False,
        "connect_timeout": 5,
    }
    if not cfg["database"]:
        cfg.pop("database", None)
    raw = pymysql.connect(**cfg)
    return Connection(raw, "mysql")


def get_conn():
    """Open a connection using the engine chosen at startup."""
    if ENGINE == "mysql":
        return _mysql_conn()
    return _sqlite_conn()


# --------------------------------------------------------------------------
# Introspection helpers (used by migrations)
# --------------------------------------------------------------------------

def table_exists(conn, table):
    c = conn.cursor()
    if conn.engine == "sqlite":
        c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        )
        return c.fetchone() is not None
    c.execute("SHOW TABLES LIKE %s", (table,))
    return c.fetchone() is not None


def column_exists(conn, table, column):
    c = conn.cursor()
    if conn.engine == "sqlite":
        c.execute("PRAGMA table_info(%s)" % table)
        return any((r["name"] if isinstance(r, dict) else r[1]) == column
                   for r in c.fetchall())
    c.execute("SHOW COLUMNS FROM %s" % table)
    return any((r["Field"] if isinstance(r, dict) else r[0]) == column
               for r in c.fetchall())


def add_column(conn, table, column, ddl):
    """Add a column if missing. Idempotent across engines and test doubles."""
    if column_exists(conn, table, column):
        return
    try:
        conn.cursor().execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, ddl))
    except Exception as exc:
        # Some engines/drivers (or MySQL test doubles) can't introspect columns
        # reliably; if the column already exists the ALTER raises "duplicate".
        if "duplicate" in str(exc).lower():
            return
        raise


# --------------------------------------------------------------------------
# Engine selection + schema creation + migrations
# --------------------------------------------------------------------------

def _try_mysql():
    try:
        import pymysql  # noqa: F401
    except ImportError:
        log.warning("PyMySQL not installed — cannot use MySQL")
        return False

    # 1) Connect straight to the configured database. This is the common case:
    #    the database + user already exist (e.g. provisioned by the official
    #    MySQL Docker image or a managed host), so we must NOT require CREATE
    #    DATABASE privileges.
    try:
        conn = _mysql_conn(db=config.Config.MYSQL_DB)
        conn.close()
        return True
    except Exception as exc:
        log.info("MySQL direct connect failed (%s); attempting to create database",
                 str(exc).splitlines()[0][:160])

    # 2) Fallback: connect without a default database and create it if we can
    #    (used for fresh self-managed servers where the app user may create it).
    try:
        conn = _mysql_conn(db="")
        cur = conn.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS `%s` CHARACTER SET utf8mb4"
                    % config.Config.MYSQL_DB)
        conn.commit()
        conn.close()
        return True
    except Exception as exc:
        log.warning("MySQL unavailable: %s", str(exc).splitlines()[0][:160])
        return False


def init_db(engine=None, sqlite_path=None):
    """
    Choose an engine, create every table, and run migrations.

    Returns the active engine name ('mysql' or 'sqlite').
    """
    global ENGINE

    if sqlite_path:
        config.Config.SQLITE_PATH = sqlite_path

    requested = engine or config.Config.DB_ENGINE

    if requested == "mysql":
        # Retry for a little while: on shared platforms the database container
        # (or managed instance) may still be initialising while this app boots.
        # Without this, a slow MySQL startup would silently downgrade to SQLite.
        retries = max(1, int(os.environ.get("MYSQL_CONNECT_RETRIES", "10")))
        delay = float(os.environ.get("MYSQL_CONNECT_RETRY_DELAY", "3"))
        connected = False
        for attempt in range(1, retries + 1):
            if _try_mysql():
                ENGINE = "mysql"
                connected = True
                break
            log.warning("MySQL not ready (attempt %d/%d) — retrying in %.0fs",
                        attempt, retries, delay)
            time.sleep(delay)

        if not connected:
            if config.Config.ALLOW_SQLITE_FALLBACK:
                log.warning(
                    "Falling back to SQLite (ENVIRONMENT=%s allows this)",
                    config.Config.ENVIRONMENT,
                )
                ENGINE = "sqlite"
            else:
                raise RuntimeError(
                    "Production is configured to use MySQL but the server is "
                    "unreachable. Refusing to silently fall back to SQLite — "
                    "check MYSQL_HOST/MYSQL_USER/MYSQL_PASSWORD/MYSQL_DB."
                )
    else:
        ENGINE = "sqlite"

    t = _TYPES[ENGINE]
    from database.schema import SCHEMA

    conn = get_conn()
    try:
        cur = conn.cursor()
        for table, body in SCHEMA.items():
            ddl = "CREATE TABLE IF NOT EXISTS %s %s" % (table, body.format(**t))
            if ENGINE == "mysql":
                ddl += " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            cur.execute(ddl)
        conn.commit()
    finally:
        conn.close()

    _run_migrations()

    where = (
        "MySQL %s@%s:%s/%s" % (
            config.Config.MYSQL_USER, config.Config.MYSQL_HOST,
            config.Config.MYSQL_PORT, config.Config.MYSQL_DB,
        )
        if ENGINE == "mysql"
        else "SQLite %s" % config.Config.SQLITE_PATH
    )
    log.info("Storage engine: %s -> %s", ENGINE.upper(), where)
    return ENGINE


def _run_migrations():
    from database import migrations

    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT version FROM schema_migrations")
        applied = {r["version"] if isinstance(r, dict) else r[0]
                   for r in c.fetchall()}
        for version, description, func in migrations.MIGRATIONS:
            if version in applied:
                continue
            log.info("Applying migration %d: %s", version, description)
            func(conn)
            c.execute(
                "INSERT INTO schema_migrations (version, description, applied_at) "
                "VALUES (?, ?, ?)",
                (version, description, datetime.now().isoformat()),
            )
            conn.commit()
            log.info("Migration %d applied.", version)
    finally:
        conn.close()


def engine_info():
    if ENGINE == "mysql":
        target = "%s:%s/%s" % (
            config.Config.MYSQL_HOST, config.Config.MYSQL_PORT,
            config.Config.MYSQL_DB,
        )
    else:
        target = config.Config.SQLITE_PATH
    return {"engine": ENGINE, "target": target}
