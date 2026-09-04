"""
Compatibility shim.

Earlier versions of Farm Bridge kept the database layer in a root-level
`db.py`. The layer now lives in `database/db.py`; this module re-exports the
same names so any older scripts/imports keep working.

    from db import get_conn, init_db, engine_info
"""

from database.db import (  # noqa: F401
    Connection,
    Cursor,
    ENGINE,
    engine_info,
    get_conn,
    init_db,
)
