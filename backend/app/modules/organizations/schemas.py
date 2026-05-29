"""Pydantic schemas for the organizations domain."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.organizations.models import OrgRole


class CreateOrgRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    # URL-safe slug: lowercase letters, digits, hyphens only.
    slug: str = Field(
        min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$"
    )


class UpdateOrgRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)


class OrgOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    created_at: datetime
    updated_at: datetime


class MemberUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str | None


class MembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user: MemberUserOut
    role: OrgRole
    created_at: datetime


class AddMemberRequest(BaseModel):
    user_id: UUID
    role: OrgRole = OrgRole.MEMBER


class UpdateMemberRoleRequest(BaseModel):
    role: OrgRole
