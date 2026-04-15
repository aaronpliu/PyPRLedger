from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ReviewBase(BaseModel):
    """Base pull request review schema with common attributes"""

    pull_request_id: str = Field(
        ..., min_length=1, max_length=64, description="Unique pull request identifier"
    )
    pull_request_commit_id: str | None = Field(
        None,
        min_length=1,
        max_length=64,
        description="Git commit SHA/hash associated with the pull request",
    )

    # Business keys (only required fields - API caller doesn't need to pass IDs)
    project_key: str = Field(..., min_length=1, max_length=32, description="Project key")
    repository_slug: str = Field(..., min_length=1, max_length=128, description="Repository slug")
    reviewer: str | None = Field(
        None,
        min_length=1,
        max_length=64,
        description="Reviewer username (NULL for pending assignment)",
    )
    pull_request_user: str = Field(
        ..., min_length=1, max_length=64, description="Pull request user username"
    )

    source_branch: str = Field(..., min_length=1, max_length=64, description="Source branch name")
    target_branch: str = Field(..., min_length=1, max_length=64, description="Target branch name")

    @field_validator("source_branch", "target_branch")
    def validate_branch_name(cls, v):
        """Validate branch name format"""
        if not all(c.isalnum() or c in "-_./" for c in v):
            raise ValueError(
                "Branch name must contain only alphanumeric characters, hyphens, underscores, dots, and forward slashes"
            )
        return v

    @field_validator("pull_request_id")
    def validate_pr_id(cls, v):
        """Validate pull request ID format"""
        if not all(c.isalnum() or c == "-" for c in v):
            raise ValueError(
                "Pull request ID must contain only alphanumeric characters and hyphens"
            )
        return v

    @field_validator("pull_request_commit_id")
    def validate_commit_id(cls, v):
        """Validate commit ID format (hexadecimal characters)"""
        if v is not None and not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("Commit ID must contain only hexadecimal characters (0-9, a-f)")
        return v


class ReviewCreate(ReviewBase):
    """Schema for creating a new pull request review"""

    git_code_diff: str | None = Field(None, max_length=1048576, description="Git code diff content")
    source_filename: str | None = Field(
        None, max_length=255, description="Source file being reviewed (null for overall PR review)"
    )
    ai_suggestions: dict[str, Any] | None = Field(
        None, description="AI-generated suggestions in JSON format"
    )
    reviewer_comments: str | None = Field(None, max_length=10000, description="Reviewer's comments")
    pull_request_status: str = Field(
        default="open", description="Pull request status (open, merged, closed, draft)"
    )
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata in JSON format")

    @field_validator("pull_request_status")
    def validate_status(cls, v):
        """Validate pull request status"""
        valid_statuses = {"open", "merged", "closed", "draft"}
        if v not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return v

    @field_validator("ai_suggestions", "metadata")
    def validate_json_fields(cls, v):
        """Validate JSON fields are properly formatted"""
        if v is not None and not isinstance(v, dict):
            raise ValueError("This field must be a valid JSON object")
        return v


class ReviewUpdate(BaseModel):
    """Schema for updating an existing pull request review"""

    git_code_diff: str | None = Field(None, max_length=1048576)
    source_filename: str | None = Field(None, max_length=255)
    ai_suggestions: dict[str, Any] | None = Field(None)
    reviewer_comments: str | None = Field(None, max_length=10000)
    pull_request_status: str | None = Field(None)
    metadata: dict[str, Any] | None = Field(None)
    reviewer: str | None = Field(
        None,
        min_length=1,
        max_length=64,
        description="Reviewer username (can be set to assign reviewer)",
    )

    @field_validator("pull_request_status")
    def validate_status(cls, v):
        """Validate pull request status if provided"""
        if v is not None:
            valid_statuses = {"open", "merged", "closed", "draft"}
            if v not in valid_statuses:
                raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return v

    @field_validator("ai_suggestions", "metadata")
    def validate_json_fields(cls, v):
        """Validate JSON fields are properly formatted if provided"""
        if v is not None and not isinstance(v, dict):
            raise ValueError("This field must be a valid JSON object")
        return v


