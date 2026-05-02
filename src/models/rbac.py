from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.core.database import Base
from src.utils.timezone import get_current_time, utc_to_local


if TYPE_CHECKING:
    from src.models.auth_user import AuthUser
    from src.models.role import Role


class UserRoleAssignment(Base):
    """User role assignment model for RBAC system

    Links users to roles with specific resource scope (global/project/repository).
    This enables hierarchical permission management.
    """

    __tablename__ = "user_role_assignment"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    auth_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("auth_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("role.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Resource scope
    resource_type: Mapped[str] = mapped_column(
        Enum("global", "project", "repository", name="resource_type_enum"),
        nullable=False,
        default="global",
        comment="Scope of this role assignment",
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Resource identifier (project_key or repository_slug, NULL for global)",
    )

    # Metadata
    granted_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who granted this role",
    )
    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="Start time for role validity (for delegation or scheduled access)",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="Optional expiration time for temporary permissions",
    )

    # Delegation fields
    is_delegated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this assignment is delegated from another user",
    )
    delegator_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who delegated this role (NULL if not delegated)",
    )
    delegation_status: Mapped[str | None] = mapped_column(
        Enum("active", "expired", "revoked", "pending", name="delegation_status_enum"),
        nullable=True,
        comment="Status of delegation (only for delegated roles)",
    )
    delegation_scope: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Specific permissions being delegated (subset of delegator's permissions)",
    )
    delegation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason or description for this delegation",
    )
    revoked_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who revoked this delegation",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="Time when delegation was revoked",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=get_current_time
    )

    # Relationships
    auth_user: Mapped[AuthUser] = relationship(
        "AuthUser",
        back_populates="role_assignments",
        foreign_keys=[auth_user_id],
    )
    role: Mapped[Role] = relationship("Role", back_populates="user_assignments")
    granter: Mapped[AuthUser | None] = relationship("AuthUser", foreign_keys=[granted_by])
    delegator: Mapped[AuthUser | None] = relationship("AuthUser", foreign_keys=[delegator_id])
    revoker: Mapped[AuthUser | None] = relationship("AuthUser", foreign_keys=[revoked_by])

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "auth_user_id",
            "role_id",
            "resource_type",
            "resource_id",
            name="unique_user_role_resource",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<UserRoleAssignment(user_id={self.auth_user_id}, "
            f"role_id={self.role_id}, resource={self.resource_type}:{self.resource_id})>"
        )

    def to_dict(self) -> dict:
        """Convert assignment to dictionary"""
        return {
            "id": self.id,
            "auth_user_id": self.auth_user_id,
            "role_id": self.role_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "granted_by": self.granted_by,
            "starts_at": utc_to_local(self.starts_at).isoformat() if self.starts_at else None,
            "expires_at": utc_to_local(self.expires_at).isoformat() if self.expires_at else None,
            "is_delegated": self.is_delegated,
            "delegator_id": self.delegator_id,
            "delegation_status": self.delegation_status,
            "delegation_scope": self.delegation_scope,
            "delegation_reason": self.delegation_reason,
            "revoked_by": self.revoked_by,
            "revoked_at": utc_to_local(self.revoked_at).isoformat() if self.revoked_at else None,
            "created_at": utc_to_local(self.created_at).isoformat(),
        }
