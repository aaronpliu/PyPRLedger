"""Create user_comment_template table

Revision ID: 030
Revises: 029_add_git_provider_to_project_registry
Create Date: 2026-09-02 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create user_comment_template table"""
    op.create_table(
        "user_comment_template",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("auth_user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False, comment="Template display name"),
        sa.Column("content", sa.Text(), nullable=False, comment="Template comment content"),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.ForeignKeyConstraint(["auth_user_id"], ["auth_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for performance
    op.create_index("idx_user_comment_tpl_user", "user_comment_template", ["auth_user_id"])
    op.create_index(
        "idx_user_comment_tpl_created", "user_comment_template", ["auth_user_id", "created_at"]
    )


def downgrade() -> None:
    """Drop user_comment_template table"""
    op.drop_index("idx_user_comment_tpl_created", table_name="user_comment_template")
    op.drop_index("idx_user_comment_tpl_user", table_name="user_comment_template")
    op.drop_table("user_comment_template")
