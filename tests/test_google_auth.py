import pytest

from backend.services.google_auth import GoogleAuthError, verify_google_id_token


def test_google_token_requires_verified_email(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.services.google_auth.id_token.verify_oauth2_token",
        lambda *args, **kwargs: {
            "sub": "google-sub-1",
            "email": "an@example.com",
            "email_verified": False,
            "name": "Nguyễn Văn An",
        },
    )

    with pytest.raises(GoogleAuthError, match="Email Google chưa được xác minh"):
        verify_google_id_token("raw-id-token", "web-client-id")


def test_google_token_returns_normalized_identity(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.services.google_auth.id_token.verify_oauth2_token",
        lambda *args, **kwargs: {
            "sub": "google-sub-1",
            "email": " AN@EXAMPLE.COM ",
            "email_verified": True,
            "name": " Nguyễn Văn An ",
        },
    )

    identity = verify_google_id_token("raw-id-token", "web-client-id")

    assert identity.subject == "google-sub-1"
    assert identity.email == "an@example.com"
    assert identity.display_name == "Nguyễn Văn An"
