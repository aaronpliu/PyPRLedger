from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.core.database import Base
from src.utils.timezone import get_current_time, utc_to_local


if TYPE_CHECKING:
    from src.models.rbac import UserRoleAssignment


class Role(Base):
    """Role model for RBAC permission system

    Defines roles with specific permissions that can be assigned to users.
    Predefined roles: viewer, reviewer, review_admin, system_admin
    """

    __tablename__ = "role"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Role identification
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Permissions stored as JSON
    # Example: {"reviews": ["read", "create"], "scores": ["read", "create", "update"]}
    permissions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=get_current_time
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=get_current_time,
        onupdate=get_current_time,
    )

    # Relationships
    user_assignments: Mapped[list[UserRoleAssignment]] = relationship(
        "UserRoleAssignment", back_populates="role", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name='{self.name}')>"

    def to_dict(self) -> dict:
        """Convert role to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "permissions": self.permissions,
            "created_at": utc_to_local(self.created_at).isoformat(),
        }
