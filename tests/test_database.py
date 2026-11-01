from __future__ import annotations

from mcp_server_toolkit.database import read_seed_sql


def test_seed_sql_is_packaged() -> None:
    seed = read_seed_sql()
    assert "CREATE TABLE" in seed
    assert "products" in seed
