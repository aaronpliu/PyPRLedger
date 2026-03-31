from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


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
    reviewer: str = Field(..., min_length=1, max_length=64, description="Reviewer username")
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
    score: float | None = Field(None, ge=0.0, le=10.0, description="Review score (0.0-10.0)")
    pull_request_status: str = Field(
        default="open", description="Pull request status (open, merged, closed, draft)"
    )
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata in JSON format")

    # Optional field to specify when the review was completed (defaults to now)
    reviewed_date: datetime | None = Field(
        None, description="When the review was completed (defaults to current time)"
    )

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

    @field_validator("reviewed_date")
    def validate_reviewed_date(cls, v):
        """Validate reviewed_date is timezone-aware or convert to UTC"""
        if v is not None:
            # If naive datetime, make it timezone-aware (assume UTC)
            if v.tzinfo is None:
                v = v.replace(tzinfo=UTC)
        return v


class ReviewUpdate(BaseModel):
    """Schema for updating an existing pull request review"""

    git_code_diff: str | None = Field(None, max_length=1048576)
    source_filename: str | None = Field(None, max_length=255)
    ai_suggestions: dict[str, Any] | None = Field(None)
    reviewer_comments: str | None = Field(None, max_length=10000)
    score: float | None = Field(None, ge=0.0, le=10.0)
    pull_request_status: str | None = Field(None)
    metadata: dict[str, Any] | None = Field(None)

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

    score: float = Field(..., ge=0.0, le=10.0, description="Review score (0.0-10.0)")


from pydantic import BaseModel, Field, field_validator, model_serializer


class ReviewResponse(BaseModel):
    """Schema for pull request review response with full entity information"""

    id: int = Field(..., description="Review database ID")
    pull_request_id: str = Field(..., description="Pull request identifier")
    pull_request_commit_id: str | None = Field(
        None, description="Commit ID for this specific review"
    )
    repository_slug: str = Field(..., description="Repository slug")
    source_branch: str = Field(..., description="Source branch name")
    target_branch: str = Field(..., description="Target branch name")
    git_code_diff: str | None = Field(None, description="Git code diff content")
    source_filename: str | None = Field(
        None, description="Source file being reviewed (null for overall PR review)"
    )
    ai_suggestions: dict[str, Any] | None = Field(None, description="AI-generated suggestions")
    reviewer_comments: str | None = Field(None, description="Reviewer's comments")
    score: float | None = Field(None, ge=0.0, le=10.0, description="Review score (0.0-10.0)")
    pull_request_status: str = Field(..., description="Pull request status")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")

    # Review tracking fields
    reviewed_date: datetime = Field(..., description="When the review was completed")
    is_latest_review: bool = Field(
        True, description="Whether this is the latest review for this file"
    )
    review_iteration: int = Field(1, description="Review iteration number (1st, 2nd, etc.)")

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

    class Config:
        """Pydantic configuration"""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "pull_request_id": "pr-123",
                "pull_request_commit_id": "abc123def456",
                "repository_slug": "code-review",
                "app_name": "member",  # NEW: Virtual field from registry
                "source_branch": "feature/new-feature",
                "target_branch": "main",
                "git_code_diff": "diff --git a/file.py b/file.py\n...",
                "source_filename": "src/file.py",
                "ai_suggestions": {
                    "suggestion_1": "Consider using list comprehension instead of loop",
                    "suggestion_2": "Add type hints for better code clarity",
                },
                "reviewer_comments": "Overall good code, but consider the suggestions from AI",
                "score": 8.5,
                "pull_request_status": "open",
                "metadata": {"labels": ["bugfix", "enhancement"], "priority": "high"},
                "reviewed_date": "2023-01-01T12:00:00Z",
                "is_latest_review": True,
                "review_iteration": 1,
                "created_date": "2023-01-01T10:00:00",
                "updated_date": "2023-01-01T12:00:00",
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
                    "repository_slug": "code-review",
                    "repository_url": "https://bitbucket.org/company/proj/code-review",
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
        }

    @model_validator(mode="before")
    @classmethod
    def remove_duplicate_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        """
        Remove duplicate fields from ORM/dict input to avoid redundancy.

        The following fields are removed because they're duplicated in nested objects:
        - project_key (available in project.project_key)
        - reviewer (available in reviewer_info.username)
        - pull_request_user (available in pull_request_user_info.username)

        Args:
            values: Input values from ORM or dict

        Returns:
            Filtered values without duplicate fields
        """
        # Create a copy to avoid modifying the original
        filtered_values = values.copy()

        # Remove duplicate fields - they're available in nested objects
        filtered_values.pop("project_key", None)
        filtered_values.pop("reviewer", None)
        filtered_values.pop("pull_request_user", None)

        return filtered_values

    @model_serializer(mode="wrap")
    def serialize_with_exclusions(self, handler):
        """
        Customize serialization to exclude duplicate fields.

        This ensures that even if duplicate fields somehow make it into the model,
        they won't appear in the serialized output.

        Args:
            handler: The default serializer handler

        Returns:
            Serialized dict without duplicate fields
        """
        data = handler(self)

        # Explicitly remove any duplicate fields from output
        data.pop("project_key", None)
        data.pop("reviewer", None)
        data.pop("pull_request_user", None)

        return data


class ReviewListResponse(BaseModel):
    """Schema for paginated pull request review list response"""

    items: list[ReviewResponse] = Field(
        default_factory=list, description="List of pull request reviews with embedded entity data"
    )
    total: int = Field(..., description="Total number of reviews")
    page: int = Field(default=1, ge=1, description="Current page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Number of items per page")

    class Config:
        """Pydantic configuration"""

        from_attributes = True
        json_schema_extra = {
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
                        "score": 8,
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

    class Config:
        """Pydantic configuration"""

        from_attributes = True
        json_schema_extra = {
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
    score_min: float | None = Field(None, ge=0.0, le=10.0, description="Filter by minimum score")
    score_max: float | None = Field(None, ge=0.0, le=10.0, description="Filter by maximum score")
    date_from: datetime | None = Field(None, description="Filter reviews created after this date")
    date_to: datetime | None = Field(None, description="Filter reviews created before this date")

    @field_validator("pull_request_status")
    def validate_status(cls, v):
        """Validate status if provided"""
        if v is not None:
            valid_statuses = {"open", "merged", "closed", "draft"}
            if v not in valid_statuses:
                raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return v

    class Config:
        """Pydantic configuration"""

        from_attributes = True


class ReviewWithProject(ReviewResponse):
    """Schema for pull request review response with project information"""

    project_name: str = Field(..., description="Project name")
    project_key: str = Field(..., description="Project key")

    class Config:
        """Pydantic configuration"""

        from_attributes = True
        json_schema_extra = {
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
                "score": 8,
                "pull_request_status": "open",
                "metadata": {"labels": ["bugfix", "enhancement"], "priority": "high"},
                "created_date": "2023-01-01T00:00:00",
                "updated_date": "2023-01-01T00:00:00",
                "project_name": "Code Review System",
                "project_key": "CRS",
            }
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

    class Config:
        """Pydantic configuration"""

        from_attributes = True
        json_schema_extra = {"example": {"current_status": "open", "new_status": "merged"}}
