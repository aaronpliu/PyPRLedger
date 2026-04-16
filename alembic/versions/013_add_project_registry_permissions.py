"""add project_registry permissions to system_admin role

Revision ID: 013
Revises: 012_fix_review_admin_assign_permission
Create Date: 2026-04-16

"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add project_registry permissions to system_admin role"""
    # Update system_admin role permissions to include project_registry management
    op.execute("""
        UPDATE role 
        SET permissions = JSON_SET(
            permissions,
            '$.project_registry', JSON_ARRAY('read', 'create', 'update', 'delete', 'manage')
        ),
        updated_at = NOW()
        WHERE name = 'system_admin'
    """)


def downgrade() -> None:
    """Remove project_registry permissions from system_admin role"""
    op.execute("""
        UPDATE role 
        SET permissions = JSON_REMOVE(permissions, '$.project_registry'),
        updated_at = NOW()
        WHERE name = 'system_admin'
    """)
