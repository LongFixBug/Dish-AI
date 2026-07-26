"""Integration contract tests for persisted nutrition goals."""


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "age": 30,
        "sex": "male",
        "height_cm": 170,
        "weight_kg": 70,
        "activity_level": "moderate",
        "goal": "lose",
        "target_weight_kg": 65,
        "target_days": 90,
    }
    payload.update(overrides)
    return payload


def test_save_and_get_goal_are_scoped_to_current_user(client) -> None:
    saved = client.post("/api/v1/nutrition-goals", json=_payload())

    assert saved.status_code == 200
    body = saved.json()
    assert body["user_id"] == "00000000-0000-0000-0000-000000000001"
    assert body["goal"]["target_calories"] < body["goal"]["maintenance_calories"]
    assert body["goal"]["reference"]["algorithm_version"] == "mifflin_goal_rate_v1"

    current = client.get("/api/v1/nutrition-goals/current")

    assert current.status_code == 200
    assert current.json()["goal"]["target_calories"] == body["goal"]["target_calories"]


def test_saving_a_second_goal_replaces_the_current_goal(client) -> None:
    first = client.post("/api/v1/nutrition-goals", json=_payload())
    assert first.status_code == 200

    second = client.post(
        "/api/v1/nutrition-goals",
        json=_payload(
            goal="gain",
            weight_kg=70,
            target_weight_kg=75,
            target_days=180,
        ),
    )

    assert second.status_code == 200
    assert second.json()["goal"]["target_calories"] > second.json()["goal"]["maintenance_calories"]
