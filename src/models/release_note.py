"""Release note model - version releases with their notes.

Mirrors the GitHub Releases concept for repositories tracked by PyPRLedger:

* one release per ``(project_key, repository_slug, tag_name)``
* a release is either a ``draft`` or ``published``
* ``is_prerelease`` versions are never advertised as the latest release

Git providers are integrated read-only, so the version release itself is managed
here (tag name, notes, pre-release flag, publish state) instead of pushing to
Bitbucket / GitHub.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.utils.timezone import get_current_time


class ReleaseNoteStatus:
    """Allowed release states."""

    DRAFT = "draft"
    PUBLISHED = "published"

    VALUES = (DRAFT, PUBLISHED)


class ReleaseNote(Base):
    """A released (or drafted) version of a repository with its notes."""

    __tablename__ = "release_note"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)

    # Business keys - the project/repository the version belongs to
    project_key: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("project.project_key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # Version data
    tag_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Git tag / version identifier"
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Release title")
    body: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="Release notes (markdown)"
    )
    previous_tag: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Previous version used to generate the notes"
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=ReleaseNoteStatus.DRAFT,
        server_default=ReleaseNoteStatus.DRAFT,
        comment="draft or published",
    )
    is_prerelease: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0", comment="Pre-release flag"
    )

    # Who released it (auth user username, snapshot at publish time)
    author: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Provider side release (GitHub Enterprise), set when pushed or imported
    external_provider: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="Provider holding the published release"
    )
    external_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Provider side release id"
    )
    external_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="Provider side release url"
    )

    # Timestamps
    published_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Set when the release is published"
    )
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=get_current_time
    )
    updated_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=get_current_time, onupdate=get_current_time
    )

    __table_args__ = (
        Index(
            "uk_release_note_tag",
            "project_key",
            "repository_slug",
            "tag_name",
            unique=True,
        ),
        Index(
            "idx_release_note_repo_status",
            "project_key",
            "repository_slug",
            "status",
            "published_date",
        ),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "project_key": self.project_key,
            "repository_slug": self.repository_slug,
            "tag_name": self.tag_name,
            "name": self.name,
            "body": self.body,
            "previous_tag": self.previous_tag,
            "status": self.status,
            "is_prerelease": self.is_prerelease,
            "author": self.author,
            "external_provider": self.external_provider,
            "external_id": self.external_id,
            "external_url": self.external_url,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "updated_date": self.updated_date.isoformat() if self.updated_date else None,
        }

    def __repr__(self) -> str:
        return (
            f"<ReleaseNote(id={self.id}, {self.project_key}/{self.repository_slug}, "
            f"tag_name='{self.tag_name}', status='{self.status}')>"
        )
