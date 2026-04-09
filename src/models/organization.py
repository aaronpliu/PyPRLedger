from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


if TYPE_CHECKING:
    pass


class OrganizationGroup(Base):
    """Organization group model for hierarchical permission management

    Supports Group -> Team hierarchy for organizing users and managing permissions.
    Groups can be nested (parent_id references another group).
    """

    __tablename__ = "organization_group"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Group information
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    # Self-referencing foreign key for nested groups
    parent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("organization_group.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Group type
    type: Mapped[str] = mapped_column(
        Enum("group", "team", name="org_group_type"),
        nullable=False,
        default="group",
    )

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
    parent: Mapped[OrganizationGroup | None] = relationship(
        "OrganizationGroup", remote_side=[id], backref="children"
    )

    def __repr__(self) -> str:
        return f"<OrganizationGroup(id={self.id}, name='{self.name}', type='{self.type}')>"

    def to_dict(self) -> dict:
        """Convert organization group to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "type": self.type,
            "created_at": self.created_at.isoformat(),
        }
