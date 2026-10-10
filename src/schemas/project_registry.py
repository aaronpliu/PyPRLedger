from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectRegistryResponse(BaseModel):
    id: int
    app_name: str
    app_alias: str | None = Field(
        default=None,
        description=(
            "The name the dependency database knows this application as, when that differs "
            "from app_name. Empty means the application name is used"
        ),
    )
    registry_kind: str = Field(
        default="application",
        description=(
            "'application' for a repository whose releases the dependency database holds, "
            "'package' for one that is only a dependency of another. The pages that read an "
            "application's releases offer the first alone: a package repository has no "
            "release records to read"
        ),
    )
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
