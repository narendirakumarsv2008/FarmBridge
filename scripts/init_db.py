#!/usr/bin/env python
"""Standalone FarmBridge schema initializer / migrator.

This is idempotent and safe to run repeatedly:

    ENVIRONMENT=production DB_ENGINE=mysql \
    MYSQL_HOST=... MYSQL_USER=... MYSQL_PASSWORD=... MYSQL_DB=farmbridge \
    python scripts/init_db.py

It never drops tables or deletes data. It creates missing tables, applies
lightweight column migrations, and creates the useful indexes.
"""

import os
import sys
from pathlib import Path

# Make the project root importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_db_status, init_db  # noqa: E402


def main():
    print('Initializing FarmBridge database...')
    engine = init_db()
    status = get_db_status()
    print('Database engine: %s' % engine)
    print('Connected: %s' % ('yes' if status.get('connected') else 'no'))
    if not status.get('connected'):
        print('Database connection failed.', file=sys.stderr)
        return 1
    print('OK: schema is ready (tables created/migrated, indexes applied).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
