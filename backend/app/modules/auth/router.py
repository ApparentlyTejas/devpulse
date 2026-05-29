"""Auth HTTP endpoints: register, login, token refresh, logout, me."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.db.session import DbSession
from app.modules.auth import service as auth_service
from app.modules.auth.deps import CurrentUser
from app.modules.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPairResponse,
    UserOut,
)
from app.modules.auth.service import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UserInactiveError,
)

router = APIRouter()


@router.post("/register", response_model=TokenPairResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: DbSession) -> TokenPairResponse:
    try:
        return await auth_service.register(db, req)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc


@router.post("/login", response_model=TokenPairResponse)
async def login(req: LoginRequest, db: DbSession) -> TokenPairResponse:
    try:
        return await auth_service.login(db, req.email, req.password)
    except (InvalidCredentialsError, UserInactiveError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(req: RefreshRequest, db: DbSession) -> TokenPairResponse:
    try:
        return await auth_service.refresh_tokens(db, req.refresh_token)
    except InvalidRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def logout(req: LogoutRequest, db: DbSession) -> None:
    await auth_service.logout(db, req.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(current_user: CurrentUser) -> UserOut:
    return UserOut.model_validate(current_user)
