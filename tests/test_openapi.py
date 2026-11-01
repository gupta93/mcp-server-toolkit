from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from mcp_server_toolkit.config import Settings
from mcp_server_toolkit.context import AppContext
from mcp_server_toolkit.tools.openapi_http import call_openapi_operation

FIXTURE = Path(__file__).parent / "fixtures" / "demo_openapi.json"


@pytest.fixture
def app() -> AppContext:
    settings = Settings()
    return AppContext(
        settings=settings,
        http=httpx.AsyncClient(),
        demo_db_path=Path("/tmp/unused.db"),
    )


@pytest.mark.asyncio
async def test_call_openapi_operation_with_spec_text(app: AppContext) -> None:
    spec_text = FIXTURE.read_text(encoding="utf-8")

    with respx.mock:
        route = respx.get("https://httpbin.org/get").respond(200, json={"args": {"greeting": "hi"}})
        payload = json.loads(
            await call_openapi_operation(
                app=app,
                operation_id="httpbinGet",
                spec_text=spec_text,
                query_params={"greeting": "hi"},
            )
        )
        assert route.called
        assert payload["response"]["status_code"] == 200
        assert payload["response"]["body"]["args"]["greeting"] == "hi"
