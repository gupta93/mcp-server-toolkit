from __future__ import annotations

import argparse
import sys

import structlog

from mcp_server_toolkit.config import get_settings
from mcp_server_toolkit.server import create_server

logger = structlog.get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MCP Server Toolkit demo server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument("--host", help="HTTP host override (streamable-http only)")
    parser.add_argument("--port", type=int, help="HTTP port override (streamable-http only)")
    parser.add_argument("--path", help="HTTP MCP path override (streamable-http only)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    server = create_server(settings)

    if args.transport == "stdio":
        logger.info("transport_selected", transport="stdio")
        server.run("stdio")
        return 0

    host = args.host or settings.http_host
    port = args.port or settings.http_port
    path = args.path or settings.http_path
    logger.info("transport_selected", transport="streamable-http", host=host, port=port, path=path)
    server.run(
        "streamable-http",
        host=host,
        port=port,
        streamable_http_path=path,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
