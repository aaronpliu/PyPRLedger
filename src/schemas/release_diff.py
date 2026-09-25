"""Schemas for release diff (compare / check) endpoints.

These models describe request/response payloads for comparing two release
refs (tags/branches/commits) and for checking whether specific commits are
contained in a target release.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class CommitInfo(BaseModel):
    """Normalized commit representation across git providers."""

    id: str = Field(..., description="Full commit SHA")
    display_id: str | None = Field(default=None, description="Short commit SHA")
    author_name: str | None = Field(default=None, description="Author display name")
    author_email: str | None = Field(default=None, description="Author email address")
    author_timestamp: int | None = Field(
        default=None, description="Author timestamp in milliseconds since epoch"
    )
    message: str | None = Field(default=None, description="Full commit message")
    url: str | None = Field(default=None, description="Web URL of the commit")

    model_config = {"from_attributes": True}


class ReleaseDiffRepository(BaseModel):
    """Repository coordinates shared by both release diff endpoints."""

    project_key: str = Field(
        ..., min_length=1, max_length=128, description="Bitbucket project key (or GitHub org)"
    )
    repository_slug: str = Field(
        ..., min_length=1, max_length=256, description="Repository slug / name"
    )
    git_provider: str | None = Field(
        default=None,
        description=(
            "Git provider override. Defaults to the configured default provider "
            "(bitbucket_server / bitbucket_cloud / github_enterprise)."
        ),
    )
    workspace_slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description=(
            "Bitbucket Cloud workspace slug holding the repository. Only used when "
            "git_provider is bitbucket_cloud: the workspace addresses the repository "
            "remotely while project_key stays the business key. Ignored by other providers."
        ),
    )


class ReleaseRefsRequest(ReleaseDiffRepository):
    """Request payload for POST /release/diff/refs."""

    limit: int = Field(
        default=100, ge=1, le=500, description="Maximum number of tags / branches returned"
    )


class ReleaseRefsResponse(BaseModel):
    """Response payload for POST /release/diff/refs."""

    project_key: str
    repository_slug: str
    git_provider: str
    tags: list[str] = Field(
        default_factory=list, description="Tag names of the repository (newest first)"
    )
    branches: list[str] = Field(default_factory=list, description="Branch names of the repository")


class ReleaseCompareRequest(ReleaseDiffRepository):
    """Request payload for POST /release/diff/compare."""

    old_release_ref: str = Field(
        ..., min_length=1, max_length=256, description="Old release ref (tag, branch or commit)"
    )
    new_release_ref: str = Field(
        ..., min_length=1, max_length=256, description="New release ref (tag, branch or commit)"
    )
    old_release_base_ref: str | None = Field(
        default=None,
        max_length=256,
        description=(
            "Optional predecessor of the old release. When provided, the old release "
            "commit set is scoped to commits reachable from old_release_ref but not "
            "from this ref. When omitted, all commits reachable from old_release_ref "
            "are used (capped by max_commits)."
        ),
    )
    new_release_base_ref: str | None = Field(
        default=None,
        max_length=256,
        description=(
            "Optional predecessor of the new release. When provided, the new release "
            "commit set is scoped to commits reachable from new_release_ref but not "
            "from this ref. When omitted, all commits reachable from new_release_ref "
            "are used (capped by max_commits)."
        ),
    )
    include_commits: bool = Field(
        default=True, description="Include commit details in the response"
    )
    max_commits: int = Field(
        default=1000, ge=1, le=5000, description="Maximum number of commits fetched per ref"
    )

    @field_validator(
        "old_release_ref",
        "new_release_ref",
        "old_release_base_ref",
        "new_release_base_ref",
    )
    @classmethod
    def _strip_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ReleaseCommitCheckRequest(ReleaseDiffRepository):
    """Request payload for POST /release/diff/check."""

    target_release_ref: str = Field(
        ..., min_length=1, max_length=256, description="Target release ref (tag, branch or commit)"
    )
    target_release_base_ref: str | None = Field(
        default=None,
        max_length=256,
        description=(
            "Optional predecessor of the target release. When provided, only commits "
            "between this ref and target_release_ref are considered part of the "
            "release. When omitted, all commits reachable from target_release_ref are "
            "used (capped by max_commits)."
        ),
    )
    commits: list[str] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Commit SHAs (full or short) to check against the target release",
    )
    max_commits: int = Field(
        default=1000, ge=1, le=5000, description="Maximum number of commits fetched for the release"
    )

    @field_validator("target_release_ref", "target_release_base_ref")
    @classmethod
    def _strip_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("commits")
    @classmethod
    def _clean_commits(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError("At least one commit id must be provided")
        return cleaned


class CommitCheckResult(BaseModel):
    """Per-commit membership result."""

    commit: str = Field(..., description="Commit id as supplied in the request")
    included: bool = Field(..., description="Whether the commit is part of the target release")
    matched_id: str | None = Field(default=None, description="Resolved full commit SHA when found")
    commit_info: CommitInfo | None = Field(
        default=None, description="Commit details when the commit was found"
    )
    reason: str = Field(
        default="",
        description="Short explanation: 'matched' or 'not_found_in_release_scope'",
    )


class ReleaseCompareResponse(BaseModel):
    """Response payload for POST /release/diff/compare."""

    project_key: str
    repository_slug: str
    git_provider: str
    old_release_ref: str
    new_release_ref: str
    old_release_base_ref: str | None = None
    new_release_base_ref: str | None = None
    old_commits_included: bool = Field(
        ..., description="True when every old release commit is reachable from the new release"
    )
    status: str = Field(
        ...,
        description=(
            "Comparison status: 'included' (old release is fully contained in new), "
            "'missing_commits' (some old commits are absent), 'identical' (same refs)"
        ),
    )
    summary: dict = Field(
        default_factory=dict,
        description="Counts: old_commit_count, new_commit_count, missing_count, added_count",
    )
    missing_commits: list[CommitInfo] = Field(
        default_factory=list,
        description="Old release commits that are NOT reachable from the new release",
    )
    added_commits: list[CommitInfo] = Field(
        default_factory=list,
        description="Commits reachable from the new release but not from the old release",
    )
    old_release_commits: list[CommitInfo] = Field(
        default_factory=list, description="Commits belonging to the old release scope"
    )
    new_release_commits: list[CommitInfo] = Field(
        default_factory=list, description="Commits belonging to the new release scope"
    )
    truncated: bool = Field(
        default=False, description="True when a commit list hit the max_commits cap"
    )


class ReleaseCommitCheckResponse(BaseModel):
    """Response payload for POST /release/diff/check."""

    project_key: str
    repository_slug: str
    git_provider: str
    target_release_ref: str
    target_release_base_ref: str | None = None
    all_included: bool = Field(
        ..., description="True when every requested commit belongs to the target release"
    )
    summary: dict = Field(
        default_factory=dict,
        description="Counts: requested, included_count, missing_count, release_commit_count",
    )
    results: list[CommitCheckResult] = Field(
        default_factory=list, description="Membership result for each requested commit"
    )
    truncated: bool = Field(
        default=False, description="True when the release commit list hit the max_commits cap"
    )
