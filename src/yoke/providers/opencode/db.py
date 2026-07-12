"""Read-only access to OpenCode's own SQLite database.

OpenCode's SSE stream was found unreliable for live progress narration in the
prior spike this adapter is ported from (CodeAlmanac, 2026-07-09); polling
OpenCode's own part/message tables is the proven alternative. Yoke doesn't
own this schema, so every query tolerates a missing file, missing table, or
corrupt database by returning an empty result instead of raising.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SQLiteRow = sqlite3.Row


def query_readonly_or_empty(
    path: Path,
    sql: str,
    params: tuple = (),
) -> tuple[SQLiteRow, ...]:
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
    except sqlite3.Error:
        return ()
    try:
        return tuple(connection.execute(sql, params).fetchall())
    except sqlite3.Error:
        return ()
    finally:
        connection.close()
