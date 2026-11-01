from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path

import structlog

from mcp_server_toolkit.config import Settings

logger = structlog.get_logger(__name__)


def read_seed_sql() -> str:
    seed = resources.files("mcp_server_toolkit.data").joinpath("seed.sql")
    return seed.read_text(encoding="utf-8")


def _data_root(settings: Settings) -> Path:
    root = settings.data_dir.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def bootstrap_sqlite_demo_db(settings: Settings) -> Path:
    """Create the bundled demo SQLite database once at server startup."""

    db_path = _data_root(settings) / "demo.db"
    if db_path.exists():
        return db_path

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(read_seed_sql())
    logger.info("sqlite_demo_initialized", path=str(db_path))
    return db_path


def resolve_sqlite_db_path(settings: Settings) -> Path:
    url = settings.database_url
    if not url.startswith("sqlite:"):
        raise ValueError("Expected MCP_TOOLKIT_DATABASE_URL to use sqlite:")

    data_root = _data_root(settings)
    if url in {"sqlite:///demo.db", "sqlite:///demo_data/demo.db"}:
        return bootstrap_sqlite_demo_db(settings)

    suffix = url.removeprefix("sqlite:")
    if suffix.startswith("////"):
        db_path = Path(suffix[3:]).resolve()
    elif suffix.startswith("///"):
        db_path = (data_root / suffix[3:]).resolve()
    else:
        raise ValueError(
            "Unsupported sqlite URL; use sqlite:///demo.db or a path under MCP_TOOLKIT_DATA_DIR"
        )

    try:
        db_path.relative_to(data_root)
    except ValueError as exc:
        raise ValueError("SQLite database path must be located under MCP_TOOLKIT_DATA_DIR") from exc

    if not db_path.exists():
        raise ValueError(
            "SQLite database file does not exist. The demo database is seeded once at startup "
            "for sqlite:///demo.db."
        )
    return db_path


def open_sqlite_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn
