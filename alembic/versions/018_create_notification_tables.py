"""Create notification and notification_preference tables

Revision ID: 018
Revises: 017
Create Date: 2026-05-02

This migration creates the notification system infrastructure:
1. notification table - stores user notifications
2. notification_preference table - stores user notification preferences
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create notification system tables"""

    # Create notification table
    op.create_table(
        "notification",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.String(64),
            sa.ForeignKey("user.username", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("type", sa.String(50), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("related_id", sa.String(100), nullable=True),
        sa.Column("related_type", sa.String(50), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column(
            "priority",
            sa.Enum("low", "normal", "high", "urgent", name="notification_priority"),
            nullable=False,
            server_default="normal",
        ),
        sa.Column(
            "channel",
            sa.Enum("in_app", "email", "slack", name="notification_channel"),
            nullable=False,
            server_default="in_app",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create indexes for performance
    op.create_index("idx_notification_user_read", "notification", ["user_id", "is_read"])
    op.create_index("idx_notification_created", "notification", [sa.text("created_at DESC")])
    op.create_index("idx_notification_type", "notification", ["type"])

    # Create notification_preference table
    op.create_table(
        "notification_preference",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.String(64),
            sa.ForeignKey("user.username", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("channel_enabled", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("slack_enabled", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("user_id", "notification_type", name="unique_user_notification_type"),
    )

    # Create index for preference lookups
    op.create_index("idx_notification_pref_user", "notification_preference", ["user_id"])


def downgrade() -> None:
    """Drop notification system tables"""

    # Drop indexes first
    op.drop_index("idx_notification_pref_user", table_name="notification_preference")
    op.drop_index("idx_notification_type", table_name="notification")
    op.drop_index("idx_notification_created", table_name="notification")
    op.drop_index("idx_notification_user_read", table_name="notification")

    # Drop tables
    op.drop_table("notification_preference")
    op.drop_table("notification")

    # Drop enums (MySQL doesn't support DROP TYPE, so we leave them)
    # For PostgreSQL, you would add:
    # op.execute("DROP TYPE IF EXISTS notification_priority")
    # op.execute("DROP TYPE IF EXISTS notification_channel")
