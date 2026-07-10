"""add git_provider column to project_registry and project

Revision ID: 029
Revises: 028
Create Date: 2026-07-03 10:00:00.000000

This migration adds a git_provider column to the project_registry and project tables
to support multiple Git providers (Bitbucket Server, GitHub Enterprise)
coexisting in the same deployment.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "029"
down_revision: str | None = "028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add git_provider column to project_registry and project"""
    op.add_column(
        "project_registry",
        sa.Column(
            "git_provider",
            sa.String(32),
            nullable=False,
            server_default="bitbucket_server",
        ),
    )
    op.add_column(
        "project",
        sa.Column(
            "git_provider",
            sa.String(32),
            nullable=False,
            server_default="bitbucket_server",
        ),
    )


def downgrade() -> None:
    """Remove git_provider columns"""
    op.drop_column("project", "git_provider")
    op.drop_column("project_registry", "git_provider")
