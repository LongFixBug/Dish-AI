"""Password hashing and signed-token primitives for account authentication."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from backend.config import Settings


class AccessTokenError(ValueError):
    """Raised when an access token cannot be trusted."""


@dataclass(frozen=True)
class AccessClaims:
    user_id: str
    role: str


class PasswordManager:
    """Argon2id password hashing with production-oriented defaults."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher(
            time_cost=3,
            memory_cost=65_536,
            parallelism=4,
            hash_len=32,
            salt_len=16,
        )
        self._dummy_hash = self._hasher.hash(secrets.token_urlsafe(32))

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, encoded: str) -> bool:
        try:
            return self._hasher.verify(encoded, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def verify_or_dummy(self, password: str, encoded: str | None) -> bool:
        """Spend the same Argon2 work even when the account does not exist."""
        valid = self.verify(password, encoded or self._dummy_hash)
        return encoded is not None and valid


class TokenManager:
    """Create and verify short-lived HS256 access tokens."""

    def __init__(
        self,
        *,
        secret_key: str,
        issuer: str,
        audience: str,
        access_ttl: timedelta,
    ) -> None:
        if len(secret_key) < 32:
            raise ValueError("Token secret must contain at least 32 characters")
        self._secret_key = secret_key
        self._issuer = issuer
        self._audience = audience
        self._access_ttl = access_ttl

    @classmethod
    def from_settings(cls, settings: Settings) -> "TokenManager":
        return cls(
            secret_key=settings.auth_secret_key,
            issuer=settings.auth_issuer,
            audience=settings.auth_audience,
            access_ttl=timedelta(minutes=settings.access_token_minutes),
        )

    def create_access_token(
        self,
        *,
        user_id: str,
        role: str,
        now: datetime | None = None,
    ) -> tuple[str, int]:
        issued_at = _as_utc(now or datetime.now(UTC))
        expires_at = issued_at + self._access_ttl
        payload = {
            "sub": user_id,
            "role": role,
            "iss": self._issuer,
            "aud": self._audience,
            "iat": issued_at,
            "exp": expires_at,
            "jti": secrets.token_hex(16),
        }
        token = jwt.encode(payload, self._secret_key, algorithm="HS256")
        return token, int(self._access_ttl.total_seconds())

    def decode_access_token(
        self,
        token: str,
        *,
        now: datetime | None = None,
    ) -> AccessClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=["HS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"verify_exp": False, "require": ["sub", "role", "exp"]},
            )
            expires_at = datetime.fromtimestamp(float(payload["exp"]), tz=UTC)
            if expires_at <= _as_utc(now or datetime.now(UTC)):
                raise AccessTokenError("Access token expired")
            user_id = payload["sub"]
            role = payload["role"]
            if not isinstance(user_id, str) or role not in {"user", "admin"}:
                raise AccessTokenError("Invalid access token claims")
            return AccessClaims(user_id=user_id, role=role)
        except AccessTokenError:
            raise
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise AccessTokenError("Invalid access token") from exc


def create_refresh_token() -> str:
    """Return an opaque token with enough entropy for long-lived sessions."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
