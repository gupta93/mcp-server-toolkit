from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

import structlog
import yaml

from mcp_server_toolkit.context import AppContext

logger = structlog.get_logger(__name__)


def _load_openapi_spec(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("{"):
        return json.loads(raw)
    return yaml.safe_load(raw)


async def _fetch_spec(app: AppContext, spec_url: str) -> dict[str, Any]:
    response = await app.http.get(spec_url, follow_redirects=True)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    text = response.text
    if "json" in content_type or text.lstrip().startswith("{"):
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
    servers = spec.get("servers") or [{"url": "/"}]
    base = str(servers[0].get("url", "/")).rstrip("/")
    resolved_path = path_template
    for key, value in path_params.items():
        resolved_path = resolved_path.replace("{" + key + "}", str(value))
    if "{" in resolved_path:
        raise ValueError(f"Missing path parameters for template {path_template!r}")
    if base.startswith("http"):
        return f"{base}{resolved_path}"
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

    response = await app.http.request(method, url, **request_kwargs)
    content_type = response.headers.get("content-type", "")

    result: dict[str, Any] = {
        "operation_id": operation_id,
        "summary": operation.get("summary"),
        "request": {"method": method, "url": url},
        "response": {
            "status_code": response.status_code,
            "headers": dict(response.headers),
        },
    }

    if "json" in content_type:
        try:
            result["response"]["body"] = response.json()
        except json.JSONDecodeError:
            result["response"]["body"] = response.text
    else:
        text = response.text
        if len(text) > 4000:
            text = text[:4000] + "\n… _(truncated)_"
        result["response"]["body"] = text

    logger.info(
        "openapi_operation_called",
        operation_id=operation_id,
        status_code=response.status_code,
    )
    return json.dumps(result, indent=2)
