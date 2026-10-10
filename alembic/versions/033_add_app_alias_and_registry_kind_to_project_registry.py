"""add app_alias and registry_kind to project_registry

Revision ID: 033
Revises: 032
Create Date: 2026-10-09 10:00:00.000000

Two things a registration has to say about itself, added together because both are
about the same question - what this registration is for - and neither has been
released on its own.

The alias: the dependency database keys its applications by a vocabulary of its
own, which does not always follow from the name an administrator registers a
repository under: a repository registered as ``trmyapp`` may have to be asked for
as ``myapptr``. The column holds that name when it differs, per repository, and is
left empty when it does not - an empty alias means the application name is used,
so the two cannot drift apart on their own.

The kind: the registry serves two purposes - resolving a repository to the
application the dependency database knows it by, and resolving a *package* name
back to the repository it lives in (which is how the App Diff compares a moved
dependency in its own repository). Only the first is something the pages that read
an application's releases can use, because the dependency database holds release
records for applications alone. Existing rows are marked ``application``: that is
what the table was built for, and a registration made for another purpose is the
exception an administrator can point out.
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
    """Add the dependency-database name and the kind to project_registry"""
    op.add_column(
        "project_registry",
        sa.Column("app_alias", sa.String(64), nullable=True),
    )
    op.add_column(
        "project_registry",
        sa.Column("registry_kind", sa.String(16), nullable=False, server_default="application"),
    )
    op.create_index(
        "ix_project_registry_registry_kind", "project_registry", ["registry_kind"]
    )


def downgrade() -> None:
    """Remove the dependency-database name and the kind"""
    op.drop_index("ix_project_registry_registry_kind", table_name="project_registry")
    op.drop_column("project_registry", "registry_kind")
    op.drop_column("project_registry", "app_alias")
