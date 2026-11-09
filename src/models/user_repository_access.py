"""Explicit grants binding a system user or a git user to one repository."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.utils.timezone import get_current_time


SUBJECT_AUTH_USER = "auth_user"
SUBJECT_GIT_USER = "git_user"
VALID_SUBJECT_TYPES = (SUBJECT_AUTH_USER, SUBJECT_GIT_USER)


class UserRepositoryAccess(Base):
    """A repository a subject is allowed to see.

    ``subject_id`` is polymorphic: it is ``AuthUser.id`` for ``auth_user`` rows
    and ``User.id`` for ``git_user`` rows, so no foreign key is declared. The
    business id ``User.user_id`` is never used as a subject id.
    """

    __tablename__ = "user_repository_access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)

    subject_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    subject_username: Mapped[str | None] = mapped_column(String(64), nullable=True)

    project_key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    repository_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    granted_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=get_current_time
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=get_current_time,
        onupdate=get_current_time,
    )

    __table_args__ = (
        UniqueConstraint(
            "subject_type",
            "subject_id",
            "project_key",
            "repository_slug",
            name="uq_user_repository_access",
        ),
        Index("ix_ura_subject", "subject_type", "subject_id"),
        Index("ix_ura_repo", "project_key", "repository_slug"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "subject_username": self.subject_username,
            "project_key": self.project_key,
            "repository_slug": self.repository_slug,
            "granted_by": self.granted_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
