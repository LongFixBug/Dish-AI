"""Integration contracts for account authentication and protected APIs."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User


async def test_register_login_refresh_me_and_logout(
    anonymous_client: TestClient,
    db_session: AsyncSession,
) -> None:
    email = f"auth-{uuid4().hex}@example.com"
    password = "mat-khau-an-toan-123"

    try:
        registered = anonymous_client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "display_name": "Nguyễn Văn An",
            },
        )
        assert registered.status_code == 201, registered.text
        registration = registered.json()
        assert registration["token_type"] == "bearer"
        assert registration["user"]["email"] == email
        assert registration["access_token"]
        assert registration["refresh_token"]

        duplicate = anonymous_client.post(
            "/api/v1/auth/register",
            json={
                "email": email.upper(),
                "password": password,
                "display_name": "Tên khác",
            },
        )
        assert duplicate.status_code == 409

        wrong_password = anonymous_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "sai-mat-khau"},
        )
        assert wrong_password.status_code == 401

        logged_in = anonymous_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert logged_in.status_code == 200, logged_in.text
        session = logged_in.json()

        me = anonymous_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {session['access_token']}"},
        )
        assert me.status_code == 200, me.text
        assert me.json()["email"] == email

        refreshed = anonymous_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": session["refresh_token"]},
        )
        assert refreshed.status_code == 200, refreshed.text
        rotated = refreshed.json()
        assert rotated["refresh_token"] != session["refresh_token"]

        reused = anonymous_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": session["refresh_token"]},
        )
        assert reused.status_code == 401

        logged_out = anonymous_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {rotated['access_token']}"},
            json={"refresh_token": rotated["refresh_token"]},
        )
        assert logged_out.status_code == 204

        after_logout = anonymous_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": rotated["refresh_token"]},
        )
        assert after_logout.status_code == 401
    finally:
        await db_session.execute(delete(User).where(User.email == email))
        await db_session.commit()


def test_expensive_endpoint_requires_access_token(
    anonymous_client: TestClient,
) -> None:
    response = anonymous_client.post(
        "/api/v1/analyze",
        files={"file": ("food.jpg", b"not-an-image", "image/jpeg")},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Cần đăng nhập để tiếp tục."
