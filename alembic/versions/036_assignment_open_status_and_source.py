"""Separate an assignment's progress from who made it

An assignment status used to carry two meanings at once. ``pending`` was the state
of a task nobody had been put on, and the automatic rules also wrote it to mean
"a rule placed this reviewer, not started" - which read as unassigned on a page
that had a reviewer sitting on it. Progress and provenance are split here:

* ``assignment_status`` keeps progress only: ``assigned`` -> ``in_progress`` ->
  ``completed``. Rows the rules wrote move from ``pending`` to ``assigned``, the
  same value a person's assignment gets.
* ``assignment_source`` records who put the reviewer there, ``manual`` or
  ``auto``. It is what the task pages read to label a rule's work, so the status
  no longer has to encode it.

A review nobody has been put on has no assignment row at all, and is reported as
``open`` where one status has to stand for the task.

Revision ID: 036
Revises: 035
Create Date: 2026-10-22 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "036"
down_revision: str | None = "035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLE = "pull_request_review_assignment"


def upgrade() -> None:
    """Record the source on the row and retire the overloaded 'pending' status."""
    op.add_column(
        TABLE,
        sa.Column(
            "assignment_source",
            sa.String(16),
            nullable=False,
            server_default="manual",
            comment="Who put the reviewer here: manual (a person) or auto (an assignment rule)",
        ),
    )

    # Only the rules ever wrote 'pending'; a person's assignment was written as
    # 'assigned'. Both meant "assigned, not started", so they become one status and
    # the rule's rows keep their provenance in the column added above.
    op.execute(
        f"""
        UPDATE {TABLE}
        SET assignment_source = 'auto'
        WHERE assignment_status = 'pending'
          AND assigned_by IS NULL
        """
    )
    op.execute(
        f"""
        UPDATE {TABLE}
        SET assignment_status = 'assigned'
        WHERE assignment_status = 'pending'
        """
    )

    op.alter_column(
        TABLE,
        "assignment_status",
        existing_type=sa.String(32),
        existing_nullable=False,
        server_default="assigned",
    )


def downgrade() -> None:
    """Put the rules' rows back on 'pending', the value that downgrade's code reads."""
    op.alter_column(
        TABLE,
        "assignment_status",
        existing_type=sa.String(32),
        existing_nullable=False,
        server_default="pending",
    )
    op.execute(
        f"""
        UPDATE {TABLE}
        SET assignment_status = 'pending'
        WHERE assignment_source = 'auto'
          AND assignment_status = 'assigned'
        """
    )
    op.drop_column(TABLE, "assignment_source")
