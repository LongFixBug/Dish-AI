"""Verification and normalization of Google OpenID Connect identity tokens."""

from dataclasses import dataclass
from typing import Any

from google.auth.exceptions import GoogleAuthError as GoogleLibraryAuthError
from google.auth.transport import requests
from google.oauth2 import id_token


class GoogleAuthError(ValueError):
    """Raised when a Google identity token cannot be trusted."""


class GoogleAuthConfigurationError(GoogleAuthError):
    """Raised when the server has no Google client configuration."""


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str
    display_name: str


def verify_google_id_token(raw_token: str, audience: str) -> GoogleIdentity:
    """Verify Google's signature and claims, then return safe identity fields."""
    if not audience:
        raise GoogleAuthConfigurationError(
            "Google login chưa được cấu hình trên máy chủ."
        )
    try:
        claims = id_token.verify_oauth2_token(
            raw_token,
            requests.Request(),
            audience=audience,
        )
    except (GoogleLibraryAuthError, ValueError, TypeError) as exc:
        raise GoogleAuthError("Google ID token không hợp lệ hoặc đã hết hạn.") from exc

    subject = _required_claim(claims, "sub")
    email = _required_claim(claims, "email").strip().lower()
    if claims.get("email_verified") is not True:
        raise GoogleAuthError("Email Google chưa được xác minh.")
    display_name = str(claims.get("name") or email.split("@", 1)[0]).strip()
    return GoogleIdentity(
        subject=subject,
        email=email,
        display_name=display_name[:100],
    )


def _required_claim(claims: dict[str, Any], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str) or not value.strip():
        raise GoogleAuthError("Google ID token thiếu thông tin bắt buộc.")
    return value.strip()
