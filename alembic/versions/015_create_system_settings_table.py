"""Create system_settings table for persistent configuration storage

Revision ID: 015
Revises: 014
Create Date: 2026-04-21

This migration creates a dedicated table for storing system-wide configuration
settings with audit trail support. Settings are persisted in MySQL for reliability
and cached in Redis for performance.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create system_settings table"""

    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "setting_key",
            sa.String(128),
            nullable=False,
            comment="Unique identifier for the setting (e.g., 'registration_enabled')",
        ),
        sa.Column(
            "setting_value",
            sa.Text(),
            nullable=False,
            comment="Current value of the setting (stored as string)",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Human-readable description of what this setting controls",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="1",
            comment="Whether this setting is currently active",
        ),
        sa.Column(
            "updated_by",
            sa.Integer(),
            nullable=True,
            comment="ID of the auth_user who last modified this setting",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Timestamp when the setting was first created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Timestamp when the setting was last updated",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("setting_key"),
    )

    # Add index on setting_key for fast lookups
    op.create_index(
        "idx_system_settings_key",
        "system_settings",
        ["setting_key"],
    )

    # Insert default registration_enabled setting
    op.execute(
        """
        INSERT INTO system_settings 
        (setting_key, setting_value, description, is_active, created_at, updated_at)
        VALUES 
        ('registration_enabled', 'true', 'Controls whether new user registration is allowed', 1, NOW(), NOW())
        """
    )


def downgrade() -> None:
    """Drop system_settings table"""
    op.drop_index("idx_system_settings_key", table_name="system_settings")
    op.drop_table("system_settings")
