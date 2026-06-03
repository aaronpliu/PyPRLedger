"""Create user_pinned_reviews table for private per-user pin/flag system

Revision ID: 024
Revises: 023
Create Date: 2026-05-30

This migration creates the user_pinned_reviews table, allowing each user to
privately mark reviews as noteworthy/pinned for quick lookup.
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create user_pinned_reviews table"""

    op.create_table(
        "user_pinned_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_date",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_user.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["pull_request_review_base.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "review_id", name="uq_user_review"),
    )

    # Add index for common query patterns
    op.create_index(
        "idx_user_pinned_user",
        "user_pinned_reviews",
        ["user_id"],
    )
    op.create_index(
        "idx_user_pinned_review",
        "user_pinned_reviews",
        ["review_id"],
    )
    op.create_index(
        "idx_user_pinned_user_review",
        "user_pinned_reviews",
        ["user_id", "review_id"],
    )


def downgrade() -> None:
    """Drop user_pinned_reviews table"""

    op.drop_index("idx_user_pinned_user_review", table_name="user_pinned_reviews")
    op.drop_index("idx_user_pinned_review", table_name="user_pinned_reviews")
    op.drop_index("idx_user_pinned_user", table_name="user_pinned_reviews")
    op.drop_table("user_pinned_reviews")
