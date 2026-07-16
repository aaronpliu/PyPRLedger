from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectRegistryResponse(BaseModel):
    id: int
    app_name: str
    project_key: str
    repository_slug: str
    git_provider: str
    description: str | None = None
    created_date: str
    updated_date: str

    model_config = {"from_attributes": True}


class ProjectRegistryListResponse(BaseModel):
    items: list[ProjectRegistryResponse] = Field(
        default_factory=list, description="List of project registry entries"
    )
    total: int = Field(..., description="Total number of entries matching the filter")
    page: int = Field(default=1, ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Number of items per page")
