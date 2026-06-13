"""Auto-assignment rule model for pull request reviews"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.core.database import Base
from src.utils.timezone import get_current_time


class PullRequestReviewAutoAssignmentRule(Base):
    """
    Auto-assignment rule for pull request reviews.

    When a review is created without an explicit reviewer, the auto-assignment
    engine evaluates all active rules in priority order. The first matching
    rule's reviewers are automatically assigned to the review.

    Conditions are stored as JSON and support exact match (list of values),
    prefix match (source_branch_prefix), and status match.
    """

    __tablename__ = "pull_request_review_auto_assignment_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Identity
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Priority — lower number = evaluated first
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, index=True)

    # Match conditions as JSON
    # Example:
    #   {"project_key": ["PROJ-A"], "repository_slug": ["frontend"]}
    conditions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Reviewers to assign (list of git usernames)
    # Example: ["alice", "bob"]
    assign_to: Mapped[list] = mapped_column(JSON, nullable=False)

    # Max reviewers from the list to assign (0 = all)
    max_assignments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Temporal validity
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # Audit
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)

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

    # Index for the common query pattern:
    # "get all active, non-expired rules ordered by priority"
    __table_args__ = (
        Index(
            "idx_auto_assign_rule_active_priority",
            "is_active",
            "priority",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PullRequestReviewAutoAssignmentRule(id={self.id}, "
            f"name='{self.name}', priority={self.priority})>"
        )
