from __future__ import annotations

import json
import sqlite3
from typing import Any

import structlog

from mcp_server_toolkit.context import AppContext
from mcp_server_toolkit.database import open_sqlite_readonly
from mcp_server_toolkit.sql_safety import SqlSafetyError, wrap_query_with_row_limit

logger = structlog.get_logger(__name__)


def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    columns = [col[0] for col in cursor.description or []]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


async def _run_postgres_readonly_query(
    conn: Any,
    limited_query: str,
    *,
    timeout_ms: int,
) -> list[Any]:
    await conn.set_read_only(True)
    async with conn.transaction():
        await conn.execute(f"SET LOCAL statement_timeout TO '{timeout_ms}ms'")
        async with conn.cursor() as cursor:
            await cursor.execute(limited_query)
            return await cursor.fetchall()


async def run_readonly_sql(query: str, *, app: AppContext) -> str:
    """Execute a validated read-only SQL query against the configured database."""

    limited_query = wrap_query_with_row_limit(query, max_rows=app.settings.max_sql_rows)
    url = app.settings.database_url

    if url.startswith("sqlite:"):
        with open_sqlite_readonly(app.demo_db_path) as conn:
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

        timeout_ms = app.settings.postgres_statement_timeout_ms
        conn = await psycopg.AsyncConnection.connect(url, row_factory=dict_row)
        async with conn:
            rows = await _run_postgres_readonly_query(
                conn,
                limited_query,
                timeout_ms=timeout_ms,
            )
        payload = {"row_count": len(rows), "rows": rows}
        return json.dumps(payload, indent=2, default=str)

    raise ValueError(
        "Unsupported MCP_TOOLKIT_DATABASE_URL scheme (use sqlite:/// or postgresql://)"
    )


__all__ = ["SqlSafetyError", "run_readonly_sql"]
