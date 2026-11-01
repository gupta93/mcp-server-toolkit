from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import structlog

from mcp_server_toolkit.context import AppContext
from mcp_server_toolkit.paths import DEFAULT_SEED_SQL, DEMO_DATA_DIR, PROJECT_ROOT
from mcp_server_toolkit.sql_safety import SqlSafetyError, ensure_row_limit, validate_readonly_select

logger = structlog.get_logger(__name__)


def _sqlite_path_from_url(database_url: str) -> Path:
    if not database_url.startswith("sqlite:"):
        raise ValueError("Expected a sqlite: URL")

    # sqlite:///relative.db  -> project-relative
    # sqlite:////absolute/path.db -> absolute (four slashes on Unix)
    suffix = database_url.removeprefix("sqlite:")
    suffix = unquote(suffix)
    if suffix.startswith("////"):
        return Path(suffix[3:])
    if suffix.startswith("///"):
        relative = suffix[3:]
        return (PROJECT_ROOT / relative).resolve()
    if suffix.startswith("//"):
        return Path(suffix[2:])
    return (PROJECT_ROOT / suffix.lstrip("/")).resolve()


def bootstrap_sqlite_db(db_path: Path, *, seed_sql: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        return
    seed = seed_sql.read_text(encoding="utf-8")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(seed)
    logger.info("sqlite_demo_initialized", path=str(db_path))


def resolve_demo_db_path(settings_database_url: str) -> Path:
    if settings_database_url.startswith("sqlite:"):
        db_path = _sqlite_path_from_url(settings_database_url)
        if not db_path.is_absolute():
            db_path = (PROJECT_ROOT / db_path).resolve()
        bootstrap_sqlite_db(db_path, seed_sql=DEFAULT_SEED_SQL)
        return db_path
    return DEMO_DATA_DIR / "demo.db"


def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    columns = [col[0] for col in cursor.description or []]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


async def run_readonly_sql(
    query: str,
    *,
    app: AppContext,
    database_url: str | None = None,
) -> str:
    """Execute a validated read-only SQL query against SQLite or Postgres."""

    url = database_url or app.settings.database_url
    safe_query = validate_readonly_select(query)
    limited_query = ensure_row_limit(safe_query, max_rows=app.settings.max_sql_rows)

    if url.startswith("sqlite:"):
        db_path = _sqlite_path_from_url(url)
        if not db_path.is_absolute():
            db_path = (PROJECT_ROOT / db_path).resolve()
        bootstrap_sqlite_db(db_path, seed_sql=DEFAULT_SEED_SQL)
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(limited_query)
            rows = _rows_to_dicts(cursor)
        payload = {"row_count": len(rows), "rows": rows}
        return json.dumps(payload, indent=2)

    if url.startswith("postgres://") or url.startswith("postgresql://"):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError(
                "Postgres support requires optional deps: pip install mcp-server-toolkit[postgres]"
            ) from exc

        conn = await psycopg.AsyncConnection.connect(url, row_factory=dict_row)
        async with conn, conn.cursor() as cursor:
            await cursor.execute(limited_query)
            rows = await cursor.fetchall()
        payload = {"row_count": len(rows), "rows": rows}
        return json.dumps(payload, indent=2, default=str)

    raise ValueError("Unsupported database URL scheme (use sqlite:/// or postgresql://)")


__all__ = ["SqlSafetyError", "run_readonly_sql", "resolve_demo_db_path", "bootstrap_sqlite_db"]
