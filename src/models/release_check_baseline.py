"""Release check baseline model.

The baseline of a repository is the ref a merge check compares against: the fork
point of a maintenance line, or the previous release of that line. Storing it per
repository makes the routine per-build check a matter of picking two releases
instead of remembering (and mistyping) a third ref - and it is shared by the whole
team, unlike a value kept in one browser.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.utils.timezone import get_current_time


class ReleaseCheckBaseline(Base):
    """Repository scoped baseline ref used by the release missing check."""

    __tablename__ = "release_check_baseline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)

    # Repository coordinates (the project key is kept upper-cased so the same
    # repository cannot end up with two baselines through casing)
    git_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    project_key: Mapped[str] = mapped_column(String(32), nullable=False)
    repository_slug: Mapped[str] = mapped_column(String(128), nullable=False)

    baseline_ref: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="Ref the missing check narrows against"
    )
    note: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Why this baseline, e.g. 'fork point of the 1.x line'"
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Username of the last editor"
    )

    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=get_current_time, nullable=False
    )
    updated_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=get_current_time, onupdate=get_current_time, nullable=False
    )

    __table_args__ = (
        # one baseline per repository
        Index(
            "uk_release_check_baseline_repo",
            "git_provider",
            "project_key",
            "repository_slug",
            unique=True,
        ),
        Index("idx_release_check_baseline_project", "project_key"),
        Index("idx_release_check_baseline_slug", "repository_slug"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "git_provider": self.git_provider,
            "project_key": self.project_key,
            "repository_slug": self.repository_slug,
            "baseline_ref": self.baseline_ref,
            "note": self.note,
            "updated_by": self.updated_by,
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "updated_date": self.updated_date.isoformat() if self.updated_date else None,
        }

    def __repr__(self) -> str:
        return (
            f"<ReleaseCheckBaseline({self.git_provider}/{self.project_key}/"
            f"{self.repository_slug}='{self.baseline_ref}')>"
        )
