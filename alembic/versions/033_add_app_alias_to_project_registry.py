"""add app_alias column to project_registry

Revision ID: 033
Revises: 032
Create Date: 2026-10-09 10:00:00.000000

The dependency database keys its applications by a vocabulary of its own, which
does not always follow from the name an administrator registers a repository
under: a repository registered as ``trmyapp`` may have to be asked for as
``myapptr``. The column holds that name when it differs, per repository, and is
left empty when it does not - an empty alias means the application name is used,
so the two cannot drift apart on their own.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "033"
down_revision: str | None = "032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the optional dependency-database name to project_registry"""
    op.add_column(
        "project_registry",
        sa.Column("app_alias", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    """Remove the dependency-database name"""
    op.drop_column("project_registry", "app_alias")
