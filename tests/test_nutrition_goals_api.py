"""API contract tests for nutrition goal preview."""


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


def test_preview_returns_source_and_calculated_targets(client) -> None:
    response = client.post("/api/v1/nutrition-goals/preview", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["reference"]["algorithm_version"] == "mifflin_goal_rate_v1"
    assert body["reference"]["standard"] == "VN_NCDD_2016"
    assert "nutrition_reference_targets" in body["reference"]["standard_usage"]
    assert body["target_calories"] < body["maintenance_calories"]
    assert body["protein_g"]["target"] > 0


def test_preview_rejects_unsafe_age(client) -> None:
    response = client.post(
        "/api/v1/nutrition-goals/preview",
        json=_payload(age=17),
    )

    assert response.status_code == 422


def test_preview_requires_authentication(anonymous_client) -> None:
    response = anonymous_client.post(
        "/api/v1/nutrition-goals/preview",
        json=_payload(),
    )

    assert response.status_code == 401


def test_preview_returns_review_status_for_medical_condition(client) -> None:
    response = client.post(
        "/api/v1/nutrition-goals/preview",
        json=_payload(medical_conditions=["bệnh thận"]),
    )

    assert response.status_code == 200
    assert response.json()["safety_status"] == "review_required"


def test_preview_returns_table_ready_profile_and_targets(client) -> None:
    response = client.post(
        "/api/v1/nutrition-goals/preview",
        json=_payload(
            age=25,
            height_cm=165,
            weight_kg=75,
            goal="maintain",
            target_weight_kg=75,
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["bmi"] == 27.5
    assert body["profile"]["bmi_category"] == "overweight"
    codes = {row["code"] for row in body["daily_targets"]}
    assert {"energy", "protein", "fiber", "calcium", "iron"}.issubset(codes)
    sodium = next(row for row in body["daily_targets"] if row["code"] == "sodium")
    assert sodium["comparator"] == "<"
