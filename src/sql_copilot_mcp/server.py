"""MCP server: exposes the database to any AI assistant as three tools."""

from typing import Any

import psycopg
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from sql_copilot_mcp import db
from sql_copilot_mcp.guard import UnsafeQueryError

mcp = MCPServer("sql-copilot")


@mcp.tool()
def list_tables() -> list[str]:
    """List all tables and views in the database. Call this first to see what data exists."""
    try:
        return db.list_tables()
    except psycopg.Error as e:
        raise ToolError(f"Database error: {e}") from e


@mcp.tool()
def describe_table(table_name: str) -> list[dict]:
    """Show the columns of one table (name, type, nullable). Use before writing SQL."""
    try:
        return db.describe_table(table_name)
    except psycopg.Error as e:
        raise ToolError(f"Database error: {e}") from e


@mcp.tool()
def run_query(sql: str) -> dict[str, Any]:
    """Run ONE read-only PostgreSQL SELECT query. Returns up to 100 rows.

    Writes, multiple statements and risky functions are rejected with a reason.
    If a query fails, read the error message, fix the SQL, and try again.
    """
    try:
        return db.run_query(sql)
    except UnsafeQueryError as e:
        raise ToolError(f"Query blocked: {e}") from e
    except psycopg.Error as e:
        # SQL mistakes (wrong column name, syntax) - tell the AI so it can retry
        raise ToolError(f"Database error: {e}") from e


if __name__ == "__main__":
    mcp.run()  # talks to the AI over stdin/stdout
