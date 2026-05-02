"""create review raw table

Revision ID: 017
Revises: 016
Create Date: 2026-05-02 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "017"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create pull_request_review_raw table for audit trail and validation"""
    op.create_table(
        "pull_request_review_raw",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column(
            "review_base_id",
            sa.Integer(),
            sa.ForeignKey("pull_request_review_base.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column(
            "created_date",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "processed_date",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Create indexes for performance
    op.create_index("idx_raw_status", "pull_request_review_raw", ["status"])
    op.create_index("idx_raw_created", "pull_request_review_raw", ["created_date"])
    op.create_index("idx_raw_review_base_id", "pull_request_review_raw", ["review_base_id"])


def downgrade() -> None:
    """Drop pull_request_review_raw table"""
    op.drop_index("idx_raw_review_base_id", table_name="pull_request_review_raw")
    op.drop_index("idx_raw_created", table_name="pull_request_review_raw")
    op.drop_index("idx_raw_status", table_name="pull_request_review_raw")
    op.drop_table("pull_request_review_raw")
