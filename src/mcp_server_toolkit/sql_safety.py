from __future__ import annotations

import re

_FORBIDDEN_KEYWORDS = re.compile(
    r"\b("
    r"INSERT|UPDATE|DELETE|MERGE|REPLACE|DROP|ALTER|CREATE|TRUNCATE|"
    r"GRANT|REVOKE|EXEC|EXECUTE|ATTACH|DETACH|PRAGMA|VACUUM|REINDEX"
    r")\b",
    re.IGNORECASE,
)


class SqlSafetyError(ValueError):
    """Raised when a SQL statement fails read-only validation."""


def validate_readonly_select(sql: str) -> str:
    """Validate and normalize a single read-only SELECT statement."""

    query = sql.strip()
    if not query:
        raise SqlSafetyError("Query must not be empty")

    if ";" in query.rstrip().rstrip(";"):
        raise SqlSafetyError("Only a single SQL statement is allowed")

    query = query.rstrip(";").strip()

    if _FORBIDDEN_KEYWORDS.search(query):
        raise SqlSafetyError("Only read-only SELECT queries are permitted")

    leading = query.lstrip().upper()
    if not (leading.startswith("SELECT") or leading.startswith("WITH")):
        raise SqlSafetyError("Query must begin with SELECT or WITH")

    return query


def wrap_query_with_row_limit(sql: str, *, max_rows: int) -> str:
    """Wrap the validated query so row limits cannot be bypassed via comments or subqueries."""

    inner = validate_readonly_select(sql)
    return f"SELECT * FROM ({inner}) AS _mcp_toolkit_limited LIMIT {max_rows}"
