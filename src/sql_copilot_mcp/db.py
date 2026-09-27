"""Database access for SQL Copilot. Every function uses the read-only user."""

import os
from datetime import date, datetime
from decimal import Decimal

import psycopg

from sql_copilot_mcp.guard import check_and_prepare

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://copilot_reader:reader_pw@localhost:5432/pagila",
)
MAX_ROWS = 100  # never send more than this many rows back to the AI


def _connect() -> psycopg.Connection:
    conn = psycopg.connect(DATABASE_URL)
    conn.read_only = True  # second safety layer, on top of the read-only user
    return conn


def _to_json_safe(value):
    """Convert database values (Decimal, dates) into JSON-friendly types."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def list_tables() -> list[str]:
    """Return the names of all tables and views in the public schema."""
    sql = """
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p', 'v', 'm')  -- tables, partitioned tables, views
          AND NOT c.relispartition               -- hide monthly partitions like payment_p2022_01
        ORDER BY c.relname
    """
    with _connect() as conn:
        return [row[0] for row in conn.execute(sql).fetchall()]


def describe_table(table_name: str) -> list[dict]:
    """Return each column of a table with its type and whether it can be empty."""
    sql = """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
    """
    with _connect() as conn:
        rows = conn.execute(sql, (table_name,)).fetchall()
    return [
        {"column": name, "type": dtype, "nullable": nullable == "YES"}
        for name, dtype, nullable in rows
    ]


def run_query(sql: str) -> dict:
    """Check the query with the guard, run it, and return at most MAX_ROWS rows."""
    safe_sql = check_and_prepare(sql, max_rows=MAX_ROWS + 1)  # +1 so we can detect "truncated"
    with _connect() as conn:
        cur = conn.execute(safe_sql)
        columns = [col.name for col in cur.description]
        rows = cur.fetchmany(MAX_ROWS + 1)
    truncated = len(rows) > MAX_ROWS
    rows = rows[:MAX_ROWS]
    return {
        "columns": columns,
        "rows": [[_to_json_safe(v) for v in row] for row in rows],
        "row_count": len(rows),
        "truncated": truncated,
    }
