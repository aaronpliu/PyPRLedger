from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator


class ReviewBase(BaseModel):
    """Base pull request review schema with common attributes"""
    pull_request_id: str = Field(..., min_length=1, max_length=64, description="Unique pull request identifier")
    project_id: int = Field(..., gt=0, description="Project ID the review belongs to")
    pull_request_user_id: int = Field(..., gt=0, description="User ID who created the pull request")
    reviewer_id: int = Field(..., gt=0, description="User ID of the reviewer")
    source_branch: str = Field(..., min_length=1, max_length=64, description="Source branch name")
    target_branch: str = Field(..., min_length=1, max_length=64, description="Target branch name")
    
    @validator("source_branch", "target_branch")
    def validate_branch_name(cls, v):
        """Validate branch name format"""
        if not all(c.isalnum() or c in "-_./" for c in v):
            raise ValueError("Branch name must contain only alphanumeric characters, hyphens, underscores, dots, and forward slashes")
        return v
    
    @validator("pull_request_id")
    def validate_pr_id(cls, v):
        """Validate pull request ID format"""
        if not all(c.isalnum() or c == "-" for c in v):
            raise ValueError("Pull request ID must contain only alphanumeric characters and hyphens")
        return v


class ReviewCreate(ReviewBase):
    """Schema for creating a new pull request review"""
    git_code_diff: Optional[str] = Field(None, max_length=1048576, description="Git code diff content")
    source_filename: Optional[str] = Field(None, max_length=255, description="Source file name")
    ai_suggestions: Optional[Dict[str, Any]] = Field(None, description="AI-generated suggestions in JSON format")
    reviewer_comments: Optional[str] = Field(None, max_length=10000, description="Reviewer's comments")
    score: Optional[int] = Field(None, ge=0, le=10, description="Review score between 0 and 10")
    pull_request_status: str = Field(default="open", description="Pull request status (open, merged, closed, draft)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata in JSON format")
    
    @validator("pull_request_status")
    def validate_status(cls, v):
        """Validate pull request status"""
        valid_statuses = {"open", "merged", "closed", "draft"}
        if v not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return v
    
    @validator("ai_suggestions", "metadata")
    def validate_json_fields(cls, v):
        """Validate JSON fields are properly formatted"""
        if v is not None and not isinstance(v, dict):
            raise ValueError("This field must be a valid JSON object")
        return v


class ReviewUpdate(BaseModel):
    """Schema for updating an existing pull request review"""
    git_code_diff: Optional[str] = Field(None, max_length=1048576)
    source_filename: Optional[str] = Field(None, max_length=255)
    ai_suggestions: Optional[Dict[str, Any]] = Field(None)
    reviewer_comments: Optional[str] = Field(None, max_length=10000)
    score: Optional[int] = Field(None, ge=0, le=10)
    pull_request_status: Optional[str] = Field(None)
    metadata: Optional[Dict[str, Any]] = Field(None)
    
    @validator("pull_request_status")
    def validate_status(cls, v):
        """Validate pull request status if provided"""
        if v is not None:
            valid_statuses = {"open", "merged", "closed", "draft"}
            if v not in valid_statuses:
                raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return v
    
    @validator("ai_suggestions", "metadata")
    def validate_json_fields(cls, v):
        """Validate JSON fields are properly formatted if provided"""
        if v is not None and not isinstance(v, dict):
            raise ValueError("This field must be a valid JSON object")
        return v


class ReviewResponse(ReviewBase):
    """Schema for pull request review response"""
    id: int = Field(..., description="Review database ID")
    git_code_diff: Optional[str] = Field(None, description="Git code diff content")
    source_filename: Optional[str] = Field(None, description="Source file name")
    ai_suggestions: Optional[Dict[str, Any]] = Field(None, description="AI-generated suggestions")
    reviewer_comments: Optional[str] = Field(None, description="Reviewer's comments")
    score: Optional[int] = Field(None, description="Review score")
    pull_request_status: str = Field(..., description="Pull request status")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    created_date: datetime = Field(..., description="Review creation timestamp")
    updated_date: datetime = Field(..., description="Review last update timestamp")
    
    class Config:
        """Pydantic configuration"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "pull_request_id": "pr-123",
                "project_id": 1,
                "pull_request_user_id": 2,
                "reviewer_id": 3,
                "source_branch": "feature/new-feature",
                "target_branch": "main",
                "git_code_diff": "diff --git a/file.py b/file.py\n...",
                "source_filename": "src/file.py",
                "ai_suggestions": {
                    "suggestion_1": "Consider using list comprehension instead of loop",
                    "suggestion_2": "Add type hints for better code clarity"
                },
                "reviewer_comments": "Overall good code, but consider the suggestions from AI",
                "score": 8,
                "pull_request_status": "open",
                "metadata": {
                    "labels": ["bugfix", "enhancement"],
                    "priority": "high"
                },
                "created_date": "2023-01-01T00:00:00",
                "updated_date": "2023-01-01T00:00:00"
            }
        }


class ReviewDetailResponse(ReviewResponse):
    """Schema for detailed pull request review response with additional information"""
    project_name: str = Field(..., description="Project name")
    pull_request_user: Dict[str, Any] = Field(..., description="Information about the user who created the pull request")
    reviewer: Dict[str, Any] = Field(..., description="Information about the reviewer")
    
    class Config:
        """Pydantic configuration"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "pull_request_id": "pr-123",
                "project_id": 1,
                "pull_request_user_id": 2,
                "reviewer_id": 3,
                "source_branch": "feature/new-feature",
                "target_branch": "main",
                "git_code_diff": "diff --git a/file.py b/file.py\n...",
                "source_filename": "src/file.py",
                "ai_suggestions": {
                    "suggestion_1": "Consider using list comprehension instead of loop",
                    "suggestion_2": "Add type hints for better code clarity"
                },
                "reviewer_comments": "Overall good code, but consider the suggestions from AI",
                "score": 8,
                "pull_request_status": "open",
                "metadata": {
                    "labels": ["bugfix", "enhancement"],
                    "priority": "high"
                },
                "created_date": "2023-01-01T00:00:00",
                "updated_date": "2023-01-01T00:00:00",
                "project_name": "Code Review System",
                "pull_request_user": {
                    "id": 2,
                    "username": "dev_user",
                    "display_name": "Developer User"
                },
                "reviewer": {
                    "id": 3,
                    "username": "reviewer_user",
                    "display_name": "Code Reviewer"
                }
            }
        }


