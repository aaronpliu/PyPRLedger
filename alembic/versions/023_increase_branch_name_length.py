"""Increase branch name field length from 64 to 255 characters

Revision ID: 023
Revises: 022
Create Date: 2026-05-12

This migration increases the max_length of source_branch and target_branch fields
to support longer Git branch names (e.g., /ref/origins/feature/...).
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Increase branch name field length to 255 characters"""

    # Alter source_branch column
    op.alter_column(
        "pull_request_review_base",
        "source_branch",
        existing_type=sa.String(64),
        type_=sa.String(255),
        existing_nullable=False,
    )

    # Alter target_branch column
    op.alter_column(
        "pull_request_review_base",
        "target_branch",
        existing_type=sa.String(64),
        type_=sa.String(255),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Revert branch name field length to 64 characters"""

    # Note: This may fail if there are existing branch names > 64 chars
    op.alter_column(
        "pull_request_review_base",
        "source_branch",
        existing_type=sa.String(255),
        type_=sa.String(64),
        existing_nullable=False,
    )

    op.alter_column(
        "pull_request_review_base",
        "target_branch",
        existing_type=sa.String(255),
        type_=sa.String(64),
        existing_nullable=False,
    )
