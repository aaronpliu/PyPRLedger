"""Schemas for release notes (version releases)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from src.core.git_provider import GitProvider


MAX_BODY_LENGTH = 60000


class ReleaseNoteCoordinates(BaseModel):
    """Repository coordinates shared by the release note endpoints."""

    project_key: str = Field(..., min_length=1, max_length=32, description="Project key")
    repository_slug: str = Field(..., min_length=1, max_length=128, description="Repository slug")
    workspace_slug: str | None = Field(
        default=None,
        max_length=128,
        description="Bitbucket Cloud workspace (falls back to the project key)",
    )
    git_provider: str | None = Field(
        default=None,
        description=(
            "Git provider override. Defaults to the configured default provider "
            "(bitbucket_server / bitbucket_cloud / github_enterprise)."
        ),
    )

    @field_validator("git_provider")
    def validate_git_provider(cls, v: str | None) -> str | None:
        if v is not None and not GitProvider.is_valid(v):
            raise ValueError(
                f"Invalid git_provider '{v}'. Must be one of: "
                f"{', '.join(sorted(GitProvider.values()))}"
            )
        return v


class ReleaseNoteCreateRequest(ReleaseNoteCoordinates):
    """Payload for creating (drafting or publishing) a version release."""

    tag_name: str = Field(..., min_length=1, max_length=255, description="Git tag / version")
    name: str | None = Field(
        default=None,
        max_length=255,
        description="Release title. Defaults to the tag name when omitted.",
    )
    body: str = Field(
        default="", max_length=MAX_BODY_LENGTH, description="Release notes (markdown)"
    )
    previous_tag: str | None = Field(
        default=None,
        max_length=255,
        description="Previous version, used by the note generator and for the changelog link",
    )
    status: str = Field(default="draft", description="draft or published")
    is_prerelease: bool = Field(default=False, description="Mark the version as a pre-release")

    @field_validator("status")
    def validate_status(cls, v: str) -> str:
        if v not in ("draft", "published"):
            raise ValueError("status must be one of: draft, published")
        return v


class ReleaseNoteUpdateRequest(BaseModel):
    """Payload for updating an existing release."""

    name: str | None = Field(default=None, max_length=255)
    body: str | None = Field(default=None, max_length=MAX_BODY_LENGTH)
    previous_tag: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, description="draft or published")
    is_prerelease: bool | None = Field(default=None)

    @field_validator("status")
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ("draft", "published"):
            raise ValueError("status must be one of: draft, published")
        return v


class ReleaseNoteResponse(BaseModel):
    """A single version release."""

    id: int
    project_key: str
    repository_slug: str
    tag_name: str
    name: str
    body: str
    previous_tag: str | None = None
    status: str
    is_prerelease: bool
    is_latest: bool = Field(default=False, description="Latest published, non pre-release version")
    author: str | None = None
    published_date: datetime | None = None
    created_date: datetime | None = None
    updated_date: datetime | None = None

    # Provider side release (set when pushed to / imported from GitHub Enterprise)
    external_provider: str | None = Field(
        default=None, description="Provider holding the published release"
    )
    external_id: str | None = Field(default=None, description="Provider side release id")
    external_url: str | None = Field(default=None, description="Provider side release url")

    model_config = {"from_attributes": True}


class ReleaseNoteListResponse(BaseModel):
    """Release list for one repository (newest first)."""

    total: int
    items: list[ReleaseNoteResponse]


class ReleaseNotePreviewRequest(ReleaseNoteCoordinates):
    """Generate release notes for a version from the commits of its release scope."""

    version: str = Field(..., min_length=1, max_length=255, description="Version being released")
    previous_version: str | None = Field(
        default=None,
        max_length=255,
        description="Previous version; every commit after it belongs to this release",
    )
    max_commits: int = Field(default=500, ge=1, le=5000)
    include_authors: bool = Field(default=True)

    @model_validator(mode="after")
    def validate_versions(self) -> ReleaseNotePreviewRequest:
        if self.previous_version and self.previous_version.strip() == self.version.strip():
            raise ValueError("previous_version must differ from version")
        return self


class ReleaseNotePushRequest(ReleaseNoteCoordinates):
    """Publish a release to the git provider (GitHub Enterprise Releases)."""

    target_commitish: str | None = Field(
        default=None,
        max_length=255,
        description="Branch/commit the tag is created from when the tag does not exist yet",
    )
    update_existing: bool = Field(
        default=True,
        description="Update the provider release when the tag already has one",
    )


class ReleaseNoteImportRequest(ReleaseNoteCoordinates):
    """Import the releases of a repository from the git provider."""

    limit: int = Field(default=50, ge=1, le=200)
    overwrite: bool = Field(
        default=False,
        description="Also refresh releases that already exist locally (notes/title/flags)",
    )


class ReleaseNoteImportResponse(BaseModel):
    """Result of a provider import."""

    imported: int = Field(default=0, description="Newly created releases")
    updated: int = Field(default=0, description="Existing releases refreshed")
    skipped: int = Field(default=0, description="Provider releases ignored")
    items: list[ReleaseNoteResponse] = Field(default_factory=list)


class ReleaseNotePreviewResponse(BaseModel):
    """Generated release notes (markdown) plus the commits they were built from."""

    version: str
    previous_version: str | None = None
    suggested_name: str
    body: str
    commit_count: int
    commits: list[dict[str, Any]] = Field(default_factory=list)
    truncated: bool = False
