"""User comment template model for personalized review comment templates"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.utils.timezone import get_current_time


if TYPE_CHECKING:
    pass


class UserCommentTemplate(Base):
    """Personal review comment template owned by an auth user"""

    __tablename__ = "user_comment_template"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Foreign key to auth_user (template owner)
    auth_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("auth_user.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Template data
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Template display name")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="Template comment content")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=get_current_time
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=get_current_time,
        onupdate=get_current_time,
    )

    # Table arguments
    __table_args__ = (Index("idx_user_comment_tpl_created", "auth_user_id", "created_at"),)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
