"""SQLAlchemy models for organizations + memberships.

Multi-tenancy lives here. An `Organization` is the tenant. Users join
organizations via `OrganizationMembership` rows that carry a role.

Cascade behavior:
  - DELETE on `organizations` cascades to `organization_memberships`.
  - DELETE on `users` cascades to `organization_memberships`.
  We rarely hard-delete in production (prefer is_active=false), but the
  cascade makes the data model coherent if we do.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.auth.models import User


class OrgRole(str, enum.Enum):
    """A user's role within a single organization.

    Stored as a VARCHAR with a CHECK constraint (not a native Postgres
    enum), which makes adding new roles a normal column-default migration
    instead of an `ALTER TYPE` migration that can lock the table.
    """

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # URL-safe slug. Lower-cased by service layer before insert so case-only
    # variants ("Acme" vs "acme") can't both exist.
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # Display name. Plain text, not unique — two orgs can share a display name.
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    memberships: Mapped[list[OrganizationMembership]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Organization {self.slug!r}>"


class OrganizationMembership(Base, TimestampMixin):
    __tablename__ = "organization_memberships"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[OrgRole] = mapped_column(
        Enum(
            OrgRole,
            name="org_role",
            native_enum=False,  # VARCHAR + CHECK, not native enum
            length=20,
            validate_strings=True,
            # Store enum *values* ("owner") not member *names* ("OWNER").
            # Default SQLAlchemy behavior uses names; we want lowercase in DB.
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=OrgRole.MEMBER,
    )

    organization: Mapped[Organization] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")

    __table_args__ = (
        # A user can only be in an org once.
        UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
        # Lookup "what orgs is this user in?" is hot — index it.
        Index("ix_membership_user_id", "user_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Membership org={self.organization_id} user={self.user_id} role={self.role}>"
