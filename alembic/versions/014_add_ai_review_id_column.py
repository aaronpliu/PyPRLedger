"""Add ai_review_id column for AI review tracking

Revision ID: 014
Revises: 013
Create Date: 2026-04-18

This migration adds a dedicated column to store unique AI review identifiers,
enabling retrieval of previous AI suggestions for feedback loops.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add ai_review_id column with index"""

    # Add column (nullable for backward compatibility)
    op.add_column(
        "pull_request_review_base",
        sa.Column("ai_review_id", sa.String(64), nullable=True),
    )

    # Add index for fast lookups
    op.create_index(
        "idx_ai_review_id",
        "pull_request_review_base",
        ["ai_review_id"],
    )


def downgrade() -> None:
    """Remove ai_review_id column and index"""
    op.drop_index("idx_ai_review_id", table_name="pull_request_review_base")
    op.drop_column("pull_request_review_base", "ai_review_id")
