"""add active and deletion tracking fields to pull_request_score

Revision ID: 005
Revises: 004
Create Date: 2026-04-05 22:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add soft delete and audit fields to pull_request_score table"""

    # Add active field with default True
    op.add_column(
        "pull_request_score", sa.Column("active", sa.Boolean(), nullable=False, server_default="1")
    )

    # Add deleted_by field (nullable, only set when deleted)
    op.add_column("pull_request_score", sa.Column("deleted_by", sa.String(64), nullable=True))

    # Add deleted_at field (nullable, only set when deleted)
    op.add_column(
        "pull_request_score", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )

    # Create index on active for efficient filtering
    op.create_index("idx_score_active", "pull_request_score", ["active"])

    # Create composite index for common query pattern
    op.create_index("idx_score_active_reviewer", "pull_request_score", ["active", "reviewer"])


def downgrade() -> None:
    """Remove soft delete and audit fields from pull_request_score table"""

    # Drop indexes
    op.drop_index("idx_score_active_reviewer", "pull_request_score")
    op.drop_index("idx_score_active", "pull_request_score")

    # Drop columns
    op.drop_column("pull_request_score", "deleted_at")
    op.drop_column("pull_request_score", "deleted_by")
    op.drop_column("pull_request_score", "active")
