"""Schemas for release diff (compare / check) endpoints.

These models describe request/response payloads for comparing two release
refs (tags/branches/commits) and for checking whether specific commits are
contained in a target release.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


# Verdict of a containment check.
#
# ``inconclusive`` is what a check reports when the difference could not be
# enumerated completely (scan limit or a provider page cap). It must never be
# presented as - or converted into - a pass.
VERDICT_CONTAINED = "contained"
VERDICT_MISSING = "missing"
VERDICT_INCONCLUSIVE = "inconclusive"


class CommitInfo(BaseModel):
    """Normalized commit representation across git providers."""

    id: str = Field(..., description="Full commit SHA")
    display_id: str | None = Field(default=None, description="Short commit SHA")
    author_name: str | None = Field(default=None, description="Author display name")
    author_username: str | None = Field(
        default=None,
        description=(
            "Provider login / account slug of the author (Bitbucket Server name, Cloud "
            "nickname, GitHub login). Used to link the author profile."
        ),
    )
    author_url: str | None = Field(
        default=None, description="Web URL of the author profile, when the provider has one"
    )
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
    refresh: bool = Field(
        default=False,
        description=(
            "Bypass the Redis cache and read from the git provider again. Used by the "
            "'Refresh' action so newly created tags / branches show up immediately."
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
    """Request payload for POST /release/diff/compare.

    One operation, one question, one vocabulary: is everything from the *source*
    release contained in the *target* release, and what does the target add on top
    of it? The optional baseline is a single starting point (the fork point of a
    maintenance line, or the previous release of that line) that narrows both
    directions.
    """

    source_ref: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Source release ref whose commits must be contained (tag, branch or commit)",
    )
    target_ref: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Target release ref that should contain them (tag, branch or commit)",
    )
    baseline_ref: str | None = Field(
        default=None,
        max_length=256,
        description=(
            "Optional baseline both directions are narrowed against: difference commits "
            "that already existed at it are ignored, which is what 'the work this line "
            "did since the fork point' means. It belongs to this comparison alone - a "
            "repository holds several release lines, each with a fork point of its own."
        ),
    )
    scan_limit: int = Field(
        default=2000,
        ge=1,
        le=10000,
        description=(
            "Maximum number of difference commits enumerated per direction before the "
            "verdict becomes 'inconclusive'. A difference is small by construction "
            "(shared history cancels out), so the limit only guards a pathological case - "
            "and reaching it is reported rather than hidden."
        ),
    )
    render_limit: int = Field(
        default=200,
        ge=1,
        le=2000,
        description="Maximum number of difference commits returned with details per direction",
    )
    include_commits: bool = Field(
        default=True,
        description=(
            "Serialize commit details for the missing and added lists. The verdict and the "
            "counts never depend on it"
        ),
    )

    @field_validator("source_ref", "target_ref")
    @classmethod
    def _require_ref(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("a release ref must not be blank")
        return stripped

    @field_validator("baseline_ref")
    @classmethod
    def _strip_optional_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


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
        default=1000,
        ge=1,
        le=5000,
        description=(
            "Maximum number of commits listed for the release. Kept for backwards "
            "compatibility: the membership verdict no longer depends on this listing, "
            "which is only used to attach commit details to the matches. A commit "
            "beyond the listing is still checked against the provider."
        ),
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
        description=(
            "Short explanation: 'matched' (contained in the target release), "
            "'not_reachable_from_target' (not an ancestor of the target ref) or "
            "'excluded_by_release_base' (present, but before the release base ref so it "
            "does not belong to that release). No reason is ever caused by a capped "
            "listing."
        ),
    )


class ReleaseCompareResponse(BaseModel):
    """Response payload for POST /release/diff/compare."""

    project_key: str
    repository_slug: str
    git_provider: str
    source_ref: str
    target_ref: str
    baseline_ref: str | None = Field(
        default=None, description="Effective baseline both directions were narrowed against"
    )
    narrowed: bool = Field(
        default=False, description="True when a baseline narrowed the comparison"
    )
    verdict: str = Field(
        default=VERDICT_INCONCLUSIVE,
        description=(
            "'contained' | 'missing' | 'inconclusive'. Derived from the provider-side "
            "difference 'source \\ target' alone, so rendered (capped) commit lists can "
            "never turn it into a pass."
        ),
    )
    scan_complete: bool = Field(
        default=False,
        description=(
            "True when the whole missing direction was enumerated. False means the only "
            "honest verdict is 'inconclusive': more commits may be missing than reported."
        ),
    )
    scan_limit: int = Field(default=0, description="Scan limit that applied per direction")
    filtered_by_baseline_count: int = Field(
        default=0,
        description="Difference commits (both directions) ignored because they existed at the baseline",
    )
    missing_count: int = Field(
        default=0,
        description=(
            "Commits of the source release that the target lacks: exact when scan_complete, "
            "otherwise a lower bound"
        ),
    )
    missing_commits: list[CommitInfo] = Field(
        default_factory=list,
        description="Missing commits with details (capped at render_limit, only when requested)",
    )
    added_count: int = Field(
        default=0, description="Commits the target has and the source does not"
    )
    added_commits: list[CommitInfo] = Field(
        default_factory=list,
        description="Added commits with details (capped at render_limit, only when requested)",
    )
    added_complete: bool = Field(
        default=False, description="True when the whole added direction was enumerated"
    )
    rendered_truncated: bool = Field(
        default=False,
        description="True when more difference commits exist than the rendered lists carry",
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
    verdict: str = Field(
        default=VERDICT_MISSING,
        description=(
            "'contained' when every requested commit belongs to the target release, "
            "'missing' otherwise. Each commit is answered by the provider, so this "
            "verdict is exact and never 'inconclusive'."
        ),
    )
    summary: dict = Field(
        default_factory=dict,
        description="Counts: requested, included_count, missing_count, release_commit_count",
    )
    results: list[CommitCheckResult] = Field(
        default_factory=list, description="Membership result for each requested commit"
    )
    truncated: bool = Field(
        default=False,
        description=(
            "True when the commit listing used to enrich the matches hit the max_commits "
            "cap. It concerns the attached details only - the verdict is answered per "
            "commit by the provider and is unaffected."
        ),
    )