class ReviewListResponse(BaseModel):
    """Schema for paginated pull request review list response"""
    items: List[ReviewResponse] = Field(default_factory=list, description="List of pull request reviews")
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
                        "project_id": 1,
                        "pull_request_user_id": 2,
                        "reviewer_id": 3,
                        "source_branch": "feature/new-feature",
                        "target_branch": "main",
                        "git_code_diff": "diff --git a/file.py b/file.py\n...",
                        "source_filename": "src/file.py",
                        "ai_suggestions": {
                            "suggestion_1": "Consider using list comprehension instead of loop",
                            "suggestion_2": "Add type hints for better code clarity"
                        },
                        "reviewer_comments": "Overall good code, but consider the suggestions from AI",
                        "score": 8,
                        "pull_request_status": "open",
                        "metadata": {
                            "labels": ["bugfix", "enhancement"],
                            "priority": "high"
                        },
                        "created_date": "2023-01-01T00:00:00",
                        "updated_date": "2023-01-01T00:00:00"
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 20
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
                "reviews_this_month": 400
            }
        }


class ReviewFilter(BaseModel):
    """Schema for pull request review filtering parameters"""
    pull_request_id: Optional[str] = Field(None, description="Filter by pull request ID")
    project_id: Optional[int] = Field(None, gt=0, description="Filter by project ID")
    pull_request_user_id: Optional[int] = Field(None, gt=0, description="Filter by pull request user ID")
    reviewer_id: Optional[int] = Field(None, gt=0, description="Filter by reviewer ID")
    source_branch: Optional[str] = Field(None, description="Filter by source branch")
    target_branch: Optional[str] = Field(None, description="Filter by target branch")
    status: Optional[str] = Field(None, description="Filter by pull request status (open, merged, closed, draft)")
    score_min: Optional[int] = Field(None, ge=0, le=10, description="Filter by minimum score")
    score_max: Optional[int] = Field(None, ge=0, le=10, description="Filter by maximum score")
    date_from: Optional[datetime] = Field(None, description="Filter reviews created after this date")
    date_to: Optional[datetime] = Field(None, description="Filter reviews created before this date")
    
    @validator("status")
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
                "pull_request_user_id": 2,
                "reviewer_id": 3,
                "source_branch": "feature/new-feature",
                "target_branch": "main",
                "git_code_diff": "diff --git a/file.py b/file.py\n...",
                "source_filename": "src/file.py",
                "ai_suggestions": {
                    "suggestion_1": "Consider using list comprehension instead of loop",
                    "suggestion_2": "Add type hints for better code clarity"
                },
                "reviewer_comments": "Overall good code, but consider the suggestions from AI",
                "score": 8,
                "pull_request_status": "open",
                "metadata": {
                    "labels": ["bugfix", "enhancement"],
                    "priority": "high"
                },
                "created_date": "2023-01-01T00:00:00",
                "updated_date": "2023-01-01T00:00:00",
                "project_name": "Code Review System",
                "project_key": "CRS"
            }
        }


class ReviewTransition(BaseModel):
    """Schema for pull request review status transition"""
    current_status: str = Field(..., description="Current pull request status")
    new_status: str = Field(..., description="New pull request status to transition to")
    
    @validator("current_status", "new_status")
    def validate_status(cls, v):
        """Validate status"""
        valid_statuses = {"open", "merged", "closed", "draft"}
        if v not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return v
    
    @validator("new_status")
    def validate_transition(cls, v, values):
        """Validate the status transition is valid"""
        if "current_status" in values:
            current = values["current_status"]
            valid_transitions = {
                "draft": ["open", "closed"],
                "open": ["merged", "closed"],
                "merged": [],
                "closed": ["open"]
            }
            if v not in valid_transitions.get(current, []):
                raise ValueError(f"Invalid transition from {current} to {v}")
        return v
    
    class Config:
        """Pydantic configuration"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "current_status": "open",
                "new_status": "merged"
            }
        }