class ReviewScoreUpdate(BaseModel):
    """Schema for updating only the score of a pull request review"""

    project_key: str = Field(
        ..., min_length=1, max_length=64, description="Project key (e.g., 'ECOM')"
    )
    repository_slug: str = Field(
        ..., min_length=1, max_length=128, description="Repository slug (e.g., 'frontend-store')"
    )
    pull_request_id: str = Field(..., min_length=1, max_length=64, description="Pull request ID")
    source_filename: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Source filename being reviewed (e.g., 'src/services/cart.py')",
    )
    reviewer: str = Field(..., min_length=1, max_length=128, description="Reviewer username")
    score: float = Field(..., ge=0.0, le=10.0, description="Review score (0.0-10.0)")


# === Score Schemas ===


class ReviewScoreBase(BaseModel):
    """Base schema for review score"""

    score: float = Field(..., ge=0.0, le=10.0, description="Score value (0.0-10.0)")
    score_description: str | None = Field(
        None, max_length=1000, description="Auto-filled or manual description"
    )
    reviewer_comments: str | None = Field(None, description="Optional detailed feedback")


class ReviewScoreCreate(ReviewScoreBase):
    """Schema for creating/updating a score"""

    pull_request_id: str
    pull_request_commit_id: str
    project_key: str
    repository_slug: str
    source_filename: str | None = Field(
        None, description="Optional filename (None for PR-level score)"
    )
    reviewer: str

    @field_validator("score_description")
    @classmethod
    def auto_fill_description(cls, v: str | None) -> str | None:
        """Auto-fill score_description if not provided"""
        # Will be filled in service layer
        return v

    @field_validator("source_filename")
    @classmethod
    def normalize_filename(cls, v: str | None) -> str | None:
        """Normalize source filename"""
        from src.utils.score_utils import normalize_source_filename

        return normalize_source_filename(v)


class ReviewScoreResponse(ReviewScoreBase):
    """Simplified score information - excludes fields already in parent ReviewResponse"""

    id: int
    reviewer: str
    reviewer_info: dict[str, Any] | None = None  # Enriched user details
    source_filename: str | None = None  # null means PR-level score, string means file-level score
    score: float
    score_description: str | None = None
    created_date: datetime
    updated_date: datetime

    model_config = {"from_attributes": True}


class ReviewScoreSummary(BaseModel):
    """Summary of scores for a review target"""

    pull_request_id: str
    project_key: str
    repository_slug: str
    total_scores: int
    average_score: float
    max_score: float | None = Field(None, description="Maximum score when multiple scores exist")
    scores: list[ReviewScoreResponse]


