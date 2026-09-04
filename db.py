"""
Backward-compatible shim for the original flat db module.

New code should import from `database.db`. This module re-exports the same
public helpers so existing scripts, tests and the MySQL test server keep
working after the refactor.
"""

from database.db import (  # noqa: F401
    SCHEMA,
    Connection,
    Cursor,
    ENGINE,
    engine_info,
    get_conn,
    init_db,
)

SQLITE_PATH = None
