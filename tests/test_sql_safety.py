from __future__ import annotations

import pytest

from mcp_server_toolkit.sql_safety import (
    SqlSafetyError,
    validate_readonly_select,
    wrap_query_with_row_limit,
)


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


def test_wrap_query_with_row_limit_uses_subquery() -> None:
    wrapped = wrap_query_with_row_limit("SELECT * FROM products", max_rows=10)
    assert wrapped.startswith("SELECT * FROM (")
    assert wrapped.endswith("LIMIT 10")


def test_wrap_query_defeats_trailing_line_comment() -> None:
    wrapped = wrap_query_with_row_limit("SELECT 999 AS value -- ignore outer limit", max_rows=1)
    assert wrapped.endswith("LIMIT 1")