class ReviewResponse(BaseModel):
    """Schema for pull request review response with full entity information"""

    id: int = Field(..., description="Review database ID")
    pull_request_id: str = Field(..., description="Pull request identifier")
    pull_request_commit_id: str | None = Field(
        None, description="Commit ID for this specific review"
    )

    # Business key fields - required top-level identifiers
    project_key: str = Field(..., min_length=1, max_length=32, description="Project key")
    repository_slug: str = Field(..., min_length=1, max_length=128, description="Repository slug")
    reviewer: str | None = Field(
        None,
        min_length=1,
        max_length=64,
        description="Reviewer username (NULL for pending assignment)",
    )
    pull_request_user: str = Field(
        ..., min_length=1, max_length=64, description="Pull request user username"
    )

    source_branch: str = Field(..., description="Source branch name")
    target_branch: str = Field(..., description="Target branch name")
    git_code_diff: str | None = Field(None, description="Git code diff content")
    source_filename: str | None = Field(
        None, description="Source file being reviewed (null for overall PR review)"
    )
    ai_suggestions: dict[str, Any] | None = Field(None, description="AI-generated suggestions")
    reviewer_comments: str | None = Field(None, description="Reviewer's comments")
    pull_request_status: str = Field(..., description="Pull request status")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")

    created_date: datetime = Field(..., description="Record creation timestamp")
    updated_date: datetime = Field(..., description="Record last update timestamp")

    # Embedded entity information - always included in response
    app_name: str = Field(
        default="Unknown",
        description="Application name this review belongs to (resolved from project registry)",
    )
    project: dict[str, Any] | None = Field(None, description="Full project information")
    repository: dict[str, Any] | None = Field(None, description="Full repository information")
    pull_request_user_info: dict[str, Any] | None = Field(
        None, description="Full information about PR author"
    )
    reviewer_info: dict[str, Any] | None = Field(
        None, description="Full information about reviewer"
    )

    # Score summary - includes aggregated stats and individual scores
    score_summary: ReviewScoreSummary | None = Field(
        None, description="Aggregated score statistics including all reviewer scores"
    )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": 1,
                "pull_request_id": "pr-123",
                "pull_request_commit_id": "abc123def456",
                "project_key": "PROJ",
                "repository_slug": "my-repo",
                "reviewer": "john_doe",
                "pull_request_user": "jane_smith",
                "source_branch": "feature/new-feature",
                "target_branch": "main",
                "git_code_diff": "diff --git a/file.py b/file.py\n...",
                "source_filename": "src/file.py",
                "ai_suggestions": {
                    "suggestion_1": "Consider using list comprehension instead of loop",
                    "suggestion_2": "Add type hints for better code clarity",
                },
                "reviewer_comments": "Overall good code, but consider the suggestions from AI",
                "pull_request_status": "open",
                "metadata": {"labels": ["bugfix", "enhancement"], "priority": "high"},
                "created_date": "2023-01-01T10:00:00",
                "updated_date": "2023-01-01T12:00:00",
                "app_name": "member",
                "project": {
                    "id": 1,
                    "project_id": 1234,
                    "project_name": "Code Review System",
                    "project_key": "PROJ",
                    "project_url": "https://bitbucket.org/company/proj",
                    "created_date": "2023-01-01T00:00:00",
                    "updated_date": "2023-01-01T00:00:00",
                },
                "repository": {
                    "id": 1,
                    "repository_id": 5678,
                    "repository_name": "Code Review API",
                    "repository_slug": "my-repo",
                    "repository_url": "https://bitbucket.org/company/proj/my-repo",
                    "created_date": "2023-01-01T00:00:00",
                    "updated_date": "2023-01-01T00:00:00",
                },
                "pull_request_user_info": {
                    "id": 2,
                    "user_id": 1002,
                    "username": "jane_smith",
                    "display_name": "Jane Smith",
                    "email_address": "jane@example.com",
                    "active": True,
                    "is_reviewer": False,
                    "created_date": "2023-01-01T00:00:00",
                    "updated_date": "2023-01-01T00:00:00",
                },
                "reviewer_info": {
                    "id": 3,
                    "user_id": 1003,
                    "username": "john_doe",
                    "display_name": "John Doe",
                    "email_address": "john@example.com",
                    "active": True,
                    "is_reviewer": True,
                    "created_date": "2023-01-01T00:00:00",
                    "updated_date": "2023-01-01T00:00:00",
                },
                "score_summary": {
                    "pull_request_id": "pr-123",
                    "project_key": "PROJ",
                    "repository_slug": "my-repo",
                    "source_filename": "src/file.py",
                    "total_scores": 2,
                    "average_score": 8.5,
                    "scores": [],
                },
            }
        },
    }


