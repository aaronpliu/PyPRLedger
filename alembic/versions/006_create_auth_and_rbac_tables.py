"""create auth and rbac tables

Revision ID: 006
Revises: 005
Create Date: 2026-04-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create authentication and RBAC tables"""

    # Create auth_user table
    op.create_table(
        "auth_user",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=128), nullable=True),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_auth_user_user_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_auth_user_username", "auth_user", ["username"], unique=False)
    op.create_index("ix_auth_user_email", "auth_user", ["email"], unique=False)
    op.create_index("ix_auth_user_user_id", "auth_user", ["user_id"], unique=False)

    # Create role table
    op.create_table(
        "role",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_role_name", "role", ["name"], unique=False)

    # Create organization_group table
    op.create_table(
        "organization_group",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column(
            "type",
            sa.Enum("group", "team", name="org_group_type"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["organization_group.id"],
            name="fk_org_group_parent_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_organization_group_parent_id",
        "organization_group",
        ["parent_id"],
        unique=False,
    )

    # Create user_role_assignment table
    op.create_table(
        "user_role_assignment",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("auth_user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column(
            "resource_type",
            sa.Enum("global", "project", "repository", name="resource_type_enum"),
            nullable=False,
        ),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["auth_user_id"],
            ["auth_user.id"],
            name="fk_user_role_auth_user_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["role.id"],
            name="fk_user_role_role_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["auth_user.id"],
            name="fk_user_role_granted_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "auth_user_id",
            "role_id",
            "resource_type",
            "resource_id",
            name="unique_user_role_resource",
        ),
    )
    op.create_index(
        "ix_user_role_assignment_auth_user_id",
        "user_role_assignment",
        ["auth_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_role_assignment_role_id",
        "user_role_assignment",
        ["role_id"],
        unique=False,
    )

    # Create audit_log table
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("auth_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("old_values", sa.JSON(), nullable=True),
        sa.Column("new_values", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("request_method", sa.String(length=10), nullable=True),
        sa.Column("request_path", sa.String(length=256), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["auth_user_id"],
            ["auth_user.id"],
            name="fk_audit_log_auth_user_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_auth_user_id", "audit_log", ["auth_user_id"], unique=False)
    op.create_index("ix_audit_log_action", "audit_log", ["action"], unique=False)
    op.create_index("ix_audit_log_resource_type", "audit_log", ["resource_type"], unique=False)
    op.create_index("ix_audit_log_resource_id", "audit_log", ["resource_id"], unique=False)
    op.create_index("ix_audit_log_request_path", "audit_log", ["request_path"], unique=False)
    op.create_index("ix_audit_log_response_status", "audit_log", ["response_status"], unique=False)
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"], unique=False)

    # Insert default roles
    from datetime import UTC, datetime

    now = datetime.now(UTC)

    op.bulk_insert(
        sa.table(
            "role",
            sa.column("id", sa.Integer),
            sa.column("name", sa.String),
            sa.column("description", sa.Text),
            sa.column("permissions", sa.JSON),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {
                "id": 1,
                "name": "viewer",
                "description": "Read-only access to reviews and scores",
                "permissions": {
                    "reviews": ["read"],
                    "scores": ["read"],
                    "projects": ["read"],
                    "repositories": ["read"],
                },
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": 2,
                "name": "reviewer",
                "description": "Can view and submit reviews and scores",
                "permissions": {
                    "reviews": ["read", "create"],
                    "scores": ["read", "create", "update"],
                    "projects": ["read"],
                    "repositories": ["read"],
                },
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": 3,
                "name": "review_admin",
                "description": "Can manage all review data (not system admin)",
                "permissions": {
                    "reviews": ["read", "create", "update", "delete"],
                    "scores": ["read", "create", "update", "delete"],
                    "projects": ["read", "manage"],
                    "repositories": ["read", "manage"],
                    "users": ["read"],
                },
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": 4,
                "name": "system_admin",
                "description": "Full system administration privileges",
                "permissions": {
                    "reviews": ["read", "create", "update", "delete"],
                    "scores": ["read", "create", "update", "delete"],
                    "projects": ["read", "create", "update", "delete", "manage"],
                    "repositories": ["read", "create", "update", "delete", "manage"],
                    "users": ["read", "create", "update", "delete", "manage"],
                    "roles": ["read", "create", "update", "delete", "manage"],
                    "settings": ["read", "update", "manage"],
                    "audit_logs": ["read", "export"],
                },
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    """Drop authentication and RBAC tables"""

    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table("audit_log")
    op.drop_table("user_role_assignment")
    op.drop_table("organization_group")
    op.drop_table("role")
    op.drop_table("auth_user")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS resource_type_enum")
    op.execute("DROP TYPE IF EXISTS org_group_type")
