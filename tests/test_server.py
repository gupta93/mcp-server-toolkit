from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcp_server_toolkit.config import Settings
from mcp_server_toolkit.context import AppContext
from mcp_server_toolkit.paths import DEFAULT_SEED_SQL
from mcp_server_toolkit.server import create_server
from mcp_server_toolkit.tools.sql_query import bootstrap_sqlite_db, run_readonly_sql


@pytest.mark.asyncio
async def test_run_readonly_sql_against_demo_db(tmp_path: Path) -> None:
    db_path = tmp_path / "demo.db"
    bootstrap_sqlite_db(db_path, seed_sql=DEFAULT_SEED_SQL)
    settings = Settings(database_url=f"sqlite:////{db_path}")
    async with httpx.AsyncClient() as client:
        app = AppContext(settings=settings, http=client, demo_db_path=db_path)
        raw = await run_readonly_sql(
            "SELECT name, category FROM products WHERE in_stock = 1 ORDER BY name",
            app=app,
        )
    data = json.loads(raw)
    assert data["row_count"] >= 2
    assert any(row["name"] == "Notebook" for row in data["rows"])


@pytest.mark.asyncio
async def test_server_lists_four_tools() -> None:
    settings = Settings(log_json=True)
    create_server(settings)

    params = StdioServerParameters(
        command="python3",
        args=["-m", "mcp_server_toolkit", "--transport", "stdio"],
        cwd=str(Path(__file__).resolve().parents[1]),
    )

    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        listed = await session.list_tools()
        names = {tool.name for tool in listed.tools}
        assert names == {
            "summarize_github_repository",
            "summarize_github_issue",
            "run_readonly_sql",
            "call_openapi_operation",
        }
