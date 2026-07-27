"""Contract tests for authenticated, user-scoped meal history."""

from datetime import UTC, datetime

from sqlalchemy import delete

from backend.config import settings
from backend.db.models import MealLog, User
from backend.services.auth import TokenManager

USER_A = "00000000-0000-0000-0000-000000000001"
USER_B = "00000000-0000-0000-0000-000000000002"
CLIENT_PREFIX = "meal-contract-"


def _meal_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "client_entry_id": f"{CLIENT_PREFIX}pho",
        "eaten_at": "2026-07-26T12:30:00+07:00",
        "meal_type": "lunch",
        "dish_name": "Phở bò",
        "total_grams": 450,
        "calories": 480,
        "protein_g": 28,
        "fat_g": 14,
        "carbs_g": 60,
        "fiber_g": 4,
        "source": "analyze",
        "analyze_source": "vision",
    }
    payload.update(overrides)
    return payload


async def _ensure_users(db_session) -> None:
    for user_id, email in (
        (USER_A, "meal-a@example.com"),
        (USER_B, "meal-b@example.com"),
    ):
        if await db_session.get(User, user_id) is None:
            db_session.add(
                User(
                    id=user_id,
                    email=email,
                    display_name=email,
                    password_hash="not-used",
                )
            )
    await db_session.commit()


def _token_for(user_id: str) -> str:
    token, _ = TokenManager.from_settings(settings).create_access_token(
        user_id=user_id,
        role="user",
    )
    return token


async def test_create_is_idempotent_and_lists_only_current_user(
    client,
    db_session,
) -> None:
    await _ensure_users(db_session)
    await db_session.execute(
        delete(MealLog).where(MealLog.client_entry_id.like(f"{CLIENT_PREFIX}%"))
    )
    await db_session.commit()

    first = client.post("/api/v1/meals", json=_meal_payload())
    second = client.post(
        "/api/v1/meals",
        json=_meal_payload(calories=500, protein_g=30),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["calories"] == 500

    created_other = client.post(
        "/api/v1/meals",
        headers={"Authorization": f"Bearer {_token_for(USER_B)}"},
        json=_meal_payload(
            client_entry_id=f"{CLIENT_PREFIX}bun",
            dish_name="Bún bò",
        ),
    )
    assert created_other.status_code == 201

    listed = client.get(
        "/api/v1/meals",
        params={"from": "2026-07-26", "to": "2026-07-26"},
    )

    assert listed.status_code == 200
    assert [item["dish_name"] for item in listed.json()["items"]] == ["Phở bò"]


async def test_patch_and_delete_cannot_cross_user_boundary(
    client,
    db_session,
) -> None:
    await _ensure_users(db_session)
    created = client.post(
        "/api/v1/meals",
        headers={"Authorization": f"Bearer {_token_for(USER_B)}"},
        json=_meal_payload(client_entry_id=f"{CLIENT_PREFIX}private"),
    )
    assert created.status_code in {200, 201}
    meal_id = created.json()["id"]

    assert client.patch(
        f"/api/v1/meals/{meal_id}",
        json={"dish_name": "Đã xem trộm"},
    ).status_code == 404
    assert client.delete(f"/api/v1/meals/{meal_id}").status_code == 404


async def test_summary_uses_vietnam_timezone_and_python_sql_totals(
    client,
    db_session,
) -> None:
    await _ensure_users(db_session)
    await db_session.execute(
        delete(MealLog).where(
            MealLog.user_id == USER_A,
            MealLog.client_entry_id.like(f"{CLIENT_PREFIX}%"),
        )
    )
    await db_session.commit()

    for suffix, eaten_at, calories in (
        ("late", "2026-07-26T23:45:00+07:00", 300),
        ("next", "2026-07-27T00:15:00+07:00", 200),
    ):
        response = client.post(
            "/api/v1/meals",
            json=_meal_payload(
                client_entry_id=f"{CLIENT_PREFIX}summary-{suffix}",
                eaten_at=eaten_at,
                calories=calories,
            ),
        )
        assert response.status_code in {200, 201}

    summary = client.get(
        "/api/v1/meals/summary",
        params={
            "from": "2026-07-26",
            "to": "2026-07-26",
            "timezone": "Asia/Ho_Chi_Minh",
        },
    )

    assert summary.status_code == 200
    body = summary.json()
    assert body["meal_count"] == 1
    assert body["totals"]["calories"] == 300
    assert body["date_from"] == "2026-07-26"
    assert body["date_to"] == "2026-07-26"


def test_meal_input_rejects_negative_nutrition_and_unknown_meal_type(client) -> None:
    negative = client.post("/api/v1/meals", json=_meal_payload(calories=-1))
    unknown_type = client.post(
        "/api/v1/meals",
        json=_meal_payload(meal_type="brunch"),
    )

    assert negative.status_code == 422
    assert unknown_type.status_code == 422


def test_meal_input_rejects_naive_timestamp(client) -> None:
    response = client.post(
        "/api/v1/meals",
        json=_meal_payload(eaten_at=datetime(2026, 7, 26, 12, 0).isoformat()),
    )

    assert response.status_code == 422


def test_meal_input_accepts_utc_timestamp(client) -> None:
    response = client.post(
        "/api/v1/meals",
        json=_meal_payload(
            client_entry_id=f"{CLIENT_PREFIX}utc",
            eaten_at=datetime(2026, 7, 26, 5, 30, tzinfo=UTC).isoformat(),
        ),
    )

    assert response.status_code in {200, 201}
