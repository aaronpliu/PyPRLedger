from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl, field_validator


class ProjectBase(BaseModel):
    """Base project schema with common attributes"""

    project_id: int = Field(..., description="Unique project business identifier (integer)")
    project_name: str = Field(..., min_length=1, max_length=128, description="Project name")
    project_key: str = Field(..., min_length=1, max_length=32, description="Unique project key")
    project_url: HttpUrl = Field(..., description="Project URL")

    @field_validator("project_key")
    def project_key_uppercase(cls, v):
        """Validate project key is uppercase"""
        return v.upper()


class ProjectCreate(ProjectBase):
    """Schema for creating a new project"""

    description: Optional[str] = Field(None, max_length=500, description="Project description")
    is_active: bool = Field(default=True, description="Whether the project is active")


class ProjectUpdate(BaseModel):
    """Schema for updating an existing project"""

    project_name: Optional[str] = Field(None, min_length=1, max_length=128)
    project_url: Optional[HttpUrl] = None
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class ProjectResponse(ProjectBase):
    """Schema for project response"""

    id: int = Field(..., description="Project database ID")
    created_date: datetime = Field(..., description="Project creation timestamp")
    updated_date: datetime = Field(..., description="Project last update timestamp")

    class Config:
        """Pydantic configuration"""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "project_id": 1234,
                "project_name": "AI Code Review Result Storage System",
                "project_key": "CRS",
                "project_url": "https://github.com/example/code-review",
                "created_date": "2026-01-01T00:00:00",
                "updated_date": "2026-01-01T00:00:00",
            }
        }


class ProjectDetailResponse(ProjectResponse):
    """Schema for detailed project response with additional information"""

    description: Optional[str] = Field(None, description="Project description")
    is_active: bool = Field(..., description="Whether the project is active")
    repository_count: int = Field(default=0, description="Number of repositories in the project")
    review_count: int = Field(default=0, description="Number of pull request reviews")
    active_reviewer_count: int = Field(default=0, description="Number of active reviewers")

    class Config:
        """Pydantic configuration"""

        from_attributes = True


class ProjectListResponse(BaseModel):
    """Schema for paginated project list response"""

    items: List[ProjectResponse] = Field(default_factory=list, description="List of projects")
    total: int = Field(..., description="Total number of projects")
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
                        "project_id": 1234,
                        "project_name": "AI Code Review Result Storage System",
                        "project_key": "CRS",
                        "project_url": "https://github.com/example/code-review",
                        "created_date": "2026-01-01T00:00:00",
                        "updated_date": "2026-01-01T00:00:00",
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 20,
            }
        }


class ProjectStats(BaseModel):
    """Schema for project statistics"""

    total_projects: int = Field(..., description="Total number of projects")
    active_projects: int = Field(..., description="Number of active projects")
    total_repositories: int = Field(
        ..., description="Total number of repositories across all projects"
    )
    total_reviews: int = Field(..., description="Total number of pull request reviews")

    class Config:
        """Pydantic configuration"""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "total_projects": 50,
                "active_projects": 45,
                "total_repositories": 120,
                "total_reviews": 5000,
            }
        }


class ProjectFilter(BaseModel):
    """Schema for project filtering parameters"""

    project_id: Optional[str] = Field(None, description="Filter by project ID")
    project_key: Optional[str] = Field(None, description="Filter by project key")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    date_from: Optional[datetime] = Field(
        None, description="Filter projects created after this date"
    )
    date_to: Optional[datetime] = Field(
        None, description="Filter projects created before this date"
    )

    class Config:
        """Pydantic configuration"""

        from_attributes = True