class ReviewListResponse(BaseModel):
    """Schema for paginated pull request review list response"""

    items: list[ReviewResponse] = Field(
        default_factory=list, description="List of pull request reviews with embedded entity data"
    )
    total: int = Field(..., description="Total number of reviews")
    page: int = Field(default=1, ge=1, description="Current page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Number of items per page")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "items": [
                    {
                        "id": 1,
                        "pull_request_id": "pr-123",
                        "project_key": "PROJ",
                        "repository_slug": "my-repo",
                        "reviewer": "john_doe",
                        "pull_request_user": "jane_smith",
                        "source_branch": "feature/new-feature",
                        "target_branch": "main",
                        "git_code_diff": "diff --git a/file.py b/file.py\n...",
                        "source_filename": "src/file.py",
                        "ai_suggestions": {
                            "suggestion_1": "Consider using list comprehension instead of loop",
                            "suggestion_2": "Add type hints for better code clarity",
                        },
                        "reviewer_comments": "Overall good code, but consider the suggestions from AI",
                        "pull_request_status": "open",
                        "metadata": {"labels": ["bugfix", "enhancement"], "priority": "high"},
                        "created_date": "2023-01-01T00:00:00",
                        "updated_date": "2023-01-01T00:00:00",
                        "project": {
                            "id": 1,
                            "project_id": 1234,
                            "project_name": "Code Review System",
                            "project_key": "PROJ",
                            "project_url": "https://bitbucket.org/company/proj",
                            "created_date": "2023-01-01T00:00:00",
                            "updated_date": "2023-01-01T00:00:00",
                        },
                        "repository": {
                            "id": 1,
                            "repository_id": 5678,
                            "repository_name": "Code Review API",
                            "repository_slug": "my-repo",
                            "repository_url": "https://bitbucket.org/company/proj/my-repo",
                            "created_date": "2023-01-01T00:00:00",
                            "updated_date": "2023-01-01T00:00:00",
                        },
                        "pull_request_user_info": {
                            "id": 2,
                            "user_id": 1002,
                            "username": "jane_smith",
                            "display_name": "Jane Smith",
                            "email_address": "jane@example.com",
                            "active": True,
                            "is_reviewer": False,
                            "created_date": "2023-01-01T00:00:00",
                            "updated_date": "2023-01-01T00:00:00",
                        },
                        "reviewer_info": {
                            "id": 3,
                            "user_id": 1003,
                            "username": "john_doe",
                            "display_name": "John Doe",
                            "email_address": "john@example.com",
                            "active": True,
                            "is_reviewer": True,
                            "created_date": "2023-01-01T00:00:00",
                            "updated_date": "2023-01-01T00:00:00",
                        },
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 20,
            }
        },
    }


class ReviewStats(BaseModel):
    """Schema for pull request review statistics"""

    total_reviews: int = Field(..., description="Total number of pull request reviews")
    open_reviews: int = Field(..., description="Number of open pull requests")
    merged_reviews: int = Field(..., description="Number of merged pull requests")
    closed_reviews: int = Field(..., description="Number of closed pull requests")
    average_score: float = Field(..., description="Average review score")
    reviews_today: int = Field(..., description="Number of reviews created today")
    reviews_this_week: int = Field(..., description="Number of reviews created this week")
    reviews_this_month: int = Field(..., description="Number of reviews created this month")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "total_reviews": 1000,
                "open_reviews": 50,
                "merged_reviews": 850,
                "closed_reviews": 100,
                "average_score": 7.5,
                "reviews_today": 20,
                "reviews_this_week": 100,
                "reviews_this_month": 400,
            }
        },
    }


class ReviewFilter(BaseModel):
    """Schema for pull request review filtering parameters"""

    pull_request_id: str | None = Field(None, description="Filter by pull request ID")
    project_key: str | None = Field(
        None, min_length=1, max_length=32, description="Filter by project key"
    )
    repository_slug: str | None = Field(
        None, min_length=1, max_length=128, description="Filter by repository slug"
    )
    pull_request_user: str | None = Field(
        None, min_length=1, max_length=64, description="Filter by pull request user username"
    )
    reviewer: str | None = Field(
        None, min_length=1, max_length=64, description="Filter by reviewer username"
    )
    source_branch: str | None = Field(None, description="Filter by source branch")
    target_branch: str | None = Field(None, description="Filter by target branch")
    pull_request_status: str | None = Field(
        None, description="Filter by pull request status (open, merged, closed, draft)"
    )
    pull_request_commit_id: str | None = Field(
        None, description="Filter by commit ID (supports prefix matching)"
    )
    score_min: float | None = Field(None, ge=0.0, le=10.0, description="Filter by minimum score")
    score_max: float | None = Field(None, ge=0.0, le=10.0, description="Filter by maximum score")
    date_from: datetime | None = Field(None, description="Filter reviews created after this date")
    date_to: datetime | None = Field(None, description="Filter reviews created before this date")
    visible_to_username: str | None = Field(
        None,
        min_length=1,
        max_length=64,
        description="Filter reviews assigned to or raised by this username",
    )

    @field_validator("pull_request_status")
    def validate_status(cls, v):
        """Validate status if provided"""
        if v is not None:
            valid_statuses = {"open", "merged", "closed", "draft"}
            if v not in valid_statuses:
                raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return v

    model_config = {"from_attributes": True}


