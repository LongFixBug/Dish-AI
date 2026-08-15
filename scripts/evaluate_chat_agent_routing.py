"""Evaluate route/tool selection for the bounded FoodAI chat assistant."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, get_args

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services import chat_service  # noqa: E402
from schemas.chat import ChatRequest, ChatRoute, ChatToolName  # noqa: E402

DEFAULT_CASES = PROJECT_ROOT / "data" / "eval" / "chat_agent_routing_v1.jsonl"
VALID_ROUTES = frozenset(get_args(ChatRoute))
VALID_TOOLS = frozenset(get_args(ChatToolName))


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
            case_id = case["case_id"]
            message = case["message"]
            route = case["expected_route"]
            tools = tuple(case["expected_tools"])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Case không hợp lệ ở dòng {line_number}") from exc
        if (
            not isinstance(case_id, str)
            or not isinstance(message, str)
            or not message.strip()
            or not isinstance(route, str)
            or route not in VALID_ROUTES
            or (not tools and route not in {"general", "out_of_scope"})
            or any(not isinstance(tool, str) or tool not in VALID_TOOLS for tool in tools)
        ):
            raise ValueError(f"Case không hợp lệ ở dòng {line_number}")
        cases.append({"case_id": case_id, "message": message, "expected_route": route, "expected_tools": tools})
    if not cases:
        raise ValueError("Không có case benchmark")
    return cases


def score_plan(case: dict[str, Any], *, route: str, tools: tuple[str, ...]) -> dict[str, bool]:
    route_correct = route == case["expected_route"]
    tools_correct = set(tools) == set(case["expected_tools"])
    return {"route_correct": route_correct, "tools_correct": tools_correct, "correct": route_correct and tools_correct}


async def live_report(cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for case in cases:
        request = ChatRequest(message=case["message"])
        planner_plan = await chat_service._plan(request)
        plan = chat_service.ground_plan(request, planner_plan)
        tools = tuple(call.tool for call in plan.calls)
        rows.append({
            "case_id": case["case_id"],
            "planner_route": planner_plan.route,
            "planner_tools": tuple(call.tool for call in planner_plan.calls),
            "actual_route": plan.route,
            "actual_tools": tools,
            **score_plan(case, route=plan.route, tools=tools),
        })
    total = len(rows)
    return {
        "n_cases": total,
        "route_accuracy": round(sum(row["route_correct"] for row in rows) / total, 4),
        "tool_set_accuracy": round(sum(row["tools_correct"] for row in rows) / total, 4),
        "exact_plan_accuracy": round(sum(row["correct"] for row in rows) / total, 4),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--live", action="store_true", help="Call the configured LLM planner.")
    args = parser.parse_args()
    cases = load_cases(args.cases)
    if not args.live:
        print(json.dumps({"n_cases": len(cases), "status": "valid"}, ensure_ascii=False))
        return
    print(json.dumps(asyncio.run(live_report(cases)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
