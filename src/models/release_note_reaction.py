"""Release note reaction model - the kudos a release is given.

A release is read by whoever the repository is shared with, and the notes are
written for them: a reaction is one such reader saying the release was welcome,
as one of a small set of emojis. One person gives each emoji at most once, which
is what the unique key says - clicking the same emoji again takes the kudos back
rather than adding a second one.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.utils.timezone import get_current_time


class ReleaseNoteReaction(Base):
    """One reader's reaction to one release."""

    __tablename__ = "release_note_reaction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)

    note_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("release_note.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Who gave it: the account, not the git author of the commits
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("auth_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    emoji: Mapped[str] = mapped_column(String(16), nullable=False)

    created_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: get_current_time()
    )

    __table_args__ = (
        # One kudos per person per emoji: the second click removes the first
        UniqueConstraint("note_id", "user_id", "emoji", name="uq_release_note_reaction"),
        # Counting the reactions of a page of releases reads by release and emoji
        Index("ix_release_note_reaction_note_emoji", "note_id", "emoji"),
    )
