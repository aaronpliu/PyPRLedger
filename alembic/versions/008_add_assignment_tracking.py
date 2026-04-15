"""add assignment tracking and fix unique constraint for nullable reviewer

Revision ID: 008_add_assignment_tracking
Revises: 007_add_assign_permission
Create Date: 2026-04-10

Support two scenarios:
1. Webhook creates review with reviewer=NULL (pending assignment)
2. Admin assigns task by setting reviewer to specific user
Both scenarios prevent duplicate records.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Modify pull_request_review table to support nullable reviewer with proper uniqueness"""

    # Step 1: Drop existing unique index that includes reviewer
    op.drop_index("idx_unique_review_identifier", table_name="pull_request_review")

    # Step 2: Make reviewer column nullable
    op.alter_column(
        "pull_request_review",
        "reviewer",
        existing_type=sa.String(64),
        nullable=True,
        existing_comment=None,
    )

    # Step 3: Create new unique index
    # MySQL treats multiple NULL values as distinct in unique indexes
    # So we need application-level logic to prevent duplicates
    op.create_index(
        "idx_unique_review_identifier",
        "pull_request_review",
        ["pull_request_commit_id", "project_key", "repository_slug", "source_filename", "reviewer"],
        unique=True,
    )

    # Step 4: Add assignment tracking fields
    op.add_column(
        "pull_request_review",
        sa.Column(
            "assigned_by",
            sa.String(64),
            sa.ForeignKey("user.username", ondelete="SET NULL"),
            nullable=True,
            comment="Username of the user who assigned this review task",
        ),
    )

    op.add_column(
        "pull_request_review",
        sa.Column(
            "assigned_date",
            sa.DateTime(),
            nullable=True,
            comment="Timestamp when the review was assigned",
        ),
    )

    op.add_column(
        "pull_request_review",
        sa.Column(
            "assignment_status",
            sa.String(32),
            nullable=False,
            server_default="auto_created",
            comment="Assignment status: auto_created (webhook), assigned (manual), completed",
        ),
    )

    # Step 5: Create indexes for assignment tracking
    op.create_index(
        "idx_assignment_status",
        "pull_request_review",
        ["assignment_status"],
    )

    op.create_index(
        "idx_assigned_by",
        "pull_request_review",
        ["assigned_by"],
    )


def downgrade() -> None:
    """Revert changes"""
    op.drop_index("idx_assigned_by", table_name="pull_request_review")
    op.drop_index("idx_assignment_status", table_name="pull_request_review")
    op.drop_column("pull_request_review", "assignment_status")
    op.drop_column("pull_request_review", "assigned_date")
    op.drop_column("pull_request_review", "assigned_by")
    op.drop_index("idx_unique_review_identifier", table_name="pull_request_review")

    # Restore original unique index
    op.create_index(
        "idx_unique_review_identifier",
        "pull_request_review",
        ["pull_request_commit_id", "project_key", "repository_slug", "source_filename", "reviewer"],
    )

    # Make reviewer NOT NULL again
    op.alter_column(
        "pull_request_review",
        "reviewer",
        existing_type=sa.String(64),
        nullable=False,
    )
