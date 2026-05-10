"""Create personal access tokens table

Revision ID: 021
Revises: 020_add_user_avatar
Create Date: 2026-05-06 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create personal_access_token table"""
    op.create_table(
        "personal_access_token",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("auth_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "name", sa.String(length=100), nullable=False, comment="Token name for identification"
        ),
        sa.Column(
            "token_hash", sa.String(length=255), nullable=False, comment="SHA-256 hash of the token"
        ),
        sa.Column(
            "prefix",
            sa.String(length=20),
            nullable=False,
            comment="First 12 characters for identification",
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=True, comment="Token expiration timestamp"),
        sa.Column("last_used_at", sa.DateTime(), nullable=True, comment="Last usage timestamp"),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
            comment="Token active status",
        ),
        sa.Column("ip_address", sa.String(length=45), nullable=True, comment="Creation IP address"),
        sa.Column("user_agent", sa.Text(), nullable=True, comment="Creation user agent"),
        sa.ForeignKeyConstraint(["auth_user_id"], ["auth_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for performance
    op.create_index("idx_auth_user", "personal_access_token", ["auth_user_id"])
    op.create_index("idx_prefix", "personal_access_token", ["prefix"])
    op.create_index("idx_expires_at", "personal_access_token", ["expires_at"])
    op.create_index("idx_is_active", "personal_access_token", ["is_active"])
    op.create_index(
        "idx_auth_user_created", "personal_access_token", ["auth_user_id", "created_at"]
    )


def downgrade() -> None:
    """Drop personal_access_token table"""
    op.drop_index("idx_auth_user_created", table_name="personal_access_token")
    op.drop_index("idx_is_active", table_name="personal_access_token")
    op.drop_index("idx_expires_at", table_name="personal_access_token")
    op.drop_index("idx_prefix", table_name="personal_access_token")
    op.drop_index("idx_auth_user", table_name="personal_access_token")
    op.drop_table("personal_access_token")
