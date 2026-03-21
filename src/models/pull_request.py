from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, JSON
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.core.database import Base


class PullRequestReview(Base):
    """Pull request review model representing the pull_request_review table in the database"""
    
    __tablename__ = "pull_request_review"
    
    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True
    )
    
    # Foreign keys
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    pull_request_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False
    )
    
    reviewer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    repository_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("repository.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Pull request information
    pull_request_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True
    )
    
    pull_request_commit_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True
    )
    
    source_branch: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )
    
    target_branch: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )
    
    # Code review details
    git_code_diff: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    source_filename: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    # AI and review content
    ai_suggestions: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True
    )
    
    reviewer_comments: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # Review metrics
    score: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    # Status
    pull_request_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False
    )
    
    # Metadata (renamed from 'metadata' to avoid SQLAlchemy reserved name conflict)
    review_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        name="metadata"  # Database column name remains 'metadata'
    )
    
    # Relationships
    project: Mapped["Project"] = relationship(
        back_populates="pull_request_reviews"
    )
    
    repository: Mapped["Repository"] = relationship(
        back_populates="pull_request_reviews"
    )
    
    pull_request_user: Mapped["User"] = relationship(
        foreign_keys=[pull_request_user_id],
        back_populates="authored_reviews"
    )
    
    reviewer: Mapped["User"] = relationship(
        foreign_keys=[reviewer_id],
        back_populates="reviewed_reviews"
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
        Index("idx_pull_request_id", "pull_request_id"),
        Index("idx_project_id", "project_id"),
        Index("idx_reviewer_id", "reviewer_id"),
        Index("idx_created_date", "created_date"),
    )
    
    def __repr__(self) -> str:
        """String representation of the pull request review"""
        return (
            f"<PullRequestReview(id={self.id}, pull_request_id='{self.pull_request_id}', "
            f"commit_id='{self.pull_request_commit_id}', project_id={self.project_id}, "
            f"repository_id={self.repository_id}, reviewer_id={self.reviewer_id}, "
            f"status='{self.pull_request_status}')>"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert pull request review model to dictionary"""
        return {
            "id": self.id,
            "pull_request_id": self.pull_request_id,
            "pull_request_commit_id": self.pull_request_commit_id,
            "project_id": self.project_id,
            "repository_id": self.repository_id,
            "pull_request_user_id": self.pull_request_user_id,
            "reviewer_id": self.reviewer_id,
            "source_branch": self.source_branch,
            "target_branch": self.target_branch,
            "git_code_diff": self.git_code_diff,
            "source_filename": self.source_filename,
            "ai_suggestions": self.ai_suggestions,
            "reviewer_comments": self.reviewer_comments,
            "score": self.score,
            "pull_request_status": self.pull_request_status,
            "metadata": self.review_metadata,
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "updated_date": self.updated_date.isoformat() if self.updated_date else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PullRequestReview":
        """Create pull request review instance from dictionary"""
        return cls(
            pull_request_id=data.get("pull_request_id"),
            pull_request_commit_id=data.get("pull_request_commit_id"),
            project_id=data.get("project_id"),
            repository_id=data.get("repository_id"),
            pull_request_user_id=data.get("pull_request_user_id"),
            reviewer_id=data.get("reviewer_id"),
            source_branch=data.get("source_branch"),
            target_branch=data.get("target_branch"),
            git_code_diff=data.get("git_code_diff"),
            source_filename=data.get("source_filename"),
            ai_suggestions=data.get("ai_suggestions"),
            reviewer_comments=data.get("reviewer_comments"),
            score=data.get("score"),
            pull_request_status=data.get("pull_request_status"),
            review_metadata=data.get("metadata")
        )
    
    def update(self, data: Dict[str, Any]) -> None:
        """Update pull request review attributes from dictionary"""
        updatable_fields = [
            "git_code_diff",
            "source_filename",
            "ai_suggestions",
            "reviewer_comments",
            "score",
            "pull_request_status",
            "review_metadata"
        ]
        
        for key, value in data.items():
            if key in updatable_fields and hasattr(self, key):
                setattr(self, key, value)
    
    @property
    def is_open(self) -> bool:
        """Check if the pull request is open"""
        return self.pull_request_status == "open"
    
    @property
    def is_merged(self) -> bool:
        """Check if the pull request is merged"""
        return self.pull_request_status == "merged"
    
    @property
    def is_closed(self) -> bool:
        """Check if the pull request is closed"""
        return self.pull_request_status == "closed"
    
    @property
    def is_draft(self) -> bool:
        """Check if the pull request is a draft"""
        return self.pull_request_status == "draft"
    
    def can_transition_to(self, new_status: str) -> bool:
        """
        Check if the pull request can transition to the new status
        
        Args:
            new_status: The target status to transition to
            
        Returns:
            bool: True if the transition is valid, False otherwise
        """
        valid_transitions = {
            "draft": ["open", "closed"],
            "open": ["merged", "closed"],
            "merged": [],
            "closed": ["open"]
        }
        
        return new_status in valid_transitions.get(self.pull_request_status, [])