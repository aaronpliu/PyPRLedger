"""create auto_assign_rule table

Revision ID: 027
Revises: 026
Create Date: 2026-06-13 18:35:53.999326

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pull_request_review_auto_assignment_rule",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("conditions", mysql.JSON(), nullable=False),
        sa.Column("assign_to", mysql.JSON(), nullable=False),
        sa.Column("max_assignments", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        mysql_collate="utf8mb4_0900_ai_ci",
        mysql_default_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_index(
        "idx_auto_assign_rule_active_priority",
        "pull_request_review_auto_assignment_rule",
        ["is_active", "priority"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_auto_assign_rule_active_priority",
        table_name="pull_request_review_auto_assignment_rule",
    )
    op.drop_table("pull_request_review_auto_assignment_rule")
