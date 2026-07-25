"""Shared authentication dependencies for protected API routes."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import settings
from backend.services.auth import AccessTokenError, TokenManager

bearer_scheme = HTTPBearer(auto_error=False)
token_manager = TokenManager.from_settings(settings)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    role: str


def require_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Cần đăng nhập để tiếp tục.")
    try:
        claims = token_manager.decode_access_token(credentials.credentials)
    except AccessTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn.",
        ) from exc
    return CurrentUser(id=claims.user_id, role=claims.role)


def require_admin(
    user: Annotated[CurrentUser, Depends(require_user)],
) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Bạn không có quyền thực hiện thao tác này.")
    return user
