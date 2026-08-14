"""Integration tests that ensure chat tools read only server-side user facts."""

from datetime import datetime

from sqlalchemy import delete

from backend.db.models import MealLog, User
from backend.services import chat_service
from backend.services.chat_tools import ParsedToolCall

USER_A = "00000000-0000-0000-0000-000000000001"
USER_B = "00000000-0000-0000-0000-000000000002"


async def _ensure_users(db_session) -> None:
    for user_id, email in (
        (USER_A, "chat-a@example.com"),
        (USER_B, "chat-b@example.com"),
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


async def test_summary_tool_is_scoped_to_user_and_timezone(db_session) -> None:
    await _ensure_users(db_session)
    await db_session.execute(delete(MealLog).where(MealLog.client_entry_id == "chat-tool-fixture"))
    db_session.add_all(
        [
            MealLog(
                user_id=USER_A,
                client_entry_id="chat-tool-fixture",
                eaten_at=datetime.fromisoformat("2099-01-02T12:00:00+07:00"),
                meal_type="lunch",
                dish_name="Phở bò",
                total_grams=450,
                calories=480,
                protein_g=28,
                fat_g=14,
                carbs_g=60,
                fiber_g=4,
                source="manual",
            ),
            MealLog(
                user_id=USER_B,
                client_entry_id="chat-tool-fixture",
                eaten_at=datetime.fromisoformat("2099-01-02T12:00:00+07:00"),
                meal_type="lunch",
                dish_name="Bún bò",
                total_grams=400,
                calories=700,
                protein_g=30,
                fat_g=20,
                carbs_g=90,
                fiber_g=5,
                source="manual",
            ),
        ]
    )
    await db_session.commit()

    context = await chat_service._execute_tool(
        db_session,
        USER_A,
        ParsedToolCall(
            tool="get_summary",
            arguments={"date_from": "2099-01-02", "date_to": "2099-01-02"},
        ),
        timezone="Asia/Ho_Chi_Minh",
    )

    assert context.payload["meal_count"] == 1
    assert context.payload["totals"]["calories"] == 480
