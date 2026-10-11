"""Record where a release was synced to Confluence

Revision ID: 034
Revises: 033
Create Date: 2026-10-11 00:30:00.000000

An optional integration: publishing a release can also write a Confluence page
holding the notes. Where that page lives is stored on the release itself, beside
the git provider release fields (``external_*``) rather than replacing them,
since a release can be published on both at once.

Every column is nullable and none of them is read by the release flow, so the
migration is additive and the integration stays switched off until it is
configured.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "034"
down_revision: str | None = "033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the Confluence page fields to release_note"""

    op.add_column(
        "release_note",
        sa.Column(
            "confluence_page_id",
            sa.String(length=64),
            nullable=True,
            comment="Confluence page id holding this release",
        ),
    )
    op.add_column(
        "release_note",
        sa.Column(
            "confluence_url",
            sa.String(length=512),
            nullable=True,
            comment="Confluence page url",
        ),
    )
    op.add_column(
        "release_note",
        sa.Column(
            "confluence_synced_date",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Set when the release was last synced",
        ),
    )
    op.add_column(
        "release_note",
        sa.Column(
            "confluence_sync_error",
            sa.String(length=512),
            nullable=True,
            comment="Why the last sync attempt failed, if it did",
        ),
    )


def downgrade() -> None:
    """Drop the Confluence page fields from release_note"""

    op.drop_column("release_note", "confluence_sync_error")
    op.drop_column("release_note", "confluence_synced_date")
    op.drop_column("release_note", "confluence_url")
    op.drop_column("release_note", "confluence_page_id")
