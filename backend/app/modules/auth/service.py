"""Auth domain service: register, login, token rotation, logout.

All business logic lives here; the router layer is thin HTTP glue.
Domain errors are plain exceptions — the router maps them to HTTP status codes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import RefreshToken, User
from app.modules.auth.schemas import RegisterRequest, TokenPairResponse
from app.modules.auth.security import (
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    mint_access_token,
    password_needs_rehash,
    verify_password,
)

# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


class UserInactiveError(Exception):
    pass


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


async def register(db: AsyncSession, req: RegisterRequest) -> TokenPairResponse:
    existing = await db.scalar(select(User).where(User.email == req.email.lower()))
    if existing is not None:
        raise EmailAlreadyRegisteredError(req.email)

    user = User(
        email=req.email.lower(),
        password_hash=hash_password(req.password),
        full_name=req.full_name,
    )
    db.add(user)
    await db.flush()  # materialize user.id before issuing tokens

    return await _issue_token_pair(db, user)


async def login(db: AsyncSession, email: str, password: str) -> TokenPairResponse:
    user = await db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError
    if not user.is_active:
        raise UserInactiveError

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    user.last_login_at = datetime.now(tz=UTC)

    return await _issue_token_pair(db, user)


async def refresh_tokens(db: AsyncSession, plaintext: str) -> TokenPairResponse:
    token_hash = hash_refresh_token(plaintext)
    now = datetime.now(tz=UTC)

    token_row = await db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .where(RefreshToken.revoked_at.is_(None))
        .where(RefreshToken.expires_at > now)
    )
    if token_row is None:
        raise InvalidRefreshTokenError

    token_row.revoked_at = now

    user = await db.get(User, token_row.user_id)
    if user is None or not user.is_active:
        raise InvalidRefreshTokenError

    return await _issue_token_pair(db, user)


async def logout(db: AsyncSession, plaintext: str) -> None:
    token_hash = hash_refresh_token(plaintext)
    token_row = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if token_row is not None and token_row.revoked_at is None:
        token_row.revoked_at = datetime.now(tz=UTC)
    # Silently succeed if not found — idempotent logout


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _issue_token_pair(db: AsyncSession, user: User) -> TokenPairResponse:
    access_token, expires_at = mint_access_token(
        user_id=user.id,
        email=user.email,
        org_id=None,
        role=None,
    )
    new_rt = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=new_rt.token_hash,
            expires_at=new_rt.expires_at,
        )
    )
    await db.commit()
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=new_rt.plaintext,
        expires_at=expires_at,
    )
