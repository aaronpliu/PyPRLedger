from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


if TYPE_CHECKING:
    from src.models.project import Project
    from src.models.repository import Repository
    from src.models.user import User


class PullRequestReviewBase(Base):
    """Base review information stored once per PR commit and file."""

    __tablename__ = "pull_request_review_base"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)

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

    source_branch: Mapped[str] = mapped_column(String(64), nullable=False)
    target_branch: Mapped[str] = mapped_column(String(64), nullable=False)
    git_code_diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_suggestions: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    pull_request_status: Mapped[str] = mapped_column(String(32), nullable=False)
    pull_request_user: Mapped[str] = mapped_column(
        String(64), ForeignKey("user.username", ondelete="CASCADE"), nullable=False, index=True
    )
    review_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        name="metadata",
    )

    # AI Review Identifier - unique ID for tracking AI suggestions per PR
    ai_review_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    project: Mapped[Project] = relationship(
        foreign_keys=[project_key], back_populates="pull_request_reviews"
    )
    repository: Mapped[Repository] = relationship(
        foreign_keys=[repository_slug], back_populates="pull_request_reviews"
    )
    pull_request_user_rel: Mapped[User] = relationship(
        foreign_keys=[pull_request_user], back_populates="authored_reviews"
    )
    assignments: Mapped[list[PullRequestReviewAssignment]] = relationship(
        back_populates="review_base", cascade="all, delete-orphan"
    )

    created_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )

    updated_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

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
            f"<PullRequestReviewBase(id={self.id}, pull_request_id='{self.pull_request_id}', "
            f"commit_id='{self.pull_request_commit_id}', file='{self.source_filename}')>"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pull_request_id": self.pull_request_id,
            "pull_request_commit_id": self.pull_request_commit_id,
            "project_key": self.project_key,
            "repository_slug": self.repository_slug,
            "pull_request_user": self.pull_request_user,
            "source_branch": self.source_branch,
            "target_branch": self.target_branch,
            "git_code_diff": self.git_code_diff,
            "source_filename": self.source_filename,
            "ai_suggestions": self.ai_suggestions,
            "pull_request_status": self.pull_request_status,
            "metadata": self.review_metadata,
            "ai_review_id": self.ai_review_id,
            "created_date": (
                self.created_date.isoformat()
                if isinstance(self.created_date, datetime)
                else self.created_date
            )
            if self.created_date
            else None,
            "updated_date": (
                self.updated_date.isoformat()
                if isinstance(self.updated_date, datetime)
                else self.updated_date
            )
            if self.updated_date
            else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PullRequestReviewBase:
        return cls(
            pull_request_id=data.get("pull_request_id"),
            pull_request_commit_id=data.get("pull_request_commit_id"),
            project_key=data.get("project_key"),
            repository_slug=data.get("repository_slug"),
            pull_request_user=data.get("pull_request_user"),
            source_branch=data.get("source_branch"),
            target_branch=data.get("target_branch"),
            git_code_diff=data.get("git_code_diff"),
            source_filename=data.get("source_filename"),
            ai_suggestions=data.get("ai_suggestions"),
            pull_request_status=data.get("pull_request_status"),
            review_metadata=data.get("metadata"),
            ai_review_id=data.get("ai_review_id"),
        )

    def update(self, data: dict[str, Any]) -> None:
        updatable_fields = [
            "git_code_diff",
            "source_filename",
            "ai_suggestions",
            "pull_request_status",
            "review_metadata",
            "source_branch",
            "target_branch",
            "pull_request_user",
        ]

        for key, value in data.items():
            if key in updatable_fields and hasattr(self, key):
                setattr(self, key, value)

    @property
    def is_open(self) -> bool:
        return self.pull_request_status == "open"

    @property
    def is_merged(self) -> bool:
        return self.pull_request_status == "merged"

    @property
    def is_closed(self) -> bool:
        return self.pull_request_status == "closed"

    @property
    def is_draft(self) -> bool:
        return self.pull_request_status == "draft"

    def can_transition_to(self, new_status: str) -> bool:
        valid_transitions = {
            "draft": ["open", "closed"],
            "open": ["merged", "closed"],
            "merged": [],
            "closed": ["open"],
        }

        return new_status in valid_transitions.get(self.pull_request_status, [])


