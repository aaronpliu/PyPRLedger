"""Pull request review models with multi-reviewer support

This module defines the base-assignment pattern for managing multiple reviewers:
- PullRequestReviewBase: Stores PR base information (once per PR+commit+file)
- PullRequestReviewAssignment: Stores reviewer assignments (one per reviewer)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


if TYPE_CHECKING:
    from src.models.project import Project
    from src.models.repository import Repository
    from src.models.user import User


class PullRequestReviewBase(Base):
    """Base review information - stores PR data once per commit+file combination

    This table contains the immutable PR information that is shared across all reviewers.
    Each unique combination of (commit_id, project, repo, file) has exactly one record.
    """

    __tablename__ = "pull_request_review_base"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Business keys (composite unique constraint)
    pull_request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    pull_request_commit_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    project_key: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("project.project_key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_slug: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("repository.repository_slug", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # PR base information (stored once, shared by all reviewers)
    source_branch: Mapped[str] = mapped_column(String(64), nullable=False)
    target_branch: Mapped[str] = mapped_column(String(64), nullable=False)
    git_code_diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_suggestions: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    pull_request_status: Mapped[str] = mapped_column(String(32), nullable=False)
    review_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, name="metadata"
    )

    # Timestamps
    created_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    project: Mapped[Project] = relationship(foreign_keys=[project_key])
    repository: Mapped[Repository] = relationship(foreign_keys=[repository_slug])
    assignments: Mapped[list[PullRequestReviewAssignment]] = relationship(
        back_populates="review_base", cascade="all, delete-orphan"
    )

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint(
            "pull_request_commit_id",
            "project_key",
            "repository_slug",
            "source_filename",
            name="uq_pr_commit_file",
        ),
        Index("idx_base_pr_commit", "pull_request_commit_id", "project_key", "repository_slug"),
    )

    def __repr__(self) -> str:
        return (
            f"<PullRequestReviewBase(id={self.id}, pr='{self.pull_request_id}', "
            f"commit='{self.pull_request_commit_id}', file='{self.source_filename}')>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "pull_request_id": self.pull_request_id,
            "pull_request_commit_id": self.pull_request_commit_id,
            "project_key": self.project_key,
            "repository_slug": self.repository_slug,
            "source_filename": self.source_filename,
            "source_branch": self.source_branch,
            "target_branch": self.target_branch,
            "git_code_diff": self.git_code_diff,
            "ai_suggestions": self.ai_suggestions,
            "pull_request_status": self.pull_request_status,
            "metadata": self.review_metadata,
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "updated_date": self.updated_date.isoformat() if self.updated_date else None,
        }


class PullRequestReviewAssignment(Base):
    """Reviewer assignment - tracks which reviewers are assigned to a review

    Each reviewer gets one assignment record per base review.
    This allows independent tracking of assignment status and reviewer comments.
    """

    __tablename__ = "pull_request_review_assignment"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to base review
    review_base_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("pull_request_review_base.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Reviewer information
    reviewer: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user.username", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Assignment tracking
    assigned_by: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("user.username", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Username of the user who assigned this review task",
    )
    assigned_date: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="Timestamp when the review was assigned"
    )
    assignment_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default="pending",
        comment="Status: pending, assigned, in_progress, completed",
    )

    # Reviewer-specific comments (each reviewer has their own)
    reviewer_comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    review_base: Mapped[PullRequestReviewBase] = relationship(back_populates="assignments")
    reviewer_rel: Mapped[User] = relationship(
        foreign_keys=[reviewer], back_populates="review_assignments"
    )
    assigned_by_rel: Mapped[User] = relationship(
        foreign_keys=[assigned_by], remote_side="User.username"
    )

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("review_base_id", "reviewer", name="uq_base_reviewer"),
        Index("idx_assignment_by_reviewer", "reviewer", "assignment_status"),
        Index("idx_assignment_by_base", "review_base_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<PullRequestReviewAssignment(id={self.id}, reviewer='{self.reviewer}', "
            f"status='{self.assignment_status}')>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "review_base_id": self.review_base_id,
            "reviewer": self.reviewer,
            "assigned_by": self.assigned_by,
            "assigned_date": self.assigned_date.isoformat() if self.assigned_date else None,
            "assignment_status": self.assignment_status,
            "reviewer_comments": self.reviewer_comments,
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "updated_date": self.updated_date.isoformat() if self.updated_date else None,
        }

    def to_full_dict(self) -> dict[str, Any]:
        """Convert to dictionary including base review information"""
        base_dict = self.review_base.to_dict() if self.review_base else {}
        assignment_dict = self.to_dict()
        return {**base_dict, **assignment_dict}
