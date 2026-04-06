from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


if TYPE_CHECKING:
    from src.models.audit_log import AuditLog
    from src.models.rbac import UserRoleAssignment
    from src.models.user import User


class AuthUser(Base):
    """Authentication user model for system login and authorization

    This table stores authentication credentials and is separate from the
    business user table (which syncs from Bitbucket). They can be linked
    via the user_id foreign key.
    """

    __tablename__ = "auth_user"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Authentication fields
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)

    # Link to Bitbucket user (optional, can be auto-associated by username)
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Reference to Bitbucket user ID (auto-linked by username)",
    )

    # Status fields
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    bitbucket_user: Mapped[User | None] = relationship(
        "User", back_populates="auth_user", foreign_keys=[user_id]
    )
    role_assignments: Mapped[list[UserRoleAssignment]] = relationship(
        "UserRoleAssignment",
        back_populates="auth_user",
        cascade="all, delete-orphan",
        foreign_keys="UserRoleAssignment.auth_user_id",
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        "AuditLog",
        back_populates="auth_user",
        cascade="all, delete-orphan",
        foreign_keys="AuditLog.auth_user_id",
    )

    def __repr__(self) -> str:
        return f"<AuthUser(id={self.id}, username='{self.username}')>"

    def to_dict(self) -> dict:
        """Convert auth user to dictionary"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "user_id": self.user_id,
            "is_active": self.is_active,
            "last_login_at": (self.last_login_at.isoformat() if self.last_login_at else None),
            "created_at": self.created_at.isoformat(),
        }
