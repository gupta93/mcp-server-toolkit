from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import structlog
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.context import Context

from mcp_server_toolkit.config import Settings, get_settings
from mcp_server_toolkit.context import AppContext
from mcp_server_toolkit.logging_setup import configure_logging
from mcp_server_toolkit.tools.github import summarize_github_issue, summarize_github_repository
from mcp_server_toolkit.tools.openapi_http import call_openapi_operation
from mcp_server_toolkit.tools.sql_query import resolve_demo_db_path, run_readonly_sql

logger = structlog.get_logger(__name__)


def _app_context(ctx: Context[AppContext]) -> AppContext:
    return ctx.request_context.lifespan_context


def create_server(settings: Settings | None = None) -> MCPServer[AppContext]:
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)

    @asynccontextmanager
    async def lifespan(_server: MCPServer[AppContext]) -> AsyncIterator[AppContext]:
        demo_db_path = resolve_demo_db_path(settings.database_url)
        timeout = httpx.Timeout(settings.http_timeout)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            app_ctx = AppContext(settings=settings, http=client, demo_db_path=demo_db_path)
            logger.info(
                "server_starting",
                transport_ready=True,
                demo_db=str(demo_db_path),
            )
            yield app_ctx

    server = MCPServer[AppContext](
        settings.server_name,
        title="MCP Server Toolkit",
        description="Portfolio demo MCP server with GitHub, SQL, and OpenAPI integrations.",
        version=settings.server_version,
        log_level=settings.log_level,
        lifespan=lifespan,
        instructions=(
            "Use summarize_github_repository for repo overviews, run_readonly_sql for demo "
            "analytics on the bundled SQLite dataset, and call_openapi_operation to invoke "
            "HTTP endpoints from an OpenAPI document."
        ),
    )

    @server.tool(name="summarize_github_repository")
    async def summarize_github_repository_tool(
        owner: str,
        repo: str,
        ctx: Context[AppContext],
    ) -> str:
        """Summarize a public GitHub repository (metadata plus recent open issues)."""
        return await summarize_github_repository(owner, repo, app=_app_context(ctx))

    @server.tool(name="summarize_github_issue")
    async def summarize_github_issue_tool(
        owner: str,
        repo: str,
        issue_number: int,
        ctx: Context[AppContext],
    ) -> str:
        """Summarize a single GitHub issue by number."""
        return await summarize_github_issue(owner, repo, issue_number, app=_app_context(ctx))

    @server.tool(name="run_readonly_sql")
    async def run_readonly_sql_tool(
        query: str,
        ctx: Context[AppContext],
        database_url: str | None = None,
    ) -> str:
        """Run a read-only SQL SELECT against the configured SQLite/Postgres database."""
        return await run_readonly_sql(query, app=_app_context(ctx), database_url=database_url)

    @server.tool(name="call_openapi_operation")
    async def call_openapi_operation_tool(
        operation_id: str,
        ctx: Context[AppContext],
        spec_url: str | None = None,
        spec_text: str | None = None,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> str:
        """Call an HTTP operation from an OpenAPI 3 spec by operationId."""
        return await call_openapi_operation(
            app=_app_context(ctx),
            operation_id=operation_id,
            spec_url=spec_url,
            spec_text=spec_text,
            path_params=path_params,
            query_params=query_params,
            json_body=json_body,
        )

    return server
