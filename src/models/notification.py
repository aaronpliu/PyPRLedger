"""Notification models for user notification system"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.utils.timezone import get_current_time


if TYPE_CHECKING:
    from src.models.user import User


class Notification(Base):
    """Notification model for storing user notifications"""

    __tablename__ = "notification"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to user
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user.username", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Notification content
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text(), nullable=False)

    # Related entity reference
    related_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    related_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Status and metadata
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[str] = mapped_column(
        Enum("low", "normal", "high", "urgent", name="notification_priority"),
        nullable=False,
        default="normal",
    )
    channel: Mapped[str] = mapped_column(
        Enum("in_app", "email", "slack", name="notification_channel"),
        nullable=False,
        default="in_app",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=get_current_time
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="notifications")

    # Indexes
    __table_args__ = (
        Index("idx_notification_user_read", "user_id", "is_read"),
        Index("idx_notification_created", created_at.desc()),
        Index("idx_notification_type", "type"),
    )

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, user={self.user_id}, type={self.type})>"

    def mark_as_read(self) -> None:
        """Mark this notification as read"""
        self.is_read = True
        self.read_at = get_current_time()

    def to_dict(self) -> dict:
        """Convert notification to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "related_id": self.related_id,
            "related_type": self.related_type,
            "is_read": self.is_read,
            "priority": self.priority,
            "channel": self.channel,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class NotificationPreference(Base):
    """Notification preference model for user notification settings"""

    __tablename__ = "notification_preference"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to user
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user.username", ondelete="CASCADE"),
        nullable=False,
    )

    # Preference configuration
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    channel_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    slack_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Timestamps
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=get_current_time,
        onupdate=get_current_time,
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="notification_preferences")

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "notification_type", name="unique_user_notification_type"),
        Index("idx_notification_pref_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<NotificationPreference(user={self.user_id}, type={self.notification_type})>"

    def to_dict(self) -> dict:
        """Convert preference to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "notification_type": self.notification_type,
            "channel_enabled": self.channel_enabled,
            "email_enabled": self.email_enabled,
            "in_app_enabled": self.in_app_enabled,
            "slack_enabled": self.slack_enabled,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
