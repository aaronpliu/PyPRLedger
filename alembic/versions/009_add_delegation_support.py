"""add delegation support to user_role_assignment

Revision ID: 009
Revises: 008
Create Date: 2026-04-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add delegation support fields to user_role_assignment table"""

    # For MySQL, we'll use sa.Enum which handles enum creation automatically
    # No need to manually create the enum type

    # 1. Add starts_at field
    op.add_column(
        "user_role_assignment",
        sa.Column(
            "starts_at",
            sa.DateTime(),
            nullable=True,
            comment="Start time for role validity (for delegation or scheduled access)",
        ),
    )

    # 2. Add delegation flag
    op.add_column(
        "user_role_assignment",
        sa.Column(
            "is_delegated",
            sa.Boolean(),
            nullable=False,
            server_default="0",  # MySQL uses 0/1 for boolean
            comment="Whether this assignment is delegated from another user",
        ),
    )

    # 3. Add delegator ID
    op.add_column(
        "user_role_assignment",
        sa.Column(
            "delegator_id",
            sa.Integer(),
            sa.ForeignKey("auth_user.id", ondelete="SET NULL"),
            nullable=True,
            comment="User who delegated this role (NULL if not delegated)",
        ),
    )

    # 4. Add delegation status (MySQL will handle enum automatically)
    op.add_column(
        "user_role_assignment",
        sa.Column(
            "delegation_status",
            sa.Enum(
                "active",
                "expired",
                "revoked",
                "pending",
                name="delegation_status_enum",
            ),
            nullable=True,
            comment="Status of delegation (only for delegated roles)",
        ),
    )

    # 5. Add delegation scope (JSON)
    op.add_column(
        "user_role_assignment",
        sa.Column(
            "delegation_scope",
            sa.JSON(),
            nullable=True,
            comment="Specific permissions being delegated (subset of delegator's permissions)",
        ),
    )

    # 6. Add delegation reason
    op.add_column(
        "user_role_assignment",
        sa.Column(
            "delegation_reason",
            sa.Text(),
            nullable=True,
            comment="Reason or description for this delegation",
        ),
    )

    # 7. Add revocation tracking
    op.add_column(
        "user_role_assignment",
        sa.Column(
            "revoked_by",
            sa.Integer(),
            sa.ForeignKey("auth_user.id", ondelete="SET NULL"),
            nullable=True,
            comment="User who revoked this delegation",
        ),
    )

    op.add_column(
        "user_role_assignment",
        sa.Column(
            "revoked_at",
            sa.DateTime(),
            nullable=True,
            comment="Time when delegation was revoked",
        ),
    )

    # 8. Add indexes for query optimization
    op.create_index("ix_user_role_delegator_id", "user_role_assignment", ["delegator_id"])

    op.create_index("ix_user_role_starts_at", "user_role_assignment", ["starts_at"])

    op.create_index(
        "ix_user_role_delegation_status",
        "user_role_assignment",
        ["delegation_status"],
    )

    op.create_index("ix_user_role_is_delegated", "user_role_assignment", ["is_delegated"])


def downgrade() -> None:
    """Remove delegation support fields"""

    # Drop indexes
    op.drop_index("ix_user_role_is_delegated", table_name="user_role_assignment")
    op.drop_index("ix_user_role_delegation_status", table_name="user_role_assignment")
    op.drop_index("ix_user_role_starts_at", table_name="user_role_assignment")
    op.drop_index("ix_user_role_delegator_id", table_name="user_role_assignment")

    # Drop columns
    op.drop_column("user_role_assignment", "revoked_at")
    op.drop_column("user_role_assignment", "revoked_by")
    op.drop_column("user_role_assignment", "delegation_reason")
    op.drop_column("user_role_assignment", "delegation_scope")
    op.drop_column("user_role_assignment", "delegation_status")
    op.drop_column("user_role_assignment", "delegator_id")
    op.drop_column("user_role_assignment", "is_delegated")
    op.drop_column("user_role_assignment", "starts_at")

    # For MySQL, the enum type is automatically dropped when the column is dropped
    # No need to manually drop the enum type
