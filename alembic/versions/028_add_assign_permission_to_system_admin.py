"""add assign permission to system_admin role

Revision ID: 028
Revises: 027
Create Date: 2026-06-21 18:00:00.000000

This migration adds the 'assign' action to the system_admin role's
reviews permissions, which is required for managing auto-assignment
rules and other task assignment features.

The assign permission was added to review_admin in migrations 007
and 012, but system_admin was inadvertently missed both times.
"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "028"
down_revision: str | None = "027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add 'assign' permission to system_admin role for task assignment"""

    op.execute("""
        UPDATE role 
        SET permissions = '{
            "reviews": ["read", "create", "update", "delete", "assign"],
            "scores": ["read", "create", "update", "delete"],
            "projects": ["read", "create", "update", "delete", "manage"],
            "repositories": ["read", "create", "update", "delete", "manage"],
            "users": ["read", "create", "update", "delete", "manage"],
            "roles": ["read", "create", "update", "delete", "manage"],
            "settings": ["read", "update", "manage"],
            "audit_logs": ["read", "export"]
        }',
        updated_at = NOW()
        WHERE name = 'system_admin'
    """)


def downgrade() -> None:
    """Remove 'assign' permission from system_admin role"""

    op.execute("""
        UPDATE role 
        SET permissions = '{
            "reviews": ["read", "create", "update", "delete"],
            "scores": ["read", "create", "update", "delete"],
            "projects": ["read", "create", "update", "delete", "manage"],
            "repositories": ["read", "create", "update", "delete", "manage"],
            "users": ["read", "create", "update", "delete", "manage"],
            "roles": ["read", "create", "update", "delete", "manage"],
            "settings": ["read", "update", "manage"],
            "audit_logs": ["read", "export"]
        }',
        updated_at = NOW()
        WHERE name = 'system_admin'
    """)
