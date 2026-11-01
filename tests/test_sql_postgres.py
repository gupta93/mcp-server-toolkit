from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_server_toolkit.tools.sql_query import _run_postgres_readonly_query


@pytest.mark.asyncio
async def test_postgres_readonly_uses_set_read_only_and_transaction() -> None:
    cursor = MagicMock()
    cursor.execute = AsyncMock()
    cursor.fetchall = AsyncMock(return_value=[{"value": 1}])
    cursor.__aenter__ = AsyncMock(return_value=cursor)
    cursor.__aexit__ = AsyncMock(return_value=None)

    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=transaction)
    transaction.__aexit__ = AsyncMock(return_value=None)

    conn = MagicMock()
    conn.set_read_only = AsyncMock()
    conn.execute = AsyncMock()
    conn.transaction = MagicMock(return_value=transaction)
    conn.cursor = MagicMock(return_value=cursor)

    rows = await _run_postgres_readonly_query(
        conn,
        "SELECT 1",
        timeout_ms=2500,
    )

    conn.set_read_only.assert_awaited_once_with(True)
    conn.execute.assert_awaited_once_with("SET LOCAL statement_timeout TO '2500ms'")
    cursor.execute.assert_awaited_once_with("SELECT 1")
    assert rows == [{"value": 1}]
