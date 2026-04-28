"""add must_change_password to auth_user

Revision ID: 016
Revises: 015
Create Date: 2026-04-28 22:46:39.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add must_change_password column to auth_user table"""
    op.add_column(
        "auth_user",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Force password change on next login",
        ),
    )


def downgrade() -> None:
    """Remove must_change_password column from auth_user table"""
    op.drop_column("auth_user", "must_change_password")
