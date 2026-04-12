"""fix review_admin assign permission

Revision ID: 012
Revises: 011
Create Date: 2026-04-12

This migration ensures that the review_admin role has the 'assign' permission
on reviews resource, which is required for assigning review tasks to reviewers.

The permission was supposed to be added in migration 007, but due to potential
issues with JSON field updates or subsequent migrations, it may have been lost.
"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Ensure review_admin role has 'assign' permission on reviews"""

    # Update review_admin role permissions to include 'assign' action
    # This is idempotent - safe to run multiple times
    op.execute("""
        UPDATE role 
        SET permissions = '{
            "reviews": ["read", "create", "update", "delete", "assign"],
            "scores": ["read", "create", "update", "delete"],
            "projects": ["read", "manage"],
            "repositories": ["read", "manage"],
            "users": ["read"],
            "roles": ["read", "manage"]
        }',
        updated_at = NOW()
        WHERE name = 'review_admin'
    """)


def downgrade() -> None:
    """Remove 'assign' permission from review_admin role (revert to pre-007 state)"""

    # Revert to original permissions without 'assign'
    op.execute("""
        UPDATE role 
        SET permissions = '{
            "reviews": ["read", "create", "update", "delete"],
            "scores": ["read", "create", "update", "delete"],
            "projects": ["read", "manage"],
            "repositories": ["read", "manage"],
            "users": ["read"],
            "roles": ["read", "manage"]
        }',
        updated_at = NOW()
        WHERE name = 'review_admin'
    """)
