"""Query guard: inspects every SQL query BEFORE it reaches the database.

The database already blocks writes (read-only user + read-only connection).
This is an extra layer that rejects risky queries early, with a clear reason
the AI can read and fix.
"""

import sqlglot
from sqlglot import exp


class UnsafeQueryError(ValueError):
    """Raised when a query is not allowed to run."""


# Anything that changes data or structure, even if hidden inside a WITH clause
WRITE_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge,
    exp.Create, exp.Drop, exp.Alter, exp.TruncateTable, exp.Command,
)

# Functions that can sleep, read server files, or kill other sessions
BLOCKED_FUNCTIONS = {
    "pg_sleep", "pg_read_file", "pg_read_binary_file", "pg_ls_dir",
    "pg_terminate_backend", "pg_cancel_backend", "set_config",
    "lo_import", "lo_export", "dblink",
}


def _function_name(func: exp.Func) -> str:
    name = func.name if isinstance(func, exp.Anonymous) else func.sql_name()
    return name.lower()


def check_and_prepare(sql: str, max_rows: int) -> str:
    """Validate a query and return a safe version with a row LIMIT added."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except sqlglot.errors.ParseError as e:
        raise UnsafeQueryError(f"Could not parse SQL: {e}") from e

    if len(statements) != 1:
        raise UnsafeQueryError("Send exactly one SQL statement at a time.")

    query = statements[0]
    if not isinstance(query, exp.Query):
        raise UnsafeQueryError("Only SELECT queries are allowed.")

    for node in query.walk():
        if isinstance(node, WRITE_NODES):
            raise UnsafeQueryError(f"Write operation not allowed: {node.key.upper()}")
        if isinstance(node, exp.Into):
            raise UnsafeQueryError("SELECT ... INTO is not allowed (it creates a table).")
        if isinstance(node, exp.Lock):
            raise UnsafeQueryError("Row locks (FOR UPDATE / FOR SHARE) are not allowed.")
        if isinstance(node, exp.Func) and _function_name(node) in BLOCKED_FUNCTIONS:
            raise UnsafeQueryError(f"Function not allowed: {_function_name(node)}")

    # Always cap rows, so a huge result never reaches the AI
    limit = query.args.get("limit")
    current = limit.expression if limit else None
    if current is None or not (isinstance(current, exp.Literal) and int(current.name) <= max_rows):
        query = query.limit(max_rows)

    return query.sql(dialect="postgres")
