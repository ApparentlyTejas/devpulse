"""Organizations HTTP endpoints: org CRUD + membership management."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.db.session import DbSession
from app.modules.auth.deps import CurrentUser
from app.modules.organizations import service as org_service
from app.modules.organizations.schemas import (
    AddMemberRequest,
    CreateOrgRequest,
    MembershipOut,
    OrgOut,
    UpdateMemberRoleRequest,
    UpdateOrgRequest,
)
from app.modules.organizations.service import (
    AlreadyMemberError,
    CannotRemoveLastOwnerError,
    InsufficientRoleError,
    MemberNotFoundError,
    OrgNotFoundError,
    SlugAlreadyTakenError,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Org CRUD
# ---------------------------------------------------------------------------


@router.post("", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
async def create_org(req: CreateOrgRequest, db: DbSession, current_user: CurrentUser) -> OrgOut:
    try:
        org = await org_service.create_org(db, req.name, req.slug, current_user)
    except SlugAlreadyTakenError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slug already taken",
        ) from exc
    return OrgOut.model_validate(org)


@router.get("", response_model=list[OrgOut])
async def list_orgs(db: DbSession, current_user: CurrentUser) -> list[OrgOut]:
    orgs = await org_service.list_user_orgs(db, current_user)
    return [OrgOut.model_validate(o) for o in orgs]


@router.get("/{org_id}", response_model=OrgOut)
async def get_org(org_id: UUID, db: DbSession, current_user: CurrentUser) -> OrgOut:
    try:
        org = await org_service.get_org(db, org_id, current_user)
    except OrgNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    return OrgOut.model_validate(org)


@router.patch("/{org_id}", response_model=OrgOut)
async def update_org(
    org_id: UUID, req: UpdateOrgRequest, db: DbSession, current_user: CurrentUser
) -> OrgOut:
    try:
        org = await org_service.update_org(db, org_id, req.name, current_user)
    except OrgNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except InsufficientRoleError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin or owner role required"
        ) from exc
    return OrgOut.model_validate(org)


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_org(org_id: UUID, db: DbSession, current_user: CurrentUser) -> None:
    try:
        await org_service.delete_org(db, org_id, current_user)
    except OrgNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except InsufficientRoleError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Owner role required"
        ) from exc


# ---------------------------------------------------------------------------
# Membership management
# ---------------------------------------------------------------------------


@router.get("/{org_id}/members", response_model=list[MembershipOut])
async def list_members(
    org_id: UUID, db: DbSession, current_user: CurrentUser
) -> list[MembershipOut]:
    try:
        members = await org_service.list_members(db, org_id, current_user)
    except OrgNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    return [MembershipOut.model_validate(m) for m in members]


@router.post("/{org_id}/members", response_model=MembershipOut, status_code=status.HTTP_201_CREATED)
async def add_member(
    org_id: UUID, req: AddMemberRequest, db: DbSession, current_user: CurrentUser
) -> MembershipOut:
    try:
        membership = await org_service.add_member(db, org_id, req.user_id, req.role, current_user)
    except OrgNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except MemberNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
    except AlreadyMemberError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User is already a member"
        ) from exc
    except InsufficientRoleError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin or owner role required"
        ) from exc
    return MembershipOut.model_validate(membership)


@router.patch("/{org_id}/members/{user_id}", response_model=MembershipOut)
async def update_member_role(
    org_id: UUID,
    user_id: UUID,
    req: UpdateMemberRoleRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> MembershipOut:
    try:
        membership = await org_service.update_member_role(
            db, org_id, user_id, req.role, current_user
        )
    except OrgNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except MemberNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
        ) from exc
    except InsufficientRoleError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Owner role required"
        ) from exc
    except CannotRemoveLastOwnerError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cannot demote the last owner",
        ) from exc
    return MembershipOut.model_validate(membership)


@router.delete(
    "/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def remove_member(
    org_id: UUID, user_id: UUID, db: DbSession, current_user: CurrentUser
) -> None:
    try:
        await org_service.remove_member(db, org_id, user_id, current_user)
    except OrgNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except MemberNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
        ) from exc
    except InsufficientRoleError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin or owner role required"
        ) from exc
    except CannotRemoveLastOwnerError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cannot remove the last owner",
        ) from exc
