from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


if TYPE_CHECKING:
    from src.models.project import Project


class ProjectRegistry(Base):
    """Project registry model for mapping projects to applications

    This table maintains the relationship between (project_key, repository_slug) pairs
    and their corresponding application names. The app_name is a virtual field that
    is resolved at query time, not stored in the pull_request_review table.

    Supports:
    1. Logical grouping of projects into applications
    2. Auto-registration with default 'Unknown' app
    3. Admin-managed application boundaries
    4. Multiple projects per application
    """

    __tablename__ = "project_registry"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)

    # Application name - logical grouping
    app_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Business keys for project identification
    project_key: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("project.project_key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    repository_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # Optional description
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_date: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), nullable=False
    )

    updated_date: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        foreign_keys=[project_key], back_populates="registry_entries"
    )

    # Unique constraints and indexes
    __table_args__ = (
        # Each (project_key, repository_slug) maps to exactly one app
        Index(
            "uk_project_repo_unique",
            "project_key",
            "repository_slug",
            unique=True,
        ),
        # Index for efficient app-based queries
        Index(
            "idx_app_project_repo",
            "app_name",
            "project_key",
            "repository_slug",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ProjectRegistry(id={self.id}, app_name='{self.app_name}', "
            f"project_key='{self.project_key}', repository_slug='{self.repository_slug}')>"
        )
