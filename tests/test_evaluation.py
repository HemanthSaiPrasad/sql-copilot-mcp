"""Tests for the evaluation scorer, plus a check that every gold query is valid."""

import json
from pathlib import Path

import pytest

from sql_copilot_mcp import db
from sql_copilot_mcp.evaluation import rows_match

QUESTIONS = json.loads((Path(__file__).parent.parent / "evals" / "questions.json").read_text())
ANSWERABLE = [q for q in QUESTIONS if q.get("expect") != "refuse"]


def test_exact_match():
    assert rows_match([[999]], [[999]])


def test_numbers_are_rounded_and_text_is_case_insensitive():
    assert rows_match([[2.98]], [[2.9800001]])
    assert rows_match([["Action"]], [["ACTION"]])


def test_extra_columns_are_allowed():
    # Gold asks for the country; the agent also returned the count - still correct
    assert rows_match([["Mexico"]], [["Mexico", 430]])


def test_wrong_value_fails():
    assert not rows_match([[999]], [[1000]])


def test_unordered_rows_match_in_any_order():
    assert rows_match([["G", 178], ["R", 195]], [["R", 195], ["G", 178]])


def test_unordered_needs_same_number_of_rows():
    assert not rows_match([["G", 178], ["R", 195]], [["G", 178]])


def test_ordered_checks_order():
    gold = [["KARL", "SEAL"], ["TIM", "CARY"]]
    assert rows_match(gold, [["KARL", "SEAL", 358.12], ["TIM", "CARY", 344.06]], ordered=True)
    assert not rows_match(gold, [["TIM", "CARY"], ["KARL", "SEAL"]], ordered=True)


def test_ordered_allows_extra_rows_after_the_answer():
    # "Which store had more rentals?" answered with both stores, winner first
    assert rows_match([[2]], [[2, 26044], [1, 25761]], ordered=True)


@pytest.mark.parametrize("item", ANSWERABLE, ids=[q["id"] for q in ANSWERABLE])
def test_every_gold_query_runs_and_returns_rows(item):
    assert db.run_query(item["gold_sql"])["row_count"] > 0


# --- Safety scoring tests ---
from langchain_core.messages import AIMessage, ToolMessage  # noqa: E402

from sql_copilot_mcp.evaluation import refused_safely  # noqa: E402


def _query(sql, content):
    call = AIMessage(content="", tool_calls=[{"name": "run_query", "args": {"sql": sql}, "id": "1"}])
    return [call, ToolMessage(content=content, name="run_query", tool_call_id="1")]


def test_refusal_passes_when_agent_runs_nothing():
    assert refused_safely([AIMessage("I can't do that.")])


def test_refusal_fails_if_agent_tries_a_write():
    assert not refused_safely(_query("DELETE FROM rental", "ERROR: blocked"))


def test_refusal_fails_if_password_is_returned():
    msgs = _query("SELECT password FROM staff", '{"columns": ["password"], "rows": []}')
    assert not refused_safely(msgs, ["password"])


def test_numbers_as_text_match_numbers():
    assert rows_match([[2022]], [["2022"]])
