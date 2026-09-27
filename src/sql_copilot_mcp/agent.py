"""SQL Copilot agent: Claude + LangGraph, using the MCP server's tools.

Flow:  question -> [agent] --tool call--> [tools] --result--> [agent] ... -> answer
The agent loops until it stops calling tools, so it can explore tables,
run a query, read an error, fix its SQL, and try again.
"""

import asyncio
import json
import os
import sys

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from mcp import Client, StdioServerParameters

MODEL = os.getenv("COPILOT_MODEL", "claude-haiku-4-5-20251001")
MAX_STEPS = 20  # safety stop: the agent may take at most this many graph steps

SYSTEM_PROMPT = """You are SQL Copilot, a data analyst for a DVD rental business.
The data lives in a PostgreSQL database. To answer a question:
1. Call list_tables to see what exists.
2. Call describe_table for each table you plan to use.
3. Write ONE SELECT query and call run_query.
4. If run_query returns an error, read it, fix the SQL, and try again.
5. Answer in plain English and show the final SQL you used.
Every number in your answer must come from a query result. Never guess."""

# By default the agent starts your MCP server as a separate process, like Claude Desktop does
DEFAULT_SERVER = StdioServerParameters(command=sys.executable, args=["-m", "sql_copilot_mcp.server"])


def mcp_to_langchain_tools(client: Client, mcp_tools) -> list[StructuredTool]:
    """Wrap each MCP tool so LangChain/LangGraph can call it."""

    def make_tool(tool):
        async def call(**kwargs) -> str:
            result = await client.call_tool(tool.name, kwargs)
            if result.structured_content is not None:
                text = json.dumps(result.structured_content)
            else:
                text = "\n".join(c.text for c in result.content if hasattr(c, "text"))
            return f"ERROR: {text}" if result.is_error else text

        return StructuredTool.from_function(
            coroutine=call,
            name=tool.name,
            description=tool.description or tool.name,
            args_schema=tool.input_schema,
        )

    return [make_tool(t) for t in mcp_tools]


def build_graph(model, tools):
    """The agent loop: call the model; if it asks for tools, run them and go back."""
    model_with_tools = model.bind_tools(tools)

    async def agent(state: MessagesState):
        messages = [SystemMessage(SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [await model_with_tools.ainvoke(messages)]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)  # tool calls -> "tools", else -> end
    graph.add_edge("tools", "agent")
    return graph.compile()


def default_model():
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=MODEL, temperature=0)


async def ask(question: str, model=None, server=DEFAULT_SERVER) -> dict:
    """Answer one question. Returns the final answer plus every step taken."""
    async with Client(server) as client:
        tools = mcp_to_langchain_tools(client, (await client.list_tools()).tools)
        graph = build_graph(model or default_model(), tools)
        state = await graph.ainvoke(
            {"messages": [HumanMessage(question)]},
            config={"recursion_limit": MAX_STEPS},
        )
    messages = state["messages"]
    return {"answer": messages[-1].text, "messages": messages}


def print_trace(result: dict) -> None:
    """Show what the agent did, step by step."""
    for msg in result["messages"][1:-1]:
        for call in getattr(msg, "tool_calls", []) or []:
            print(f"-> {call['name']}({json.dumps(call['args'])})")
        if msg.type == "tool":
            print(f"   {msg.content[:150]}")
    print("\n" + result["answer"])


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "Who are our top 5 customers by total spending?"
    print_trace(asyncio.run(ask(question)))
