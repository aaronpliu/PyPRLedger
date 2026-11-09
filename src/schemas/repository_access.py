"""Schemas for the explicit user-to-repository visibility grants."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RepositoryAccessItem(BaseModel):
    """One repository a subject is allowed to see."""

    project_key: str = Field(..., min_length=1, max_length=32, description="Project key")
    repository_slug: str = Field(
        ..., min_length=1, max_length=128, description="Repository slug within the project"
    )


class RepositoryAccessReplaceRequest(BaseModel):
    """Replace the complete grant list of one subject."""

    items: list[RepositoryAccessItem] = Field(
        default_factory=list, description="Complete list of granted repositories"
    )
    reason: str | None = Field(None, max_length=255, description="Reason recorded in the audit log")


class RepositoryAccessResponse(BaseModel):
    """The grants currently held by one subject."""

    subject_type: str
    subject_id: int
    subject_username: str | None
    items: list[dict]
    total: int


class RepositoryCatalogItem(BaseModel):
    """A registered repository, without any business data."""

    project_key: str
    repository_slug: str
    app_name: str | None = None
