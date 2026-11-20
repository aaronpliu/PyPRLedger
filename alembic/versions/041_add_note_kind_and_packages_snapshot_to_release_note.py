"""Tell what a release note's body covers

Revision ID: 041
Revises: 040
Create Date: 2026-11-20 10:00:00.000000

A release slot per tag now serves two kinds of note: the ordinary
per-repository note the generator writes ("single"), and the aggregate note of
an application version span - the application plus the packages it pins
("combined"). The kind decides what overwrites what: a combined save takes the
slot, a single save does not.

Both columns are additive: existing releases read as "single" with no package
snapshot, which is exactly what they are.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "041"
down_revision: str | None = "040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the note kind and the package snapshot to release_note"""

    op.add_column(
        "release_note",
        sa.Column(
            "note_kind",
            sa.String(length=16),
            nullable=False,
            server_default="single",
            comment="single (per-repository) or combined (application + packages)",
        ),
    )
    op.create_index("ix_release_note_note_kind", "release_note", ["note_kind"])
    op.add_column(
        "release_note",
        sa.Column(
            "packages_snapshot",
            sa.JSON(),
            nullable=True,
            comment="Packages a combined note carried (one entry per package)",
        ),
    )


def downgrade() -> None:
    """Drop the note kind and the package snapshot from release_note"""

    op.drop_column("release_note", "packages_snapshot")
    op.drop_index("ix_release_note_note_kind", table_name="release_note")
    op.drop_column("release_note", "note_kind")