class PullRequestReviewAssignment(Base):
    """Reviewer-specific assignment data for a base review."""

    __tablename__ = "pull_request_review_assignment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)

    review_base_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("pull_request_review_base.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user.username", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_by: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("user.username", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Username of the user who assigned this review task",
    )
    assigned_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="Timestamp when the review was assigned",
    )
    assignment_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default="pending",
        comment="Status: pending, assigned, in_progress, completed",
    )
    reviewer_comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    review_base: Mapped[PullRequestReviewBase] = relationship(back_populates="assignments")
    reviewer_rel: Mapped[User] = relationship(
        foreign_keys=[reviewer], back_populates="review_assignments"
    )
    assigned_by_rel: Mapped[User | None] = relationship(
        foreign_keys=[assigned_by], back_populates="assigned_reviews"
    )

    created_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )

    updated_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

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
        return {
            "id": self.id,
            "review_base_id": self.review_base_id,
            "reviewer": self.reviewer,
            "assigned_by": self.assigned_by,
            "assigned_date": (
                self.assigned_date.isoformat()
                if isinstance(self.assigned_date, datetime)
                else self.assigned_date
            )
            if self.assigned_date
            else None,
            "assignment_status": self.assignment_status,
            "reviewer_comments": self.reviewer_comments,
            "created_date": (
                self.created_date.isoformat()
                if isinstance(self.created_date, datetime)
                else self.created_date
            )
            if self.created_date
            else None,
            "updated_date": (
                self.updated_date.isoformat()
                if isinstance(self.updated_date, datetime)
                else self.updated_date
            )
            if self.updated_date
            else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PullRequestReviewAssignment:
        return cls(
            review_base_id=data.get("review_base_id"),
            reviewer=data.get("reviewer"),
            assigned_by=data.get("assigned_by"),
            assigned_date=data.get("assigned_date"),
            assignment_status=data.get("assignment_status", "pending"),
            reviewer_comments=data.get("reviewer_comments"),
        )

    def update(self, data: dict[str, Any]) -> None:
        updatable_fields = [
            "reviewer",
            "assigned_by",
            "assigned_date",
            "assignment_status",
            "reviewer_comments",
        ]

        for key, value in data.items():
            if key in updatable_fields and hasattr(self, key):
                setattr(self, key, value)

    def to_full_dict(self) -> dict[str, Any]:
        base_dict = self.review_base.to_dict() if self.review_base else {}
        return {**base_dict, **self.to_dict()}


class PullRequestScore(Base):
    """Pull request score model representing the pull_request_score table in the database

    Supports:
    1. Multiple reviewers per pull request (each reviewer has one score per target)
    2. File-level scoring (score specific files)
    3. PR-level scoring (score entire PR when source_filename is NULL)
    4. Unique constraint ensures one score per reviewer per review target
    """

    __tablename__ = "pull_request_score"

    # Primary key - auto-generated by database
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)

    # === Composite Business Key (Unique Constraint) ===
    pull_request_id = Column(String(100), nullable=False, index=True)  # Reduced from 255
    pull_request_commit_id = Column(String(100), nullable=False)  # Reduced from 255
    project_key = Column(String(50), ForeignKey("project.project_key"), nullable=False, index=True)
    repository_slug = Column(
        String(128), ForeignKey("repository.repository_slug"), nullable=False, index=True
    )  # Match repository model
    source_filename = Column(
        String(255), nullable=True
    )  # Reduced from 500, NULL for PR-level scores
    reviewer = Column(
        String(64), ForeignKey("user.username"), nullable=False, index=True
    )  # Match user model

    # Score information
    score: Mapped[float] = mapped_column(Float(precision=2), nullable=False)
    score_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Soft delete and audit fields
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1", index=True
    )
    deleted_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    project: Mapped[Project] = relationship(foreign_keys=[project_key], back_populates="scores")
    repository: Mapped[Repository] = relationship(
        foreign_keys=[repository_slug], back_populates="scores"
    )
    reviewer_rel: Mapped[User] = relationship(
        foreign_keys=[reviewer], back_populates="scores_given"
    )

    # === Constraints & Indexes ===
    __table_args__ = (
        # One score per reviewer per review target (file or PR)
        # Using shorter column names to fit MySQL's 3072 byte limit
        UniqueConstraint(
            "pull_request_id",
            "project_key",
            "repository_slug",
            "source_filename",  # Can be NULL
            "reviewer",
            name="uq_score_reviewer_target",
        ),
        # Indexes for common query patterns
        Index("idx_score_by_pr", "pull_request_id", "project_key", "repository_slug"),
        Index("idx_score_by_file", "pull_request_id", "source_filename"),
        Index("idx_score_by_reviewer", "reviewer", "created_date"),
        Index(
            "idx_score_full_lookup",
            "project_key",
            "repository_slug",
            "pull_request_id",
            "source_filename",
        ),
    )

    def __repr__(self) -> str:
        """String representation of the pull request score"""
        target = f"file '{self.source_filename}'" if self.source_filename else "PR"
        return (
            f"<PullRequestScore(id={self.id}, pull_request_id='{self.pull_request_id}', "
            f"target={target}, reviewer='{self.reviewer}', score={self.score})>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert pull request score model to dictionary"""
        return {
            "id": self.id,
            "pull_request_id": self.pull_request_id,
            "pull_request_commit_id": self.pull_request_commit_id,
            "project_key": self.project_key,
            "repository_slug": self.repository_slug,
            "source_filename": self.source_filename,
            "reviewer": self.reviewer,
            "score": self.score,
            "score_description": self.score_description,
            "reviewer_comments": self.reviewer_comments,
            "active": self.active,
            "deleted_by": self.deleted_by,
            "deleted_at": (
                self.deleted_at.isoformat()
                if isinstance(self.deleted_at, datetime) and self.deleted_at
                else None
            ),
            "created_date": (
                self.created_date.isoformat()
                if isinstance(self.created_date, datetime)
                else self.created_date
            )
            if self.created_date
            else None,
            "updated_date": (
                self.updated_date.isoformat()
                if isinstance(self.updated_date, datetime)
                else self.updated_date
            )
            if self.updated_date
            else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PullRequestScore:
        """Create pull request score instance from dictionary"""
        return cls(
            pull_request_id=data.get("pull_request_id"),
            pull_request_commit_id=data.get("pull_request_commit_id"),
            project_key=data.get("project_key"),
            repository_slug=data.get("repository_slug"),
            source_filename=data.get("source_filename"),
            reviewer=data.get("reviewer"),
            score=data.get("score"),
            score_description=data.get("score_description"),
            reviewer_comments=data.get("reviewer_comments"),
        )

    def update(self, data: dict[str, Any]) -> None:
        """Update pull request score attributes from dictionary"""
        updatable_fields = ["score", "score_description", "reviewer_comments"]

        for key, value in data.items():
            if key in updatable_fields and hasattr(self, key):
                setattr(self, key, value)
