"""Refactor score to separate table

Revision ID: 004
Revises: 003
Create Date: 2024-01-15

"""

import contextlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Step 1: Add missing index on repository.repository_slug for FK constraint
    # Check if index exists first to avoid duplicate key error
    with contextlib.suppress(Exception):
        op.create_index("idx_repository_slug", "repository", ["repository_slug"])

    # Step 2: Drop old columns from pull_request_review (if they exist)
    # Use if_exists=True to handle cases where columns may have been removed manually
    # Note: MySQL doesn't support DROP COLUMN IF EXISTS, so we need to check column existence first
    from sqlalchemy import inspect

    # Get the database inspector to check column existence
    inspector = inspect(op.get_bind())
    columns = [col["name"] for col in inspector.get_columns("pull_request_review")]

    if "score" in columns:
        op.drop_column("pull_request_review", "score")
    if "reviewed_date" in columns:
        op.drop_column("pull_request_review", "reviewed_date")
    if "is_latest_review" in columns:
        op.drop_column("pull_request_review", "is_latest_review")
    if "review_iteration" in columns:
        op.drop_column("pull_request_review", "review_iteration")

    # Step 3: Create new pull_request_score table with shorter column types
    op.create_table(
        "pull_request_score",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pull_request_id", sa.String(100), nullable=False),  # Reduced from 255
        sa.Column("pull_request_commit_id", sa.String(100), nullable=False),  # Reduced from 255
        sa.Column("project_key", sa.String(50), nullable=False),
        sa.Column("repository_slug", sa.String(128), nullable=False),  # Match repository model
        sa.Column("source_filename", sa.String(255), nullable=True),  # Reduced from 500
        sa.Column("reviewer", sa.String(64), nullable=False),  # Match user model
        sa.Column("score", sa.Float(precision=2), nullable=False),
        sa.Column("score_description", sa.Text(), nullable=True),
        sa.Column("reviewer_comments", sa.Text(), nullable=True),
        sa.Column("created_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_date", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_key"], ["project.project_key"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["repository_slug"], ["repository.repository_slug"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["reviewer"], ["user.username"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Step 4: Create indexes (removed the oversized unique index, using UniqueConstraint in model instead)
    op.create_index(
        "idx_score_by_pr",
        "pull_request_score",
        ["pull_request_id", "project_key", "repository_slug"],
    )
    op.create_index(
        "idx_score_by_file", "pull_request_score", ["pull_request_id", "source_filename"]
    )
    op.create_index("idx_score_by_reviewer", "pull_request_score", ["reviewer", "created_date"])
    op.create_index(
        "idx_score_full_lookup",
        "pull_request_score",
        ["project_key", "repository_slug", "pull_request_id", "source_filename"],
    )


def downgrade() -> None:
    # Reverse the migration
    op.drop_table("pull_request_score")

    # Remove the index we added for FK constraint
    with contextlib.suppress(Exception):
        op.drop_index("idx_repository_slug", "repository")

    # Recreate old columns (empty)
    from sqlalchemy import inspect

    # Check if columns already exist before adding them
    inspector = inspect(op.get_bind())
    columns = [col["name"] for col in inspector.get_columns("pull_request_review")]

    if "score" not in columns:
        op.add_column("pull_request_review", sa.Column("score", sa.Float(), nullable=True))
    if "reviewed_date" not in columns:
        op.add_column(
            "pull_request_review", sa.Column("reviewed_date", sa.DateTime(), nullable=True)
        )
    if "is_latest_review" not in columns:
        op.add_column(
            "pull_request_review", sa.Column("is_latest_review", sa.Boolean(), nullable=True)
        )
    if "review_iteration" not in columns:
        op.add_column(
            "pull_request_review", sa.Column("review_iteration", sa.Integer(), nullable=True)
        )
