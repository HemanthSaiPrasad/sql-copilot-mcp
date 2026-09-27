"""Test the MCP server the way an AI client would: list tools, then call one."""

import asyncio

from mcp import Client

from sql_copilot_mcp.server import mcp


def test_server_exposes_three_tools():
    async def check():
        async with Client(mcp) as client:
            result = await client.list_tools()
            return sorted(tool.name for tool in result.tools)

    assert asyncio.run(check()) == ["describe_table", "list_tables", "run_query"]


def test_server_runs_a_query():
    async def check():
        async with Client(mcp) as client:
            return await client.call_tool("run_query", {"sql": "SELECT 1 AS one"})

    result = asyncio.run(check())
    assert result.is_error is False
    assert "one" in str(result.content)


def test_server_reports_blocked_query_as_error():
    async def check():
        async with Client(mcp) as client:
            return await client.call_tool("run_query", {"sql": "DROP TABLE customer"})

    result = asyncio.run(check())
    assert result.is_error is True
    assert "Query blocked: Only SELECT" in str(result.content)


def test_server_reports_sql_mistakes_so_ai_can_fix_them():
    async def check():
        async with Client(mcp) as client:
            return await client.call_tool("run_query", {"sql": "SELECT no_such_column FROM customer"})

    result = asyncio.run(check())
    assert result.is_error is True
    assert "no_such_column" in str(result.content)
