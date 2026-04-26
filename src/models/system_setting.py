"""System settings model for persistent configuration storage"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.utils.timezone import get_current_time


class SystemSetting(Base):
    """Model for storing system-wide configuration settings

    Provides persistent storage for system settings with audit trail support.
    Settings are cached in Redis for performance but persisted in MySQL for reliability.
    """

    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    setting_key: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique identifier for the setting (e.g., 'registration_enabled')",
    )
    setting_value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Current value of the setting (stored as string)",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable description of what this setting controls",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether this setting is currently active",
    )
    updated_by: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="ID of the auth_user who last modified this setting",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_current_time,
        nullable=False,
        comment="Timestamp when the setting was first created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_current_time,
        onupdate=get_current_time,
        nullable=False,
        comment="Timestamp when the setting was last updated",
    )

    def __repr__(self) -> str:
        return f"<SystemSetting(key='{self.setting_key}', value='{self.setting_value}')>"
