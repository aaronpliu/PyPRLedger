"""change_score_to_float

Revision ID: 003
Revises: 002
Create Date: 2026-03-31

Change the score column in pull_request_review table from Integer to Float
to support decimal scores (e.g., 7.5, 8.3)

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Change score column type from Integer to Float

    This allows for more granular scoring with decimal values
    """
    # Alter the score column type from Integer to Float
    op.alter_column(
        "pull_request_review",
        "score",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=True,
    )


def downgrade() -> None:
    """
    Revert score column back to Integer

    Note: This may result in loss of precision if decimal scores exist
    """
    op.alter_column(
        "pull_request_review",
        "score",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
