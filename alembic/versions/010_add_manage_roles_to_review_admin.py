"""add manage roles permission to review_admin role

Revision ID: 010
Revises: 009
Create Date: 2026-04-12

"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add 'manage roles' permission to review_admin role"""

    # Update review_admin role permissions to include roles management
    # This allows review admins to create and manage role delegations
    from datetime import UTC, datetime

    new_permissions = {
        "reviews": ["read", "create", "update", "delete"],
        "scores": ["read", "create", "update", "delete"],
        "projects": ["read", "manage"],
        "repositories": ["read", "manage"],
        "users": ["read"],
        "roles": ["read", "manage"],
    }

    # Use SQLAlchemy to update the role
    from sqlalchemy import JSON, DateTime, String, column, table

    role_table = table(
        "role", column("name", String), column("permissions", JSON), column("updated_at", DateTime)
    )

    op.execute(
        role_table.update()
        .where(role_table.c.name == "review_admin")
        .values(permissions=new_permissions, updated_at=datetime.now(UTC))
    )


def downgrade() -> None:
    """Remove 'manage roles' permission from review_admin role"""

    # Revert to original permissions without roles management
    from datetime import UTC, datetime

    original_permissions = {
        "reviews": ["read", "create", "update", "delete"],
        "scores": ["read", "create", "update", "delete"],
        "projects": ["read", "manage"],
        "repositories": ["read", "manage"],
        "users": ["read"],
    }

    # Use SQLAlchemy to update the role
    from sqlalchemy import JSON, DateTime, String, column, table

    role_table = table(
        "role", column("name", String), column("permissions", JSON), column("updated_at", DateTime)
    )

    op.execute(
        role_table.update()
        .where(role_table.c.name == "review_admin")
        .values(permissions=original_permissions, updated_at=datetime.now(UTC))
    )
