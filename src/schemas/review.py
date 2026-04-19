"""Schemas for multi-reviewer review system"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReviewBaseResponse(BaseModel):
    """Base review information from PullRequestReviewBase"""

    id: int
    pull_request_id: str
    pull_request_commit_id: str | None = None
    project_key: str
    repository_slug: str
    app_name: str | None = None  # Virtual column resolved from project registry
    pull_request_user: str
    pull_request_user_info: dict[str, Any] | None = None
    source_filename: str | None = None
    source_branch: str
    target_branch: str
    git_code_diff: str | None = None
    ai_suggestions: dict[str, Any] | None = None
    pull_request_status: str
    metadata: dict[str, Any] | None = None
    created_date: datetime
    updated_date: datetime

    # Embedded project information for PR URL generation
    project: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class ReviewerAssignmentResponse(BaseModel):
    """Reviewer assignment information from PullRequestReviewAssignment"""

    id: int
    reviewer: str
    reviewer_info: dict[str, Any] | None = None  # Enriched user details
    assigned_by: str | None = None
    assigned_by_info: dict[str, Any] | None = None  # Enriched assigner details
    assigned_date: datetime | None = None
    assignment_status: str = "pending"
    reviewer_comments: str | None = None
    created_date: datetime
    updated_date: datetime

    model_config = {"from_attributes": True}


class ReviewWithAssignmentsResponse(ReviewBaseResponse):
    """Complete review with all reviewer assignments"""

    reviewers: list[ReviewerAssignmentResponse] = []
    total_reviewers: int = 0
    completed_reviewers: int = 0
    pending_reviewers: int = 0

    model_config = {"from_attributes": True}


class ReviewListResponse(BaseModel):
    """Response for review list endpoint"""

    items: list[ReviewWithAssignmentsResponse]
    total: int
    page: int
    page_size: int


class AssignReviewerRequest(BaseModel):
    """Request schema for assigning a reviewer"""

    reviewer: str = Field(..., min_length=1, max_length=64, description="Reviewer username")
    assignment_status: str = Field(
        default="assigned",
        description="Initial assignment status (pending, assigned, in_progress)",
    )


class UpdateAssignmentStatusRequest(BaseModel):
    """Request schema for updating assignment status"""

    assignment_status: str = Field(
        ..., description="New status (pending, assigned, in_progress, completed)"
    )
    reviewer_comments: str | None = Field(None, description="Optional comments")
