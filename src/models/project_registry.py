from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.core.git_provider import GitProvider
from src.utils.timezone import get_current_time


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
    5. Per-project Git provider tracking
    6. Telling an application from a package, which are registered here for two
       different reasons
    """

    PROVIDER_BITBUCKET_SERVER = GitProvider.BITBUCKET_SERVER.value
    PROVIDER_BITBUCKET_CLOUD = GitProvider.BITBUCKET_CLOUD.value
    PROVIDER_GITHUB_ENTERPRISE = GitProvider.GITHUB_ENTERPRISE.value
    VALID_PROVIDERS = GitProvider.values()
    DEFAULT_PROVIDER = GitProvider.default().value

    # What a registration is: an application, whose releases the dependency database
    # holds records of, or a package that is only ever a dependency of one. Empty
    # means nobody has said, and a registration nobody has classified is treated as
    # it always was - which is what keeps this an opt-in.
    KIND_APPLICATION = "application"
    KIND_PACKAGE = "package"
    VALID_KINDS = (KIND_APPLICATION, KIND_PACKAGE)

    __tablename__ = "project_registry"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)

    # Application name - logical grouping
    app_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # What the dependency database knows this application as, when that differs
    # from the name above. Empty means the application name is used, so a
    # registration that needs no alias keeps following a rename of it.
    app_alias: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Business keys for project identification
    project_key: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("project.project_key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    repository_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # Git provider for this project (bitbucket_server, github_enterprise)
    git_provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DEFAULT_PROVIDER, server_default=DEFAULT_PROVIDER
    )

    # What this registration is for. The registry serves two purposes - resolving a
    # repository to the application the dependency database knows it by, and
    # resolving a package name back to the repository it lives in - and only the
    # first is something the pages that read an application's releases can use: a
    # package repository has no release records, so offering it as an application is
    # a dead end.
    #
    # Empty means nobody has said, and a registration nobody has classified behaves
    # as it always did - shown everywhere. That is what makes the classification an
    # administrator can make in the registry page an opt-in: applying this column to
    # a registry that fills itself in changes nothing until someone makes a choice.
    registry_kind: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)

    # Optional description
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=get_current_time, nullable=False
    )

    updated_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=get_current_time, onupdate=get_current_time, nullable=False
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
            f"project_key='{self.project_key}', repository_slug='{self.repository_slug}', "
            f"git_provider='{self.git_provider}')>"
        )
