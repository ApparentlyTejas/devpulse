"""FastAPI dependencies for the auth domain.

`CurrentUser` is the primary import for any route that requires authentication.
It resolves to the authenticated `User` ORM instance.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db.session import DbSession
from app.modules.auth import service as auth_service
from app.modules.auth.models import User
from app.modules.auth.security import InvalidAccessTokenError, decode_access_token

_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> User:
    try:
        claims = decode_access_token(credentials.credentials)
    except InvalidAccessTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = await auth_service.get_user_by_id(db, claims.sub)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