class ReviewWithProject(ReviewResponse):
    """Schema for pull request review response with project information"""

    project_name: str = Field(..., description="Project name")
    project_key: str = Field(..., description="Project key")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": 1,
                "pull_request_id": "pr-123",
                "project_id": 1,
                "repository_id": 1,
                "pull_request_user_id": 2,
                "reviewer_id": 3,
                "source_branch": "feature/new-feature",
                "target_branch": "main",
                "git_code_diff": "diff --git a/file.py b/file.py\n...",
                "source_filename": "src/file.py",
                "ai_suggestions": {
                    "suggestion_1": "Consider using list comprehension instead of loop",
                    "suggestion_2": "Add type hints for better code clarity",
                },
                "reviewer_comments": "Overall good code, but consider the suggestions from AI",
                "pull_request_status": "open",
                "metadata": {"labels": ["bugfix", "enhancement"], "priority": "high"},
                "created_date": "2023-01-01T00:00:00",
                "updated_date": "2023-01-01T00:00:00",
                "project_name": "Code Review System",
                "project_key": "CRS",
            }
        },
    }


class ReviewTransition(BaseModel):
    """Schema for pull request review status transition"""

    current_status: str = Field(..., description="Current pull request status")
    new_status: str = Field(..., description="New pull request status to transition to")

    @field_validator("current_status", "new_status")
    def validate_status(cls, v):
        """Validate status"""
        valid_statuses = {"open", "merged", "closed", "draft"}
        if v not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return v

    @field_validator("new_status")
    def validate_transition(cls, v, values):
        """Validate the status transition is valid"""
        if "current_status" in values:
            current = values["current_status"]
            valid_transitions = {
                "draft": ["open", "closed"],
                "open": ["merged", "closed"],
                "merged": [],
                "closed": ["open"],
            }
            if v not in valid_transitions.get(current, []):
                raise ValueError(f"Invalid transition from {current} to {v}")
        return v

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {"example": {"current_status": "open", "new_status": "merged"}},
    }


class ReviewAssignmentRequest(BaseModel):
    """Schema for assigning review task to a reviewer"""

    pull_request_id: str = Field(..., description="Pull request ID")
    project_key: str = Field(..., min_length=1, max_length=32, description="Project key")
    repository_slug: str = Field(..., min_length=1, max_length=128, description="Repository slug")
    assignee_username: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Reviewer username to assign",
    )
    pull_request_user: str = Field(
        ..., min_length=1, max_length=64, description="PR author username"
    )
    source_branch: str = Field(..., min_length=1, description="Source branch")
    target_branch: str = Field(..., min_length=1, description="Target branch")
    pull_request_commit_id: str | None = Field(None, description="Commit ID (optional)")
    git_code_diff: str | None = Field(None, description="Git code diff content (optional)")
    ai_suggestions: dict[str, Any] | None = Field(None, description="AI suggestions (optional)")
    reviewer_comments: str | None = Field(None, description="Reviewer comments (optional)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "pull_request_id": "123",
                "project_key": "PROJ",
                "repository_slug": "my-repo",
                "assignee_username": "john_doe",
                "pull_request_user": "jane_smith",
                "source_branch": "feature/new-feature",
                "target_branch": "main",
            }
        }
    }
