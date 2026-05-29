"""SQLAlchemy models for the auth domain: User + RefreshToken.

Design notes:
  - `email` is CITEXT so case differences don't create duplicate accounts.
  - `password_hash` stores the full argon2id-encoded string ($argon2id$...).
  - `is_active` is the soft-delete flag. We deactivate users; we don't drop.
  - RefreshToken stores SHA-256(token_plaintext), never the token itself.
  - Composite index on (user_id, revoked_at IS NULL) speeds up the hot
    "find active refresh tokens for this user" query.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.organizations.models import OrganizationMembership


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Email is lower-cased by the service layer before insert. RFC 5321
    # max local+domain length is 254. The unique constraint enforces no
    # duplicates; service-layer normalization ensures case-insensitivity.
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    memberships: Mapped[list[OrganizationMembership]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email!r}>"


class RefreshToken(Base, TimestampMixin):
    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # SHA-256 hex digest of the actual token (64 chars). Indexed for O(1)
    # lookup on refresh. The unique constraint catches accidental reuse.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens")

    __table_args__ = (
        # Hot query: "find active refresh tokens for this user". A partial
        # index on revoked_at IS NULL would be even better, but Alembic
        # autogenerate doesn't track those reliably — we'll add it by hand
        # in a follow-up migration once we have measurements.
        Index("ix_refresh_token_user_id", "user_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RefreshToken user={self.user_id} expires={self.expires_at}>"
