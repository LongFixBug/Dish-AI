from uuid import uuid4

from sqlalchemy import delete, select

from backend.db.models import User, UserIdentity


async def test_google_login_creates_and_reuses_identity(
    client,
    db_session,
    monkeypatch,
) -> None:
    email = f"google-{uuid4().hex}@example.com"
    user_id = None

    monkeypatch.setattr(
        "backend.api.auth.verify_google_id_token",
        lambda token, audience: type(
            "GoogleIdentity",
            (),
            {
                "subject": "google-sub-test",
                "email": email,
                "display_name": "Google User",
            },
        )(),
    )

    try:
        first = client.post(
            "/api/v1/auth/google",
            json={"id_token": "a" * 120},
        )
        assert first.status_code == 200, first.text
        user_id = first.json()["user"]["id"]

        identity = await db_session.scalar(
            select(UserIdentity).where(
                UserIdentity.provider_subject == "google-sub-test"
            )
        )
        assert identity is not None
        assert str(identity.user_id) == user_id

        second = client.post(
            "/api/v1/auth/google",
            json={"id_token": "a" * 120},
        )
        assert second.status_code == 200, second.text
        assert second.json()["user"]["id"] == user_id
    finally:
        if user_id is not None:
            await db_session.execute(delete(UserIdentity).where(UserIdentity.user_id == user_id))
            await db_session.execute(delete(User).where(User.id == user_id))
            await db_session.commit()


async def test_google_login_does_not_take_over_password_account(
    client,
    db_session,
    monkeypatch,
) -> None:
    email = f"existing-{uuid4().hex}@example.com"
    user = User(
        email=email,
        display_name="Password User",
        password_hash="existing-password-hash",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    monkeypatch.setattr(
        "backend.api.auth.verify_google_id_token",
        lambda token, audience: type(
            "GoogleIdentity",
            (),
            {
                "subject": "google-sub-existing",
                "email": email,
                "display_name": "Google User",
            },
        )(),
    )

    try:
        response = client.post(
            "/api/v1/auth/google",
            json={"id_token": "a" * 120},
        )

        assert response.status_code == 409
        assert "liên kết" in response.json()["detail"]
    finally:
        await db_session.execute(delete(User).where(User.id == user.id))
        await db_session.commit()
