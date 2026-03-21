from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.core.database import Base


class Repository(Base):
    """Repository model representing the repository table in the database"""
    
    __tablename__ = "repository"
    
    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True
    )
    
    # Foreign key to project
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Repository information
    repository_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )
    
    repository_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False
    )
    
    repository_slug: Mapped[str] = mapped_column(
        String(128),
        nullable=False
    )
    
    repository_url: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    # Relationship to project
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="repositories"
    )
    
    # Relationship to pull request reviews
    pull_request_reviews: Mapped[List["PullRequestReview"]] = relationship(
        "PullRequestReview",
        back_populates="repository"
    )
    
    # Timestamps
    created_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    
    updated_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_repository_id", "repository_id"),
        Index("idx_project_id", "project_id"),
    )
    
    def __repr__(self) -> str:
        """String representation of the repository"""
        return (
            f"<Repository(id={self.id}, repository_id='{self.repository_id}', "
            f"repository_name='{self.repository_name}', project_id={self.project_id})>"
        )
    
    def to_dict(self) -> dict:
        """Convert repository model to dictionary"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "repository_id": self.repository_id,
            "repository_name": self.repository_name,
            "repository_slug": self.repository_slug,
            "repository_url": self.repository_url,
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "updated_date": self.updated_date.isoformat() if self.updated_date else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Repository":
        """Create repository instance from dictionary"""
        return cls(
            project_id=data.get("project_id"),
            repository_id=data.get("repository_id"),
            repository_name=data.get("repository_name"),
            repository_slug=data.get("repository_slug"),
            repository_url=data.get("repository_url")
        )
    
    def update(self, data: dict) -> None:
        """Update repository attributes from dictionary"""
        for key, value in data.items():
            if hasattr(self, key) and key not in ["id", "created_date"]:
                setattr(self, key, value)