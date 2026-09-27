"""Talk to the MCP server exactly like an AI app would: start it, list tools, call them."""

import asyncio
import sys

from mcp import Client, StdioServerParameters

SERVER = StdioServerParameters(command=sys.executable, args=["-m", "sql_copilot_mcp.server"])


async def main():
    async with Client(SERVER) as client:
        tools = await client.list_tools()
        print("Tools:", [t.name for t in tools.tools])

        tables = await client.call_tool("list_tables", {})
        print("\nTables:", tables.structured_content)

        top = await client.call_tool(
            "run_query",
            {
                "sql": """
                    SELECT c.first_name, c.last_name, SUM(p.amount) AS total_spent
                    FROM customer c JOIN payment p ON p.customer_id = c.customer_id
                    GROUP BY c.customer_id ORDER BY total_spent DESC LIMIT 5
                """
            },
        )
        print("\nTop 5 customers:", top.structured_content)


asyncio.run(main())
