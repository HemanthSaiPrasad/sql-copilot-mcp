"""Agent tests with a FAKE model: no API key, no cost, same answer every time.

The fake model replays scripted replies, but the tool calls are REAL: they go
through the MCP server, the guard, and the database.
"""

import asyncio

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from sql_copilot_mcp.agent import ask
from sql_copilot_mcp.server import mcp


class FakeModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self  # the fake model ignores tool definitions


def tool_call(sql: str, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": "run_query", "args": {"sql": sql}, "id": call_id}])


def run(question: str, replies: list) -> dict:
    return asyncio.run(ask(question, model=FakeModel(responses=replies), server=mcp))


def tool_outputs(result: dict) -> list[str]:
    return [m.content for m in result["messages"] if m.type == "tool"]


def test_agent_runs_a_query_and_answers():
    result = run(
        "How many customers do we have?",
        [tool_call("SELECT count(*) AS n FROM customer", "c1"), AIMessage("We have many customers.")],
    )
    assert '"n"' in tool_outputs(result)[0]  # the real query ran
    assert result["answer"] == "We have many customers."


def test_agent_sees_errors_and_can_retry():
    result = run(
        "List customer names",
        [
            tool_call("SELECT full_name FROM customer", "c1"),  # wrong column
            tool_call("SELECT first_name FROM customer LIMIT 3", "c2"),  # fixed
            AIMessage("Here are three customers."),
        ],
    )
    first, second = tool_outputs(result)
    assert first.startswith("ERROR") and "full_name" in first  # the AI can read what went wrong
    assert "first_name" in second


def test_agent_cannot_bypass_the_guard():
    result = run(
        "Delete everything",
        [tool_call("DELETE FROM customer", "c1"), AIMessage("I can't do that.")],
    )
    assert "Query blocked" in tool_outputs(result)[0]
