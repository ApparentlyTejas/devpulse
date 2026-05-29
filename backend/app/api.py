"""API router composition root.

As we add domain modules (auth, organizations, services, ...) we mount their
routers here. Keeping this file as the single mount point gives us one place
to find every endpoint and one place to apply version-wide concerns.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.organizations.router import router as orgs_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(orgs_router, prefix="/organizations", tags=["organizations"])
