from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from mcp_server_toolkit.context import AppContext
from mcp_server_toolkit.http_security import HttpSecurityError, public_response_headers
from mcp_server_toolkit.tools.openapi_http import call_openapi_operation

FIXTURE = Path(__file__).parent / "fixtures" / "demo_openapi.json"
SPEC_TEXT = FIXTURE.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_call_openapi_operation_with_spec_text(app_context: AppContext) -> None:
    with respx.mock:
        route = respx.get("https://httpbin.org/get").respond(
            200,
            json={"args": {"greeting": "hi"}},
            headers={"Set-Cookie": "session=secret"},
        )
        payload = json.loads(
            await call_openapi_operation(
                app=app_context,
                operation_id="httpbinGet",
                spec_text=SPEC_TEXT,
                query_params={"greeting": "hi"},
            )
        )
        assert route.called
        assert payload["response"]["status_code"] == 200
        assert payload["response"]["body"]["args"]["greeting"] == "hi"
        assert "set-cookie" not in {k.lower() for k in payload["response"]["headers"]}


@pytest.mark.asyncio
async def test_openapi_blocks_disallowed_target(app_context: AppContext) -> None:
    spec = SPEC_TEXT.replace("https://httpbin.org", "https://example.com")
    with pytest.raises(HttpSecurityError, match="not in"):
        await call_openapi_operation(
            app=app_context,
            operation_id="httpbinGet",
            spec_text=spec,
        )


@pytest.mark.asyncio
async def test_openapi_response_size_cap(app_context: AppContext) -> None:
    app_context.settings.openapi_max_response_bytes = 32
    with respx.mock:
        respx.get("https://httpbin.org/get").respond(200, text="x" * 100)
        payload = json.loads(
            await call_openapi_operation(
                app=app_context,
                operation_id="httpbinGet",
                spec_text=SPEC_TEXT,
            )
        )
    assert payload["response"]["truncated"] is True


def test_public_response_headers_strips_set_cookie() -> None:
    headers = httpx.Headers({"Content-Type": "application/json", "Set-Cookie": "a=b"})
    sanitized = public_response_headers(headers)
    assert not any(key.lower() == "set-cookie" for key in sanitized)
    assert sanitized.get("content-type") == "application/json"
