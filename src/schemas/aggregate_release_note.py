"""Schemas for the aggregate release note.

One application version span, one note: the application's own commits plus the
commits every package it pins gained between the two versions. The scope rule
is deliberate - only the packages the application declares (its workspace pins)
are compared commit by commit; the transitive closure the dependency database
adds is summarized, because a change two levels down the graph says nothing
about this release unless the application pins it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.schemas.release_diff import ReleaseCompareResponse, ReleaseDiffRepository


class AggregateReleaseNoteRequest(ReleaseDiffRepository):
    """Request payload for POST /release/aggregate-note/build."""

    app_name: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "The application the dependency record is keyed by. Resolved from the "
            "project registry when left out."
        ),
    )
    source_ref: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="The version the release starts from (tag, branch or commit)",
    )
    target_ref: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="The version being released (tag, branch or commit)",
    )
    include_commits: bool = Field(
        default=True,
        description="Render the commit lists; the verdicts stand either way",
    )
    refresh: bool = Field(
        default=False,
        description="Bypass the caches of the graph and the per-package comparisons",
    )


class AggregatePackageRepository(BaseModel):
    """Where a package's commits are read from."""

    project_key: str
    repository_slug: str
    git_provider: str | None = None


class AggregatePackageEntry(BaseModel):
    """One package the release span moved, and what the note says about it.

    ``status`` keeps a package that cannot be compared from hiding in the note:
    ``compared`` carries a full comparison, ``skipped`` names why there is
    nothing to compare (not registered, added or removed in this span), and
    ``failed`` carries the provider error - "cannot say" must stay legible.
    """

    name: str
    change: str = Field(description="'upgraded' | 'added' | 'removed'")
    from_version: str = Field(description="Empty when the package was added in this span")
    to_version: str = Field(description="Empty when the package was removed in this span")
    status: str = Field(description="'compared' | 'skipped' | 'failed'")
    reason: str | None = None
    repository: AggregatePackageRepository | None = None
    comparison: ReleaseCompareResponse | None = None


class AggregateReleaseNoteSummary(BaseModel):
    """Counts a reader can trust without scrolling."""

    packages_changed: int = 0
    packages_compared: int = 0
    packages_skipped: int = 0
    packages_failed: int = 0
    app_commits: int = 0
    package_commits: int = 0


class AggregateReleaseNoteResponse(BaseModel):
    """The whole note: the application's section, one entry per moved package."""

    app_name: str
    project_key: str
    repository_slug: str
    git_provider: str | None = None
    source_ref: str
    target_ref: str
    application: ReleaseCompareResponse
    packages: list[AggregatePackageEntry] = Field(default_factory=list)
    unchanged_packages: list[str] = Field(
        default_factory=list,
        description="'name@version' of every package both versions hold unchanged",
    )
    summary: AggregateReleaseNoteSummary = Field(default_factory=AggregateReleaseNoteSummary)
