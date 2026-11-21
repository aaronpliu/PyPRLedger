"""Schemas for the aggregate release note.

One application version span, one note: the application's own commits plus the
commits every package it pins gained between the two versions. The scope rule
is deliberate - only the packages the application declares (its exact pins, as
the dependency database holds them) are compared commit by commit; a transitive
dependency is a skipped entry with its reason, because a change two levels down
says nothing about this release unless the application pins it. An application
the database holds no record for is monolithic: the note degrades to the
application's own comparison and says so.
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
    summarize: bool = Field(
        default=False,
        description=(
            "Run the optional LLM pass over the application's own scope: one "
            "summary paragraph and section hints for its commits. A pass that "
            "fails degrades to the deterministic notes."
        ),
    )
    language: str | None = Field(
        default=None,
        max_length=8,
        description="Language the rendered bodies are written in (en / zh-CN / zh-TW)",
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
    body: str | None = Field(
        default=None,
        description=(
            "The package's rendered release note body (categorized sections, "
            "ticket links, authors), set for compared entries"
        ),
    )


class AggregateReleaseNoteSummary(BaseModel):
    """Counts a reader can trust without scrolling."""

    packages_changed: int = 0
    packages_compared: int = 0
    packages_skipped: int = 0
    packages_failed: int = 0
    unchanged_packages: int = 0
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
    dependency_source: str = Field(
        default="none",
        description=(
            "'database' when the dependency database held a record for both refs "
            "of the span and the packages are its answer; 'none' when the "
            "application is monolithic - no packages, none guessed"
        ),
    )
    application: ReleaseCompareResponse
    application_body: str | None = Field(
        default=None,
        description="The application's rendered release note body (categorized sections, ticket links, authors)",
    )
    summary_source: str | None = Field(
        default=None,
        description="'llm' when the optional AI pass answered, 'deterministic' when it ran and degraded",
    )
    summary_notice: str | None = Field(
        default=None,
        description="Why there is no AI summary, when the pass was asked for and could not be made",
    )
    packages: list[AggregatePackageEntry] = Field(default_factory=list)
    unchanged_packages: list[str] = Field(
        default_factory=list,
        description="'name@version' of every package both versions hold unchanged",
    )
    summary: AggregateReleaseNoteSummary = Field(default_factory=AggregateReleaseNoteSummary)


class AggregateNotePlanEntry(BaseModel):
    """One package the span moved, as the dependency database places it.

    The plan is versions only - no repository resolution, no commit
    comparison - so it can be shown while the release is still being typed.
    """

    name: str
    change: str = Field(description="'upgraded' | 'added' | 'removed'")
    from_version: str = Field(description="Empty when the package was added in this span")
    to_version: str = Field(description="Empty when the package was removed in this span")
    pinned: bool = Field(description="Whether the application declares the package")
    reason: str | None = Field(
        default=None,
        description="Why the package will not get a commit comparison, when it will not",
    )


class AggregateNotePlanResponse(BaseModel):
    """The dependency versions a span carries, before any note is built.

    The declared pins of each ref are the authoritative answer to "what does
    this version of the application carry": what the dependency database holds,
    not an inference. An application with no record is monolithic - empty pins,
    no packages, none guessed.
    """

    app_name: str
    source_ref: str
    target_ref: str
    dependency_source: str = Field(
        default="none",
        description="'database' when both refs have records, 'none' when the application is monolithic",
    )
    source_pins: dict[str, str] = Field(
        default_factory=dict,
        description="What the application's source version declares: '{package: version}'",
    )
    target_pins: dict[str, str] = Field(
        default_factory=dict,
        description="What the application's target version declares: '{package: version}'",
    )
    packages: list[AggregateNotePlanEntry] = Field(default_factory=list)
    unchanged_packages: list[str] = Field(
        default_factory=list,
        description="'name@version' of every package both versions hold at the same version",
    )
