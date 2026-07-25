"""Security contracts for password and token handling."""

from datetime import UTC, datetime, timedelta

import pytest

from backend.services.auth import (
    AccessTokenError,
    PasswordManager,
    TokenManager,
    hash_refresh_token,
)


def test_password_hash_uses_argon2id_and_never_contains_plaintext() -> None:
    manager = PasswordManager()

    encoded = manager.hash("mat-khau-rat-kho-doan-123")

    assert encoded.startswith("$argon2id$")
    assert "mat-khau-rat-kho-doan-123" not in encoded
    assert manager.verify("mat-khau-rat-kho-doan-123", encoded) is True
    assert manager.verify("sai-mat-khau", encoded) is False
    assert manager.verify_or_dummy("sai-mat-khau", None) is False


def test_access_token_round_trip_preserves_minimal_identity_claims() -> None:
    manager = TokenManager(
        secret_key="test-secret-key-longer-than-thirty-two-bytes",
        issuer="foodai-test",
        audience="foodai-mobile-test",
        access_ttl=timedelta(minutes=15),
    )

    token, expires_in = manager.create_access_token(
        user_id="user-123",
        role="user",
        now=datetime(2026, 7, 25, tzinfo=UTC),
    )
    claims = manager.decode_access_token(
        token,
        now=datetime(2026, 7, 25, 0, 1, tzinfo=UTC),
    )

    assert expires_in == 900
    assert claims.user_id == "user-123"
    assert claims.role == "user"


def test_access_token_rejects_expired_and_tampered_values() -> None:
    manager = TokenManager(
        secret_key="test-secret-key-longer-than-thirty-two-bytes",
        issuer="foodai-test",
        audience="foodai-mobile-test",
        access_ttl=timedelta(seconds=1),
    )
    token, _ = manager.create_access_token(
        user_id="user-123",
        role="user",
        now=datetime(2026, 7, 25, tzinfo=UTC),
    )

    with pytest.raises(AccessTokenError):
        manager.decode_access_token(
            token,
            now=datetime(2026, 7, 25, 0, 0, 2, tzinfo=UTC),
        )
    with pytest.raises(AccessTokenError):
        manager.decode_access_token(f"{token}tampered")


def test_refresh_token_is_stored_as_a_one_way_digest() -> None:
    raw = "refresh-token-value"

    digest = hash_refresh_token(raw)

    assert raw not in digest
    assert digest == hash_refresh_token(raw)
    assert digest != hash_refresh_token("another-token")
