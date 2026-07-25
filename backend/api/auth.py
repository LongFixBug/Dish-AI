"""Account registration, login and rotating-token endpoints."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import CurrentUser, require_user, token_manager
from backend.config import settings
from backend.db.models import RefreshToken, User
from backend.db.postgres import get_session
from backend.services.auth import (
    PasswordManager,
    create_refresh_token,
    hash_refresh_token,
)
from schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
password_manager = PasswordManager()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    existing = await session.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email này đã được sử dụng.")

    user = User(
        email=payload.email,
        display_name=payload.display_name,
        password_hash=password_manager.hash(payload.password),
    )
    session.add(user)
    try:
        await session.flush()
        response = _issue_session(session, user)
        await session.commit()
        await session.refresh(user)
        return response
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Email này đã được sử dụng.") from exc


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    user = await session.scalar(select(User).where(User.email == payload.email))
    password_valid = password_manager.verify_or_dummy(
        payload.password,
        user.password_hash if user is not None else None,
    )
    if (
        user is None
        or not user.is_active
        or not password_valid
    ):
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng.")

    response = _issue_session(session, user)
    await session.commit()
    return response


@router.post("/refresh", response_model=TokenResponse)
async def refresh_session(
    payload: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    now = datetime.now(UTC)
    result = await session.execute(
        select(RefreshToken, User)
        .join(User, User.id == RefreshToken.user_id)
        .where(RefreshToken.token_hash == hash_refresh_token(payload.refresh_token))
        .with_for_update()
    )
    row = result.one_or_none()
    if row is None:
        raise _invalid_refresh_token()

    token, user = row
    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if token.revoked_at is not None or expires_at <= now or not user.is_active:
        raise _invalid_refresh_token()

    token.revoked_at = now
    response = _issue_session(session, user, now=now)
    await session.commit()
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    current_user: Annotated[CurrentUser, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    token = await session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(payload.refresh_token),
            RefreshToken.user_id == current_user.id,
        )
    )
    if token is not None and token.revoked_at is None:
        token.revoked_at = datetime.now(UTC)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: Annotated[CurrentUser, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    user = await session.get(User, current_user.id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Tài khoản không còn hoạt động.")
    return user


def _issue_session(
    session: AsyncSession,
    user: User,
    *,
    now: datetime | None = None,
) -> TokenResponse:
    issued_at = now or datetime.now(UTC)
    access_token, expires_in = token_manager.create_access_token(
        user_id=str(user.id),
        role=user.role,
        now=issued_at,
    )
    raw_refresh_token = create_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh_token),
            expires_at=issued_at + timedelta(days=settings.refresh_token_days),
        )
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


def _invalid_refresh_token() -> HTTPException:
    return HTTPException(status_code=401, detail="Refresh token không hợp lệ hoặc đã hết hạn.")
