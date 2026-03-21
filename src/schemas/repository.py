from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl, validator


class RepositoryBase(BaseModel):
    """Base repository schema with common attributes"""
    repository_id: str = Field(..., min_length=1, max_length=64, description="Unique repository identifier")
    repository_name: str = Field(..., min_length=1, max_length=128, description="Repository name")
    repository_slug: str = Field(..., min_length=1, max_length=128, description="Repository slug")
    repository_url: HttpUrl = Field(..., description="Repository URL")
    
    @validator("repository_slug")
    def repository_slug_format(cls, v):
        """Validate repository slug format"""
        if not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError("Repository slug must contain only alphanumeric characters, hyphens, and underscores")
        return v.lower()  # Store lowercase
    
    @validator("repository_id")
    def repository_id_alphanumeric(cls, v):
        """Validate repository ID contains only alphanumeric characters and hyphens"""
        if not all(c.isalnum() or c == "-" for c in v):
            raise ValueError("Repository ID must contain only alphanumeric characters and hyphens")
        return v


class RepositoryCreate(RepositoryBase):
    """Schema for creating a new repository"""
    project_id: int = Field(..., description="Project ID the repository belongs to")
    description: Optional[str] = Field(None, max_length=500, description="Repository description")
    is_public: bool = Field(default=False, description="Whether the repository is public")
    default_branch: Optional[str] = Field(None, max_length=64, description="Default branch name (e.g., 'main', 'master')")


class RepositoryUpdate(BaseModel):
    """Schema for updating an existing repository"""
    repository_name: Optional[str] = Field(None, min_length=1, max_length=128)
    repository_slug: Optional[str] = Field(None, min_length=1, max_length=128)
    repository_url: Optional[HttpUrl] = None
    description: Optional[str] = Field(None, max_length=500)
    is_public: Optional[bool] = None
    default_branch: Optional[str] = Field(None, max_length=64)
    
    @validator("repository_slug")
    def repository_slug_format(cls, v):
        """Validate repository slug format if provided"""
        if v is not None:
            if not all(c.isalnum() or c in "-_" for c in v):
                raise ValueError("Repository slug must contain only alphanumeric characters, hyphens, and underscores")
            return v.lower()
        return v


class RepositoryResponse(RepositoryBase):
    """Schema for repository response"""
    id: int = Field(..., description="Repository database ID")
    project_id: int = Field(..., description="Project ID the repository belongs to")
    created_date: datetime = Field(..., description="Repository creation timestamp")
    updated_date: datetime = Field(..., description="Repository last update timestamp")
    
    class Config:
        """Pydantic configuration"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "project_id": 1,
                "repository_id": "repo-001",
                "repository_name": "Code Review API",
                "repository_slug": "code-review-api",
                "repository_url": "https://github.com/example/code-review-api",
                "created_date": "2023-01-01T00:00:00",
                "updated_date": "2023-01-01T00:00:00"
            }
        }


class RepositoryDetailResponse(RepositoryResponse):
    """Schema for detailed repository response with additional information"""
    description: Optional[str] = Field(None, description="Repository description")
    is_public: bool = Field(..., description="Whether the repository is public")
    default_branch: Optional[str] = Field(None, description="Default branch name")
    review_count: int = Field(default=0, description="Number of pull request reviews in this repository")
    last_review_date: Optional[datetime] = Field(None, description="Date of the last review in this repository")
    
    class Config:
        """Pydantic configuration"""
        from_attributes = True


class RepositoryListResponse(BaseModel):
    """Schema for paginated repository list response"""
    items: List[RepositoryResponse] = Field(default_factory=list, description="List of repositories")
    total: int = Field(..., description="Total number of repositories")
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
                        "project_id": 1,
                        "repository_id": "repo-001",
                        "repository_name": "Code Review API",
                        "repository_slug": "code-review-api",
                        "repository_url": "https://github.com/example/code-review-api",
                        "created_date": "2023-01-01T00:00:00",
                        "updated_date": "2023-01-01T00:00:00"
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 20
            }
        }


class RepositoryStats(BaseModel):
    """Schema for repository statistics"""
    total_repositories: int = Field(..., description="Total number of repositories")
    public_repositories: int = Field(..., description="Number of public repositories")
    private_repositories: int = Field(..., description="Number of private repositories")
    repositories_with_reviews: int = Field(..., description="Number of repositories with at least one review")
    total_reviews: int = Field(..., description="Total number of pull request reviews across all repositories")
    
    class Config:
        """Pydantic configuration"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "total_repositories": 50,
                "public_repositories": 30,
                "private_repositories": 20,
                "repositories_with_reviews": 40,
                "total_reviews": 5000
            }
        }


class RepositoryFilter(BaseModel):
    """Schema for repository filtering parameters"""
    project_id: Optional[int] = Field(None, description="Filter by project ID")
    repository_id: Optional[str] = Field(None, description="Filter by repository ID")
    repository_slug: Optional[str] = Field(None, description="Filter by repository slug")
    is_public: Optional[bool] = Field(None, description="Filter by public status")
    date_from: Optional[datetime] = Field(None, description="Filter repositories created after this date")
    date_to: Optional[datetime] = Field(None, description="Filter repositories created before this date")
    
    class Config:
        """Pydantic configuration"""
        from_attributes = True


class RepositoryInfo(BaseModel):
    """Schema for repository information used in review responses"""
    id: int = Field(..., description="Repository database ID")
    repository_id: str = Field(..., description="Repository identifier")
    repository_name: str = Field(..., description="Repository name")
    repository_slug: str = Field(..., description="Repository slug")
    repository_url: str = Field(..., description="Repository URL")
    
    class Config:
        """Pydantic configuration"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "repository_id": "repo-001",
                "repository_name": "Code Review API",
                "repository_slug": "code-review-api",
                "repository_url": "https://github.com/example/code-review-api"
            }
        }


class RepositoryWithProject(RepositoryResponse):
    """Schema for repository response with project information"""
    project_name: str = Field(..., description="Project name")
    project_key: str = Field(..., description="Project key")
    project_id: str = Field(..., description="Project identifier")
    
    class Config:
        """Pydantic configuration"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "project_id": 1,
                "repository_id": "repo-001",
                "repository_name": "Code Review API",
                "repository_slug": "code-review-api",
                "repository_url": "https://github.com/example/code-review-api",
                "created_date": "2023-01-01T00:00:00",
                "updated_date": "2023-01-01T00:00:00",
                "project_name": "Code Review System",
                "project_key": "CRS",
                "project_id": "PROJ-001"
            }
        }