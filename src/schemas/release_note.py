"""Schemas for release notes (version releases)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from src.core.git_provider import GitProvider


MAX_BODY_LENGTH = 60000


# How the release scope base of a tag was obtained.
#
# ``ancestor`` is the only resolved value that was *proven* (the base is an
# ancestor of the released ref); ``name_order`` is inferred from the tag order.
SOURCE_EXPLICIT = "explicit"
SOURCE_ANCESTOR = "ancestor"
SOURCE_NAME_ORDER = "name_order"
SOURCE_NONE = "none"

# Why a scope looks the way it does.
#
# ``first_release`` and ``unresolved`` are the two cases where the commits come
# from the whole history reachable from the version instead of a release scope:
# the tag has no predecessor, or its predecessor could not be determined.
REASON_PROVIDED = "provided"
REASON_RESOLVED = "resolved"
REASON_FIRST_RELEASE = "first_release"
REASON_UNRESOLVED = "unresolved"

# Where the prose of a generated note came from.
#
# ``deterministic`` is the grouping derived from the commit subjects alone, which
# needs no configuration; ``llm`` adds the summary paragraph the model wrote. A
# caller that asked for a summary but could not get one is answered with
# ``deterministic`` - the notes are never withheld for the sake of the AI pass.
SUMMARY_DETERMINISTIC = "deterministic"
SUMMARY_LLM = "llm"


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
    author_avatar_url: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Profile picture of the author, resolved from the local account. "
            "Null when the author is unknown locally or has no avatar."
        ),
    )
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
        description=(
            "Previous version; every commit after it belongs to this release. Leave it out "
            "to let the server resolve the predecessor from the repository's tags."
        ),
    )
    max_commits: int = Field(
        default=500,
        ge=1,
        le=5000,
        description="Cap for the returned commit list (and for the scan behind it)",
    )
    include_authors: bool = Field(default=True)
    refresh: bool = Field(
        default=False,
        description=(
            "Re-resolve the release scope instead of reusing the cached resolution, for when "
            "a tag has just been created or moved"
        ),
    )
    language: str | None = Field(
        default=None,
        max_length=16,
        description=(
            "Language of the generated prose (section titles and the summary), e.g. "
            "'en', 'zh-CN', 'zh-TW'. Defaults to English."
        ),
    )
    summarize: bool = Field(
        default=False,
        description=(
            "Also ask the configured LLM for a summary paragraph and for a section per "
            "commit. Ignored - the notes stay deterministic - when no LLM is configured "
            "or the call fails."
        ),
    )

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
    previous_version: str | None = Field(
        default=None,
        description=(
            "Release scope base: what the caller supplied, or the predecessor the server "
            "resolved from the repository's tags"
        ),
    )
    previous_sha: str | None = Field(
        default=None, description="Revision the scope base was pinned to (when known)"
    )
    version_sha: str | None = Field(
        default=None, description="Revision the released ref was pinned to (when known)"
    )
    previous_source: str = Field(
        default=SOURCE_NONE,
        description="How the base was obtained: 'explicit' | 'ancestor' | 'name_order' | 'none'",
    )
    previous_verified: bool = Field(
        default=False,
        description=(
            "True only for a caller-supplied base or one proven to be an ancestor; a base "
            "inferred from the tag order is reported as unverified"
        ),
    )
    scope_reason: str = Field(
        default=REASON_UNRESOLVED,
        description=(
            "'provided' | 'resolved' | 'first_release' | 'unresolved'. The last two mean the "
            "commits come from the history reachable from the version rather than from a "
            "release scope - a statement about the scope, never about the repository size"
        ),
    )
    suggested_name: str
    body: str
    commit_count: int = Field(
        description=(
            "Size of the release scope: exact when it was resolved completely, a lower bound "
            "when a scan or the history listing hit its cap"
        )
    )
    commits: list[dict[str, Any]] = Field(default_factory=list)
    truncated: bool = Field(
        default=False,
        description="True when the returned commits are only part of that scope",
    )
    summary: str | None = Field(
        default=None,
        description="Summary paragraph of the release, when one was written for it",
    )
    summary_source: str = Field(
        default=SUMMARY_DETERMINISTIC,
        description=(
            "'deterministic' | 'llm': whether the prose was derived from the commit subjects "
            "alone or was written by the configured LLM"
        ),
    )
