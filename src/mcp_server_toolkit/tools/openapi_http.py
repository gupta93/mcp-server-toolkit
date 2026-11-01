from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlencode

import structlog
import yaml

from mcp_server_toolkit.context import AppContext
from mcp_server_toolkit.http_security import (
    HttpSecurityError,
    public_response_headers,
    read_response_body,
    safe_http_request,
    validate_outbound_http_url,
)

logger = structlog.get_logger(__name__)


def _load_openapi_spec(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("{"):
        return json.loads(raw)
    return yaml.safe_load(raw)


async def _fetch_spec(app: AppContext, spec_url: str) -> dict[str, Any]:
    validate_outbound_http_url(spec_url, allowed_hosts=app.settings.openapi_allowed_hosts)
    response = await safe_http_request(
        app.http,
        "GET",
        spec_url,
        allowed_hosts=app.settings.openapi_allowed_hosts,
        max_bytes=app.settings.openapi_max_response_bytes,
    )
    response.raise_for_status()
    max_bytes = app.settings.openapi_max_response_bytes
    body, _truncated = read_response_body(
        response.content,
        max_bytes=max_bytes,
        content_type=response.headers.get("content-type", ""),
        encoding=response.encoding,
        truncated=bool(response.extensions.get("mcp_truncated")),
    )
    if isinstance(body, dict):
        return body
    text = str(body)
    if "json" in response.headers.get("content-type", "") or text.lstrip().startswith("{"):
        return json.loads(text)
    return yaml.safe_load(text)


def _find_operation(spec: dict[str, Any], operation_id: str) -> tuple[str, str, dict[str, Any]]:
    paths = spec.get("paths") or {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete", "head", "options"):
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            if operation.get("operationId") == operation_id:
                return method.upper(), path, operation
    raise ValueError(f"operationId {operation_id!r} not found in OpenAPI spec")


def _build_url(spec: dict[str, Any], path_template: str, path_params: dict[str, Any]) -> str:
    servers = spec.get("servers") or []
    if not servers:
        raise ValueError(
            "OpenAPI spec must define at least one server with an absolute http(s) URL"
        )

    base = str(servers[0].get("url", "")).rstrip("/")
    resolved_path = path_template
    for key, value in path_params.items():
        resolved_path = resolved_path.replace("{" + key + "}", str(value))
    if "{" in resolved_path:
        raise ValueError(f"Missing path parameters for template {path_template!r}")

    if not re.match(r"^https?://", base):
        raise ValueError(
            "OpenAPI server URL must be absolute (http:// or https://). "
            f"Got {base!r}; relative server URLs are not supported."
        )
    return f"{base}{resolved_path}"


async def call_openapi_operation(
    *,
    app: AppContext,
    operation_id: str,
    spec_url: str | None = None,
    spec_text: str | None = None,
    path_params: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> str:
    """Call an HTTP operation described by an OpenAPI 3 document."""

    if not spec_url and not spec_text:
        raise ValueError("Provide either spec_url or spec_text")
    if spec_url and spec_text:
        raise ValueError("Provide only one of spec_url or spec_text")

    spec = await _fetch_spec(app, spec_url) if spec_url else _load_openapi_spec(spec_text or "")
    method, path_template, operation = _find_operation(spec, operation_id)

    url = _build_url(spec, path_template, path_params or {})
    if query_params:
        url = f"{url}?{urlencode(query_params, doseq=True)}"

    request_kwargs: dict[str, Any] = {}
    if json_body is not None:
        request_kwargs["json"] = json_body

    try:
        response = await safe_http_request(
            app.http,
            method,
            url,
            allowed_hosts=app.settings.openapi_allowed_hosts,
            max_bytes=app.settings.openapi_max_response_bytes,
            **request_kwargs,
        )
    except HttpSecurityError:
        raise

    max_bytes = app.settings.openapi_max_response_bytes
    body, truncated = read_response_body(
        response.content,
        max_bytes=max_bytes,
        content_type=response.headers.get("content-type", ""),
        encoding=response.encoding,
        truncated=bool(response.extensions.get("mcp_truncated")),
    )

    result: dict[str, Any] = {
        "operation_id": operation_id,
        "summary": operation.get("summary"),
        "request": {"method": method, "url": url},
        "response": {
            "status_code": response.status_code,
            "headers": public_response_headers(response.headers),
            "body": body,
            "truncated": truncated,
        },
    }

    logger.info(
        "openapi_operation_called",
        operation_id=operation_id,
        status_code=response.status_code,
    )
    return json.dumps(result, indent=2, default=str)
