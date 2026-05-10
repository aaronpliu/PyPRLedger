"""Personal Access Token model for API authentication"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


if TYPE_CHECKING:
    from src.models.auth_user import AuthUser


class PersonalAccessToken(Base):
    """Personal Access Token model for API authentication"""

    __tablename__ = "personal_access_token"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Foreign key to auth_user
    auth_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("auth_user.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Token metadata
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    prefix: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Creation context
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    auth_user: Mapped[AuthUser] = relationship("AuthUser", back_populates="personal_access_tokens")

    # Table arguments
    __table_args__ = (Index("idx_auth_user_created", "auth_user_id", "created_at"),)

    def to_dict(self) -> dict:
        """Convert to dictionary (excludes sensitive data)"""
        return {
            "id": self.id,
            "name": self.name,
            "prefix": self.prefix,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "is_active": self.is_active,
        }
