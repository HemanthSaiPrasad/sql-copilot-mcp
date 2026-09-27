"""MCP server: exposes the database to any AI assistant as three tools."""

from typing import Any

from mcp.server.mcpserver import MCPServer

from sql_copilot_mcp import db

mcp = MCPServer("sql-copilot")


@mcp.tool()
def list_tables() -> list[str]:
    """List all tables and views in the database. Call this first to see what data exists."""
    return db.list_tables()


@mcp.tool()
def describe_table(table_name: str) -> list[dict]:
    """Show the columns of one table (name, type, nullable). Use before writing SQL."""
    return db.describe_table(table_name)


@mcp.tool()
def run_query(sql: str) -> dict[str, Any]:
    """Run a read-only PostgreSQL SELECT query. Returns up to 100 rows."""
    return db.run_query(sql)


if __name__ == "__main__":
    mcp.run()  # talks to the AI over stdin/stdout
