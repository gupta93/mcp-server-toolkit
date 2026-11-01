from __future__ import annotations

from pathlib import Path

import httpx
import pytest_asyncio

from mcp_server_toolkit.config import Settings
from mcp_server_toolkit.context import AppContext


@pytest_asyncio.fixture
async def app_context(tmp_path: Path) -> AppContext:
    settings = Settings(
        data_dir=tmp_path / "data",
        openapi_allowed_hosts=["httpbin.org"],
    )
    async with httpx.AsyncClient() as client:
        yield AppContext(
            settings=settings,
            http=client,
            demo_db_path=tmp_path / "unused.db",
        )
