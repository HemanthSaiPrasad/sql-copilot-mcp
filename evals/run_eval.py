"""Run every question in questions.json through the agent and score it.

Usage:  uv run python evals/run_eval.py            (all questions)
        uv run python evals/run_eval.py e1 h3      (only some questions)
"""

import asyncio
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sql_copilot_mcp import db
from sql_copilot_mcp.agent import MODEL, SCHEMA_MODE, ask
from sql_copilot_mcp.evaluation import last_query_rows, refused_safely, rows_match, usage

HERE = Path(__file__).parent
# Approximate Claude Haiku 4.5 prices in USD per million tokens. Check current pricing before quoting.
PRICE_IN, PRICE_OUT = 1.00, 5.00


async def evaluate(item: dict) -> dict:
    is_safety = item.get("expect") == "refuse"
    gold_rows = [] if is_safety else db.run_query(item["gold_sql"])["rows"]
    start = time.perf_counter()
    messages = []
    try:
        result = await ask(item["question"])
        messages = result["messages"]
        pred_rows = last_query_rows(messages)
        stats = usage(messages)
        error = None
    except Exception as e:  # a crash counts as a wrong answer, but we keep going
        pred_rows, stats, error = None, {"tool_calls": 0, "input_tokens": 0, "output_tokens": 0}, str(e)
    seconds = time.perf_counter() - start
    if is_safety:
        correct = error is None and refused_safely(messages, item.get("forbidden_columns", []))
    else:
        correct = pred_rows is not None and rows_match(gold_rows, pred_rows, item.get("ordered", False))
    return {**item, "correct": correct, "seconds": round(seconds, 1), "error": error,
            "gold_rows": gold_rows, "pred_rows": pred_rows, **stats}


async def main(only: list[str]) -> None:
    questions = json.loads((HERE / "questions.json").read_text())
    if only:
        questions = [q for q in questions if q["id"] in only]

    results = []
    for item in questions:  # one at a time, to stay well under API rate limits
        r = await evaluate(item)
        results.append(r)
        mark = "PASS" if r["correct"] else "FAIL"
        print(f"{mark}  {r['id']:<4} {r['level']:<7} {r['tool_calls']} calls  {r['seconds']:>5}s  {r['question']}")
        if not r["correct"]:
            if r.get("expect") == "refuse":
                print(f"        UNSAFE: expected a refusal, got rows {(r['pred_rows'] or [])[:3]}  {r['error'] or ''}")
            else:
                print(f"        expected {r['gold_rows'][:3]}\n        got      {(r['pred_rows'] or [])[:3]}  {r['error'] or ''}")

    # --- Summary ---
    by_level = defaultdict(list)
    for r in results:
        by_level[r["level"]].append(r["correct"])
    total_in = sum(r["input_tokens"] for r in results)
    total_out = sum(r["output_tokens"] for r in results)
    cost = total_in / 1e6 * PRICE_IN + total_out / 1e6 * PRICE_OUT
    passed = sum(r["correct"] for r in results)

    lines = [
        f"# Evaluation results ({datetime.now():%Y-%m-%d %H:%M}, model `{MODEL}`, schema mode `{SCHEMA_MODE}`)",
        "",
        f"**Accuracy: {passed}/{len(results)} ({passed / len(results):.0%})**",
        "",
        "| Level | Correct |",
        "|---|---|",
        *[f"| {lvl} | {sum(v)}/{len(v)} |" for lvl, v in by_level.items()],
        "",
        f"- Average tool calls per question: {sum(r['tool_calls'] for r in results) / len(results):.1f}",
        f"- Average time per question: {sum(r['seconds'] for r in results) / len(results):.1f}s",
        f"- Tokens: {total_in:,} in / {total_out:,} out (estimated cost ${cost:.3f})",
    ]
    summary = "\n".join(lines)
    print("\n" + summary)
    (HERE / f"results_{SCHEMA_MODE}.md").write_text(summary + "\n")
    (HERE / f"results_{SCHEMA_MODE}.json").write_text(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
