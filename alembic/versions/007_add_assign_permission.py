"""add assign permission to review_admin role

Revision ID: 007
Revises: 006
Create Date: 2026-04-09

"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add 'assign' permission to review_admin role for task assignment"""

    # Update review_admin role permissions to include 'assign' action
    op.execute("""
        UPDATE role 
        SET permissions = '{
            "reviews": ["read", "create", "update", "delete", "assign"],
            "scores": ["read", "create", "update", "delete"],
            "projects": ["read", "manage"],
            "repositories": ["read", "manage"],
            "users": ["read"]
        }',
        updated_at = NOW()
        WHERE name = 'review_admin'
    """)


def downgrade() -> None:
    """Remove 'assign' permission from review_admin role"""

    # Revert to original permissions without 'assign'
    op.execute("""
        UPDATE role 
        SET permissions = '{
            "reviews": ["read", "create", "update", "delete"],
            "scores": ["read", "create", "update", "delete"],
            "projects": ["read", "manage"],
            "repositories": ["read", "manage"],
            "users": ["read"]
        }',
        updated_at = NOW()
        WHERE name = 'review_admin'
    """)
