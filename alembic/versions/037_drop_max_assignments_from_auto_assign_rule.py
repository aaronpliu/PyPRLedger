"""Let a rule's reviewer list be exactly who reviews

A rule carried two ways to say how many reviewers a pull request gets: the
``assign_to`` list, and ``max_assignments``, which truncated that list to its
first N names. Truncation was silent and order-dependent - the third name of a
three-name list with ``max_assignments = 2`` was dropped without a word, and the
form never showed why - and it ran before the usernames were checked against the
user table, so a stale name in the first slots could leave a review with fewer
assignments than asked for, or none at all.

The list is what the rule is about, so it is the only place that says how many
reviewers there are. The column goes.

Revision ID: 037
Revises: 036
Create Date: 2026-10-27 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "037"
down_revision: str | None = "036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLE = "pull_request_review_auto_assignment_rule"


def upgrade() -> None:
    """Drop the cap; every username in a rule's list is assigned."""
    op.drop_column(TABLE, "max_assignments")


def downgrade() -> None:
    """Restore the column, at 0 - the value that assigns the whole list.

    The caps that were in place are not recoverable from the rows, and guessing one
    would truncate a reviewer list the current code assigns in full. ``0`` reads as
    "assign all", so a downgraded rule keeps assigning the reviewers it lists.
    """
    op.add_column(
        TABLE,
        sa.Column(
            "max_assignments",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
