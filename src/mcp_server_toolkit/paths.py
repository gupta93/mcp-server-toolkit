from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent
DEMO_DATA_DIR = PROJECT_ROOT / "demo_data"
DEFAULT_SEED_SQL = DEMO_DATA_DIR / "seed.sql"
