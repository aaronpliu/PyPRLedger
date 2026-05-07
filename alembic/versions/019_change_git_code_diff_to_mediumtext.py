"""Change git_code_diff from TEXT to MEDIUMTEXT

Revision ID: 019
Revises: 018
Create Date: 2026-05-06

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema - change git_code_diff to MEDIUMTEXT"""
    # MySQL TEXT max length: 65,535 bytes (~64KB)
    # MySQL MEDIUMTEXT max length: 16,777,215 bytes (~16MB)
    # This allows storing large code diffs without truncation

    op.alter_column(
        table_name="pull_request_review_base",
        column_name="git_code_diff",
        type_=sa.Text().with_variant(sa.dialects.mysql.MEDIUMTEXT(), "mysql"),
        existing_type=sa.Text(),
        nullable=True,
        comment="Git code diff content (supports up to 16MB)",
    )


def downgrade() -> None:
    """Downgrade database schema - revert git_code_diff to TEXT"""
    op.alter_column(
        table_name="pull_request_review_base",
        column_name="git_code_diff",
        type_=sa.Text(),
        existing_type=sa.Text().with_variant(sa.dialects.mysql.MEDIUMTEXT(), "mysql"),
        nullable=True,
        comment="Git code diff content",
    )
