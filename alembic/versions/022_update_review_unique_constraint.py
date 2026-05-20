"""Update review unique constraint to use pull_request_id

Revision ID: 022
Revises: 021
Create Date: 2026-05-12

This migration updates the unique constraint on pull_request_review_base table
to use pull_request_id instead of pull_request_commit_id for proper PR-level tracking.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Update unique constraint to use pull_request_id instead of pull_request_commit_id"""
    from sqlalchemy import inspect

    # Get the bind/connection to inspect the database
    bind = op.get_bind()

    # Check existing constraints
    inspector = inspect(bind)
    constraints = inspector.get_unique_constraints("pull_request_review_base")
    constraint_names = [c["name"] for c in constraints]

    # Drop the old unique constraint if it exists
    if "uq_pr_commit_file" in constraint_names:
        op.drop_constraint("uq_pr_commit_file", "pull_request_review_base", type_="unique")

    # Create new unique constraint with pull_request_id only if it doesn't exist
    if "uq_pr_id_file" not in constraint_names:
        op.create_unique_constraint(
            "uq_pr_id_file",
            "pull_request_review_base",
            ["pull_request_id", "project_key", "repository_slug", "source_filename"],
        )


def downgrade() -> None:
    """Revert to original constraint using pull_request_commit_id"""
    from sqlalchemy import inspect

    # Get the bind/connection to inspect the database
    bind = op.get_bind()

    # Check if the new constraint exists
    inspector = inspect(bind)
    constraints = inspector.get_unique_constraints("pull_request_review_base")
    constraint_names = [c["name"] for c in constraints]

    # Drop the new unique constraint if it exists
    if "uq_pr_id_file" in constraint_names:
        op.drop_constraint("uq_pr_id_file", "pull_request_review_base", type_="unique")

    # Recreate the old unique constraint
    op.create_unique_constraint(
        "uq_pr_commit_file",
        "pull_request_review_base",
        ["pull_request_commit_id", "project_key", "repository_slug", "source_filename"],
    )
