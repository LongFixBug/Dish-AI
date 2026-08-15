"""Contracts for the hand-authored agentic chat routing benchmark."""


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
