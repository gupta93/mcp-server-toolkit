from __future__ import annotations

import pytest

from mcp_server_toolkit.sql_safety import SqlSafetyError, ensure_row_limit, validate_readonly_select


def test_validate_accepts_select() -> None:
    assert validate_readonly_select("SELECT 1") == "SELECT 1"


def test_validate_accepts_with_cte() -> None:
    sql = "WITH cte AS (SELECT 1 AS n) SELECT n FROM cte"
    assert validate_readonly_select(sql) == sql


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "DELETE FROM products",
        "SELECT 1; DROP TABLE products",
        "INSERT INTO products VALUES (1, 'x', 'y', 1, 1)",
        "PRAGMA table_info(products)",
    ],
)
def test_validate_rejects_unsafe_sql(sql: str) -> None:
    with pytest.raises(SqlSafetyError):
        validate_readonly_select(sql)


def test_ensure_row_limit_appends_limit() -> None:
    assert ensure_row_limit("SELECT * FROM products", max_rows=10).endswith("LIMIT 10")


def test_ensure_row_limit_preserves_existing() -> None:
    sql = "SELECT * FROM products LIMIT 5"
    assert ensure_row_limit(sql, max_rows=10) == sql
