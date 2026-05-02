from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.models.repository import Repository
from src.utils.timezone import get_current_time, utc_to_local


if TYPE_CHECKING:
    from src.models.project_registry import ProjectRegistry
    from src.models.pull_request import PullRequestReviewBase, PullRequestScore


class Project(Base):
    """Project model representing the project table in the database"""

    __tablename__ = "project"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)

    # Project information
    project_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)

    project_name: Mapped[str] = mapped_column(String(128), nullable=False)

    project_key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    project_url: Mapped[str] = mapped_column(String(255), nullable=False)

    # Status fields
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Timestamps
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=get_current_time
    )

    updated_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=get_current_time,
        onupdate=get_current_time,
    )

    # Relationships
    repositories: Mapped[list[Repository]] = relationship(
        "Repository", back_populates="project", cascade="all, delete-orphan"
    )

    pull_request_reviews: Mapped[list[PullRequestReviewBase]] = relationship(
        "PullRequestReviewBase", back_populates="project", cascade="all, delete-orphan"
    )

    # Registry entries linking this project to applications
    registry_entries: Mapped[list[ProjectRegistry]] = relationship(
        "ProjectRegistry", back_populates="project", cascade="all, delete-orphan"
    )

    # Score records
    scores: Mapped[list[PullRequestScore]] = relationship(
        "PullRequestScore", back_populates="project", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (Index("idx_project_id", "project_id"),)

    def __repr__(self) -> str:
        """String representation of the project"""
        return (
            f"<Project(id={self.id}, project_id='{self.project_id}', "
            f"project_name='{self.project_name}', project_key='{self.project_key}')>"
        )

    def to_dict(self) -> dict:
        """Convert project model to dictionary"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "project_key": self.project_key,
            "project_url": self.project_url,
            "created_date": utc_to_local(self.created_date).isoformat()
            if self.created_date
            else None,
            "updated_date": utc_to_local(self.updated_date).isoformat()
            if self.updated_date
            else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Project:
        """Create project instance from dictionary"""
        created_date = data.get("created_date")
        updated_date = data.get("updated_date")

        if isinstance(created_date, str):
            created_date = datetime.fromisoformat(created_date)

        if isinstance(updated_date, str):
            updated_date = datetime.fromisoformat(updated_date)

        return cls(
            id=data.get("id"),
            project_id=data.get("project_id"),
            project_name=data.get("project_name"),
            project_key=data.get("project_key"),
            project_url=data.get("project_url"),
            is_active=data.get("is_active", True),
            created_date=created_date,
            updated_date=updated_date,
        )

    def update(self, data: dict) -> None:
        """Update project attributes from dictionary"""
        for key, value in data.items():
            if hasattr(self, key) and key not in ["id", "created_date"]:
                setattr(self, key, value)
