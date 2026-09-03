"""
Dev-only MySQL server for sandboxes without a real mysqld.

Speaks the genuine MySQL wire protocol (via mysql-mimic) so the app's
pymysql driver, SQL dialect and upserts are all exercised for real, while
the storage underneath is a SQLite file. Use ONLY for testing; in
production point MYSQL_HOST/USER/PASSWORD at a real MySQL server.

    python3 tools/mysql_test_server.py --port 3307 --store /tmp/fb_mysql.db
"""

import argparse
import asyncio
import re
import sqlite3
import os

from mysql_mimic import MysqlServer, Session


def _translate(sql):
    """Rewrite the MySQL dialect the app emits into SQLite equivalents."""
    s = sql.strip()
    low = s.lower()

    # session/handshake noise from drivers and clients
    if low.startswith(('set ', 'use ', 'commit', 'rollback', 'begin', 'start transaction')):
        return None
    if low.startswith('create database') or low.startswith('drop database'):
        return None

    s = re.sub(r'\bAUTO_INCREMENT\b', 'AUTOINCREMENT', s, flags=re.I)
    s = re.sub(r'\s+ENGINE=InnoDB[^;]*', '', s, flags=re.I)
    s = re.sub(r'\bLONGTEXT\b', 'TEXT', s, flags=re.I)
    s = re.sub(r'\bDOUBLE\b', 'REAL', s, flags=re.I)
    s = re.sub(r'VARCHAR\(\d+\)', 'TEXT', s, flags=re.I)

    # MySQL upsert -> SQLite upsert (inverse of db.py's translation)
    if re.search(r'ON DUPLICATE KEY UPDATE', s, re.I):
        s = re.sub(r'ON DUPLICATE KEY UPDATE',
                   'ON CONFLICT(phone) DO UPDATE SET', s, flags=re.I)
        s = re.sub(r'VALUES\((\w+)\)', r'excluded.\1', s, flags=re.I)
    return s


class SqliteBackedSession(Session):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.last_insert_id = 0

    async def query(self, expression, sql, attrs):
        stmt = _translate(sql)
        if stmt is None:
            return [], []

        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            if re.match(r'^\s*SELECT\s+LAST_INSERT_ID\(\)', stmt, re.I):
                return [(self.last_insert_id,)], ['id']
            cur.execute(stmt)
            if re.match(r'^\s*INSERT\b', stmt, re.I):
                self.last_insert_id = cur.lastrowid or 0
            if cur.description:
                cols = [d[0] for d in cur.description]
                rows = [tuple(r[c] for c in cols) for r in cur.fetchall()]
                conn.commit()
                return rows, cols
            conn.commit()
            return [], []
        finally:
            conn.close()


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=3307)
    ap.add_argument('--store', default='/tmp/fb_mysql_store.db')
    args = ap.parse_args()

    if os.path.exists(args.store):
        os.remove(args.store)

    server = MysqlServer(session_factory=lambda: SqliteBackedSession(args.store))
    await server.start_server(port=args.port, host='127.0.0.1')
    print(f'[mysql-test] listening on 127.0.0.1:{args.port} store={args.store}',
          flush=True)
    await server.serve_forever()


if __name__ == '__main__':
    asyncio.run(main())
