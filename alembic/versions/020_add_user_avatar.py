"""Add avatar_url column to auth_user table

Revision ID: 020
Revises: 019
Create Date: 2026-05-06

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema - add avatar_url column to auth_user table"""
    op.add_column(
        "auth_user",
        sa.Column("avatar_url", sa.String(500), nullable=True, comment="User avatar image URL"),
    )


def downgrade() -> None:
    """Downgrade database schema - remove avatar_url column from auth_user table"""
    op.drop_column("auth_user", "avatar_url")
