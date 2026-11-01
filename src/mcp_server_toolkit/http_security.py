from __future__ import annotations

import ipaddress
import socket
from collections.abc import Sequence
from urllib.parse import urlparse

import httpx


class HttpSecurityError(ValueError):
    """Raised when an outbound HTTP URL fails SSRF validation."""


def _normalized_allowed_hosts(allowed_hosts: list[str]) -> set[str]:
    return {host.strip().lower().rstrip(".") for host in allowed_hosts if host.strip()}


def _reject_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise HttpSecurityError(f"Blocked IP address: {ip}")


def _resolve_host_ips(hostname: str) -> Sequence[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HttpSecurityError(f"Could not resolve host {hostname!r}") from exc

    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip = ipaddress.ip_address(sockaddr[0])
        ips.append(ip)
    if not ips:
        raise HttpSecurityError(f"No addresses resolved for host {hostname!r}")
    return ips


def validate_outbound_http_url(url: str, *, allowed_hosts: list[str]) -> None:
    """Validate scheme, allowlist, and resolved IPs for an outbound HTTP(S) URL."""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HttpSecurityError("Only http and https URLs are allowed")

    hostname = parsed.hostname
    if not hostname:
        raise HttpSecurityError("URL must include a hostname")

    host_key = hostname.lower().rstrip(".")
    allowlist = _normalized_allowed_hosts(allowed_hosts)
    if not allowlist:
        raise HttpSecurityError(
            "Outbound OpenAPI HTTP is disabled until MCP_TOOLKIT_OPENAPI_ALLOWED_HOSTS is set"
        )
    if host_key not in allowlist:
        raise HttpSecurityError(f"Host {hostname!r} is not in MCP_TOOLKIT_OPENAPI_ALLOWED_HOSTS")

    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        for ip in _resolve_host_ips(hostname):
            _reject_ip(ip)
    else:
        _reject_ip(literal)


def public_response_headers(headers: httpx.Headers) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key.lower() != "set-cookie"}


async def _read_capped_response_body(
    response: httpx.Response, *, max_bytes: int
) -> tuple[bytes, bool]:
    data = bytearray()
    truncated = False
    async for chunk in response.aiter_bytes():
        if len(data) >= max_bytes:
            truncated = True
            break
        take = chunk[: max_bytes - len(data)]
        data.extend(take)
        if len(take) < len(chunk):
            truncated = True
            break
    return bytes(data), truncated


def read_response_body(
    raw: bytes,
    *,
    max_bytes: int,
    content_type: str,
    encoding: str | None,
    truncated: bool = False,
) -> tuple[str | dict, bool]:
    if len(raw) > max_bytes:
        truncated = True
        raw = raw[:max_bytes]

    if "json" in content_type:
        import json

        try:
            return json.loads(raw.decode(encoding or "utf-8")), truncated
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    text = raw.decode(encoding or "utf-8", errors="replace")
    if truncated:
        text += "\n… _(truncated)_"
    return text, truncated


async def safe_http_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    allowed_hosts: list[str],
    max_bytes: int,
    **kwargs: object,
) -> httpx.Response:
    validate_outbound_http_url(url, allowed_hosts=allowed_hosts)
    async with client.stream(method, url, follow_redirects=False, **kwargs) as response:
        if response.status_code in {301, 302, 303, 307, 308}:
            await response.aclose()
            raise HttpSecurityError("Redirects are not allowed for OpenAPI outbound requests")
        body, truncated = await _read_capped_response_body(response, max_bytes=max_bytes)
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=body,
            request=response.request,
            extensions={"mcp_truncated": truncated},
        )
