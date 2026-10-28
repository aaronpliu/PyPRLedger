"""Record the contributors of a release

Revision ID: 038
Revises: 037
Create Date: 2026-10-28 17:40:00.000000

The people a release was written by are read from the commits of its scope when
the notes are generated: the commits are already in hand there, so the credits
are stored with the release instead of being rebuilt from the git provider every
time the release page asks for them.

The column is nullable - a release written by hand carries no credits - so the
migration is additive and leaves existing releases untouched.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "038"
down_revision: str | None = "037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the contributor snapshot to release_note"""

    op.add_column(
        "release_note",
        sa.Column(
            "contributors",
            sa.JSON(),
            nullable=True,
            comment="Contributors of the release scope (one entry per person)",
        ),
    )


def downgrade() -> None:
    """Drop the contributor snapshot from release_note"""

    op.drop_column("release_note", "contributors")
