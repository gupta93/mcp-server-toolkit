from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from mcp_server_toolkit.http_security import safe_http_request


@pytest.mark.asyncio
async def test_safe_http_request_stops_reading_at_size_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mcp_server_toolkit.http_security.validate_outbound_http_url",
        lambda *args, **kwargs: None,
    )

    async def app(scope, receive, send):
        async def body():
            while True:
                chunk = await receive()
                if chunk["type"] == "http.request":
                    break

        await body()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        for _ in range(50):
            await send({"type": "http.response.body", "body": b"x" * 1024, "more_body": True})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://httpbin.org") as client:
        response = await safe_http_request(
            client,
            "GET",
            "http://httpbin.org/stream",
            allowed_hosts=["httpbin.org"],
            max_bytes=4096,
        )

    assert len(response.content) == 4096
    assert response.extensions.get("mcp_truncated") is True
