"""Contracts for the hand-authored agentic chat routing benchmark."""

import pytest


def test_routing_cases_are_valid_and_score_exact_route_and_tools(tmp_path) -> None:
    from scripts.evaluate_chat_agent_routing import load_cases, score_plan

    path = tmp_path / "cases.jsonl"
    path.write_text(
        '{"case_id":"catalog-01","message":"Phở bò bao nhiêu calo?",'
        '"expected_route":"catalog","expected_tools":["search_catalog"]}\n',
        encoding="utf-8",
    )
    cases = load_cases(path)

    assert len(cases) == 1
    assert score_plan(cases[0], route="catalog", tools=("search_catalog",)) == {
        "route_correct": True,
        "tools_correct": True,
        "correct": True,
    }


@pytest.mark.asyncio
async def test_live_report_scores_the_grounded_plan(monkeypatch) -> None:
    from backend.services import chat_service
    from schemas.chat import ChatPlan
    from scripts.evaluate_chat_agent_routing import live_report

    cases = [
        {
            "case_id": "thanks",
            "message": "Cảm ơn nhé.",
            "expected_route": "general",
            "expected_tools": (),
        }
    ]

    async def fake_plan(request):
        return ChatPlan.model_validate({"route": "out_of_scope", "calls": []})

    monkeypatch.setattr(chat_service, "_plan", fake_plan)

    report = await live_report(cases)

    assert report["route_accuracy"] == 1.0
    assert report["rows"][0]["planner_route"] == "out_of_scope"
    assert report["rows"][0]["actual_route"] == "general"
