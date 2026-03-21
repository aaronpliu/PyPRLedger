from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, DateTime, Index, Integer, String
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.core.database import Base


class Project(Base):
    """Project model representing the project table in the database"""
    
    __tablename__ = "project"
    
    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True
    )
    
    # Project information
    project_id: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        nullable=False,
        index=True
    )
    
    project_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False
    )
    
    project_key: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        nullable=False
    )
    
    project_url: Mapped[str] = mapped_column(
        String(255),
        nullable=False
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
    
    # Relationships
    repositories: Mapped[List["Repository"]] = relationship(
        "Repository",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    
    pull_request_reviews: Mapped[List["PullRequestReview"]] = relationship(
        "PullRequestReview",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_project_id", "project_id"),
    )
    
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
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "updated_date": self.updated_date.isoformat() if self.updated_date else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        """Create project instance from dictionary"""
        return cls(
            project_id=data.get("project_id"),
            project_name=data.get("project_name"),
            project_key=data.get("project_key"),
            project_url=data.get("project_url")
        )
    
    def update(self, data: dict) -> None:
        """Update project attributes from dictionary"""
        for key, value in data.items():
            if hasattr(self, key) and key not in ["id", "created_date"]:
                setattr(self, key, value)