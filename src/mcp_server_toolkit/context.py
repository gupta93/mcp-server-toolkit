from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from mcp_server_toolkit.config import Settings


@dataclass(slots=True)
class AppContext:
    settings: Settings
    http: httpx.AsyncClient
    demo_db_path: Path
