from __future__ import annotations

import pytest

from mcp_server_toolkit.http_security import HttpSecurityError, validate_outbound_http_url


def test_empty_allowlist_blocks_requests() -> None:
    with pytest.raises(HttpSecurityError, match="OPENAPI_ALLOWED_HOSTS"):
        validate_outbound_http_url("https://example.com/path", allowed_hosts=[])


def test_host_must_be_allowlisted() -> None:
    with pytest.raises(HttpSecurityError, match="not in"):
        validate_outbound_http_url("https://evil.example/path", allowed_hosts=["httpbin.org"])


def test_blocks_non_http_schemes() -> None:
    with pytest.raises(HttpSecurityError, match="http and https"):
        validate_outbound_http_url("file:///etc/passwd", allowed_hosts=["example.com"])


def test_blocks_loopback_literal_ip() -> None:
    with pytest.raises(HttpSecurityError, match="Blocked IP"):
        validate_outbound_http_url("http://127.0.0.1/", allowed_hosts=["127.0.0.1"])


def test_allows_public_host_in_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mcp_server_toolkit.http_security._resolve_host_ips",
        lambda _host: [__import__("ipaddress").ip_address("93.184.216.34")],
    )
    validate_outbound_http_url("https://example.com/test", allowed_hosts=["example.com"])
