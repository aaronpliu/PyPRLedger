"""Create pull_request_review_association table for linking related reviews

Revision ID: 025
Revises: 024
Create Date: 2026-05-30

This migration creates the pull_request_review_association table, allowing bidirectional
many-to-many associations between reviews (e.g., original review to follow-up PR review).
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create pull_request_review_association table"""

    op.create_table(
        "pull_request_review_association",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("associated_review_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_date",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["pull_request_review_base.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["associated_review_id"],
            ["pull_request_review_base.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["auth_user.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "review_id", "associated_review_id", name="uq_pull_request_review_association"
        ),
    )

    # Add indexes for common query patterns
    op.create_index(
        "idx_assoc_review",
        "pull_request_review_association",
        ["review_id"],
    )
    op.create_index(
        "idx_assoc_associated",
        "pull_request_review_association",
        ["associated_review_id"],
    )


def downgrade() -> None:
    """Drop pull_request_review_association table"""

    op.drop_index("idx_assoc_associated", table_name="pull_request_review_association")
    op.drop_index("idx_assoc_review", table_name="pull_request_review_association")
    op.drop_table("pull_request_review_association")
