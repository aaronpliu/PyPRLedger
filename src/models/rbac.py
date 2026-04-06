from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


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
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="Optional expiration time for temporary permissions",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )

    # Relationships
    auth_user: Mapped[AuthUser] = relationship(
        "AuthUser",
        back_populates="role_assignments",
        foreign_keys=[auth_user_id],
    )
    role: Mapped[Role] = relationship("Role", back_populates="user_assignments")
    granter: Mapped[AuthUser | None] = relationship("AuthUser", foreign_keys=[granted_by])

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
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat(),
        }
