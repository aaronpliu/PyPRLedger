"""Add reactions (kudos) to releases

Revision ID: 039
Revises: 038
Create Date: 2026-10-29 10:20:00.000000

A release can be given kudos by the people who read it: one row per person and
emoji, so the same person cannot count twice and clicking the emoji again takes
the kudos back.

The table is new and the release rows are untouched, so the migration is additive.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "039"
down_revision: str | None = "038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the reaction table"""

    op.create_table(
        "release_note_reaction",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("note_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("emoji", sa.String(length=16), nullable=False),
        sa.Column("created_date", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["note_id"], ["release_note.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["auth_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("note_id", "user_id", "emoji", name="uq_release_note_reaction"),
    )
    op.create_index(
        op.f("ix_release_note_reaction_id"), "release_note_reaction", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_release_note_reaction_note_id"),
        "release_note_reaction",
        ["note_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_release_note_reaction_user_id"),
        "release_note_reaction",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_release_note_reaction_note_emoji",
        "release_note_reaction",
        ["note_id", "emoji"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the reaction table"""

    op.drop_index("ix_release_note_reaction_note_emoji", table_name="release_note_reaction")
    op.drop_index(op.f("ix_release_note_reaction_user_id"), table_name="release_note_reaction")
    op.drop_index(op.f("ix_release_note_reaction_note_id"), table_name="release_note_reaction")
    op.drop_index(op.f("ix_release_note_reaction_id"), table_name="release_note_reaction")
    op.drop_table("release_note_reaction")
