"""Schemas for the App Diff endpoint.

These models describe comparing two or more releases of one application at
direct-dependency level: the releases in the order their datetimes put them, the
version matrix (one row per package, one column per release), and one comparison
per adjacent pair of releases - the same shape a repository comparison has,
applied to the same package at two versions instead of the same repository at
two refs.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from src.schemas.release_diff import CommitInfo


# Verdict of a whole comparison.
#
# ``incomplete`` is what a comparison reports when a selected release has no
# dependency record. That release's versions are unknown, so the comparison must
# never be rendered - or answered - as "nothing changed".
VERDICT_IDENTICAL = "identical"
VERDICT_CHANGED = "changed"
VERDICT_INCOMPLETE = "incomplete"


# State of one package between two adjacent releases.
STATE_UNCHANGED = "unchanged"
STATE_CHANGED = "changed"
STATE_ADDED = "added"
STATE_REMOVED = "removed"

# Direction of a changed package. Absent when the two versions cannot be
# ordered, which must never be presented as an upgrade.
DIRECTION_UPGRADE = "upgrade"
DIRECTION_DOWNGRADE = "downgrade"

# Every state a package can be counted under.
STATES: tuple[str, ...] = (
    STATE_UNCHANGED,
    STATE_CHANGED,
    STATE_ADDED,
    STATE_REMOVED,
)

# What a row of the matrix compares: the application's own version, or one of
# the dependencies it declares.
KIND_APPLICATION = "application"
KIND_DEPENDENCY = "dependency"

# A comparison needs two releases to be a comparison at all, and a matrix stops
# being readable well before it has twenty columns.
MIN_RELEASES = 2
MAX_RELEASES = 8


class AppVersionDiffCoordinates(BaseModel):
    """Where the application lives, and whether to read past the cache.

    Every App Diff request carries these, the batches that continue a comparison
    included: a batch asks the same question about the same releases, so it is
    answered with the same reading.
    """

    project_key: str = Field(
        ..., min_length=1, max_length=128, description="Bitbucket project key (or GitHub org)"
    )
    repository_slug: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Repository the application is resolved through",
    )
    git_provider: str | None = Field(
        default=None,
        description=(
            "Git provider override. Defaults to the provider the repository is registered "
            "under, then to the configured default."
        ),
    )
    workspace_slug: str | None = Field(
        default=None,
        description="Bitbucket Cloud only: workspace holding the repository.",
    )
    refresh: bool = Field(
        default=False,
        description=(
            "Bypass the cache and read every release from the dependency source again. A "
            "tag can be moved, so a reader who suspects one should not have to wait for the "
            "cache to expire."
        ),
    )


class AppVersionDiffRequest(AppVersionDiffCoordinates):
    """The application whose releases are compared, and which releases."""

    refs: list[str] = Field(
        ...,
        min_length=MIN_RELEASES,
        max_length=MAX_RELEASES,
        description=(
            "The application releases to compare, as they appear in the repository's tags "
            "and branches. The order they are supplied in is ignored: the releases are "
            "presented in the order their datetimes put them."
        ),
    )
    max_package_comparisons: int | None = Field(
        default=None,
        ge=1,
        description=(
            "How many dependency comparisons each adjacent pair should carry in this "
            "response. Null takes the server's default. Asking for a deeper reading asks for "
            "a longer first response, so the numbers are clamped to the server's ceiling "
            "rather than refused, and the effective ones ride back with the answer."
        ),
    )
    max_total_package_comparisons: int | None = Field(
        default=None,
        ge=1,
        description=(
            "How many dependency comparisons this page should run automatically in total - "
            "what the first response carries plus what the page asks for afterwards. This is "
            "the dial a reader deepens to have a release that moved dozens of packages read "
            "whole: the pairs still answer with their first few, and the rest is read behind "
            "them. Null takes the server's default, and the page ceiling applies."
        ),
    )
    include_code: bool = Field(
        default=True,
        description=(
            "Read the commits between every pair of adjacent releases as well. The dependency "
            "axis is answered either way; this only decides whether the code axis is read, "
            "which costs one repository comparison per pair."
        ),
    )

    @field_validator("refs")
    @classmethod
    def _clean_refs(cls, value: list[str]) -> list[str]:
        """Trim the refs and drop repeats, keeping the first of each."""
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            ref = (item or "").strip()
            if ref and ref not in seen:
                seen.add(ref)
                cleaned.append(ref)
        if len(cleaned) < MIN_RELEASES:
            raise ValueError(f"a comparison needs at least {MIN_RELEASES} distinct releases")
        return cleaned


class AppVersionDiffRelease(BaseModel):
    """One selected release, placed on the timeline."""

    ref: str = Field(..., description="Release ref, as the repository reports it")
    released_at: str | None = Field(
        default=None,
        description=(
            "The release datetime: the dependency record's own timestamp when it has one, "
            "otherwise the date of the tag. Null when neither exists."
        ),
    )
    has_record: bool = Field(
        default=False,
        description="Whether the dependency source holds a record for this release",
    )


class AppVersionDiffMove(BaseModel):
    """What one package did between two adjacent releases."""

    name: str = Field(..., description="Package name as the application declares it")
    kind: str = Field(
        ...,
        description=(
            f"What the name is: `{KIND_APPLICATION}` for the application's own version, "
            f"`{KIND_DEPENDENCY}` for one of the packages it declares. A comparison "
            "reports both, and a reader has to be able to tell them apart"
        ),
    )
    source_version: str | None = Field(
        default=None, description="Version in the earlier release; null when not declared"
    )
    target_version: str | None = Field(
        default=None, description="Version in the later release; null when not declared"
    )
    state: str = Field(..., description="unchanged | changed | added | removed")
    direction: str | None = Field(
        default=None,
        description=(
            "upgrade | downgrade, or null when the move is not a change or when the two "
            "versions cannot be ordered. Never an upgrade in that last case."
        ),
    )
    orderable: bool = Field(
        default=True,
        description="Whether both versions parsed into ordered components",
    )


class AppVersionDiffRow(BaseModel):
    """One row of the matrix: an entry across every selected release.

    The first row is the application itself - its own version is one of the
    things a release comparison is about - and the rest are the dependencies it
    declares.
    """

    kind: str = Field(
        ...,
        description="'application' for the application's own version, 'dependency' for a package",
    )
    name: str
    versions: list[str | None] = Field(
        ...,
        description=(
            "One entry per release, in the order the releases are presented; null where the "
            "release does not declare the package"
        ),
    )
    moves: list[AppVersionDiffMove | None] = Field(
        default_factory=list,
        description=(
            "One entry per boundary between adjacent releases; null where the boundary "
            "involves a release with no record, so the move is unknown rather than unchanged"
        ),
    )


class AppVersionDiffCode(BaseModel):
    """The commits between two adjacent releases.

    The dependency axis cannot prove that nothing happened - a tag moved to a new
    commit while the versions it pins stayed identical yields no dependency
    change at all - so what landed between the two refs is read alongside it.
    """

    verdict: str = Field(
        ...,
        description=(
            "The repository comparison's verdict for the pair: 'contained' when the later "
            "release holds everything of the earlier one, 'missing' otherwise, "
            "'inconclusive' when the difference could not be enumerated completely."
        ),
    )
    scan_complete: bool = Field(
        default=False,
        description="Whether the missing direction was enumerated completely",
    )
    added_count: int = Field(default=0, description="Commits the later release adds")
    missing_count: int = Field(
        default=0,
        description="Commits of the earlier release the later one does not contain",
    )
    added_commits: list[CommitInfo] = Field(default_factory=list)
    missing_commits: list[CommitInfo] = Field(default_factory=list)
    truncated: bool = Field(
        default=False, description="Whether more commits exist than the rendered lists carry"
    )
    deferred: bool = Field(
        default=False,
        description=(
            "Whether this comparison was left for later rather than found impossible: the two "
            "versions are known and the repository is known, but the pair had more moved "
            "packages than one response reads. The page asks for these in batches "
            "(POST /release/apps/diff/packages); until then there is no verdict, which is not "
            "the same as an inconclusive one and must never be shown as one."
        ),
    )
    unavailable: str | None = Field(
        default=None,
        description=(
            "Why the commits could not be read - an unreachable provider, a release ref the "
            "provider does not know. Null when they were read, including when there are none."
        ),
    )


class AppVersionDiffPackageComparison(BaseModel):
    """One dependency's own comparison, between the two releases of a pair.

    The dependency axis says which version a package moved to; this says what came
    with it - the commits between the two versions of that package, read the way a
    repository comparison reads two release refs. Which repository a package lives
    in is not in the dependency record, so it is resolved through the project
    registry by the name the record uses; a package that resolves to no repository
    (an external library), to several, or whose versions the provider cannot
    compare is reported as inconclusive with the reason, never left out and never
    counted as contained.
    """

    name: str = Field(..., description="Package name as the application declares it")
    state: str = Field(
        ...,
        description=(
            "The move this package made: 'changed' has two versions and is compared, "
            "'added' and 'removed' have one and are reported as such"
        ),
    )
    source_version: str | None = Field(
        default=None, description="Version in the earlier release; its tag in that repository"
    )
    target_version: str | None = Field(
        default=None, description="Version in the later release; its tag in that repository"
    )
    project_key: str | None = Field(
        default=None, description="Project the package was resolved to, when it was"
    )
    repository_slug: str | None = Field(
        default=None, description="Repository the package was resolved to, when it was"
    )
    git_provider: str | None = Field(
        default=None, description="Provider that repository lives on, when it was resolved"
    )
    code: AppVersionDiffCode = Field(
        ...,
        description=(
            "The comparison itself, in the same shape the application's own code axis uses. "
            "`unavailable` carries why there is none: no registered repository, an ambiguous "
            "name, a version the provider does not know, or a package past the ceiling"
        ),
    )


class AppVersionDiffInterval(BaseModel):
    """One adjacent pair of releases, compared."""

    source_ref: str = Field(..., description="Earlier release of the pair")
    target_ref: str = Field(..., description="Later release of the pair")
    complete: bool = Field(
        default=False,
        description=(
            "Whether both releases have a record. False means the only honest reading is "
            "'unknown': it must never be presented as 'no changes'."
        ),
    )
    summary: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Counts per state over every row of the matrix, the application's own included: "
            "unchanged, changed, upgrade, downgrade, added, removed"
        ),
    )
    dependencies_moved: bool = Field(
        default=False,
        description=(
            "Whether any dependency row moved. Decided over the dependency rows alone, so it "
            "stays true to its name when the application's own version is the only thing that "
            "moved - which is what the rebuild reading is built on."
        ),
    )
    changes: list[AppVersionDiffMove] = Field(
        default_factory=list,
        description="Every row that moved in this interval, in matrix row order",
    )
    packages: list[AppVersionDiffPackageComparison] = Field(
        default_factory=list,
        description=(
            "Every dependency that moved in this interval, with the commits between the two "
            "versions it moved between. The application's own version is not among them: it "
            "is the pair's code axis, which this page reads above"
        ),
    )
    code: AppVersionDiffCode | None = Field(
        default=None,
        description=(
            "The commits between the two releases. Null when the pair is incomplete or the "
            "request did not ask for the code axis - which is not the same as a pair with no "
            "commits, so it must not be presented as one."
        ),
    )


class AppVersionDiffPackageBudget(BaseModel):
    """How many package comparisons the page may run, and how it should ask for them.

    These are the *effective* numbers, not the ones asked for: a request may ask for a
    deeper reading than the defaults, and it is answered with what the server will
    actually do - the ceilings any request is held to included. The page reads its
    pacing from here rather than from numbers compiled into it.
    """

    per_pair: int = Field(
        ..., description="Most comparisons an adjacent pair carries in this response"
    )
    page_total: int = Field(..., description="Most comparisons this page may run automatically")
    batch: int = Field(
        ..., description="Most deferred packages should be asked for at a time"
    )
    remaining: int = Field(
        ...,
        description=(
            "How much of ``page_total`` this response leaves. The page asks for its deferred "
            "packages in batches until this runs out, and leaves whatever is left for a "
            "reader to ask for."
        ),
    )


class AppVersionDiffResponse(BaseModel):
    """Two or more releases of one application, compared."""

    project_key: str
    repository_slug: str
    app_name: str = Field(..., description="The application the repository resolved to")
    git_provider: str

    releases: list[AppVersionDiffRelease] = Field(
        default_factory=list, description="The releases, in release-datetime order"
    )
    verdict: str = Field(
        default=VERDICT_INCOMPLETE,
        description=(
            "identical | changed | incomplete. Incomplete as soon as one selected release has "
            "no record; the comparisons between the releases that do have records are still "
            "reported."
        ),
    )
    summary: dict[str, int] = Field(
        default_factory=dict,
        description="Totals over the complete intervals only",
    )
    rows: list[AppVersionDiffRow] = Field(
        default_factory=list,
        description="The matrix, the application's own version first, then its direct dependencies",
    )
    intervals: list[AppVersionDiffInterval] = Field(default_factory=list)
    package_comparisons: AppVersionDiffPackageBudget = Field(
        ...,
        description=(
            "The comparison budget this answer was read under, and how much of it is left. "
            "The page paces its batches by it, so that what a page reads is decided by the "
            "server rather than by a number compiled into the page."
        ),
    )


# A batch is a few packages at a time, asked for while the page is being read. A
# request larger than this is not a batch but a way around the ceiling above, so
# the schema refuses it rather than quietly reading it.
MAX_PACKAGE_BATCH = 25


class AppVersionDiffPackageRequest(BaseModel):
    """One package to compare, as the page read it off the matrix.

    The versions come from the page rather than being read again here: the pair is
    the one the first response reported, and a comparison needs no more than the
    name of the package and the two versions it moved between.
    """

    name: str = Field(
        ..., min_length=1, max_length=256, description="Package name as the application declares it"
    )
    source_version: str = Field(
        ..., min_length=1, description="Version in the earlier release of the pair"
    )
    target_version: str = Field(
        ..., min_length=1, description="Version in the later release of the pair"
    )


class AppVersionDiffPackagesRequest(AppVersionDiffCoordinates):
    """A pair of releases, and the packages of it to compare now.

    One pair per request, because a comparison is between two releases: the batches
    that finish a comparison are batches of packages within a pair, never across
    pairs. A package moved in several pairs is asked for once per pair, which is
    what it takes to answer what changed between those two releases.
    """

    source_ref: str = Field(
        ..., min_length=1, max_length=256, description="Earlier release of the pair"
    )
    target_ref: str = Field(
        ..., min_length=1, max_length=256, description="Later release of the pair"
    )
    packages: list[AppVersionDiffPackageRequest] = Field(
        ...,
        min_length=1,
        max_length=MAX_PACKAGE_BATCH,
        description=(
            f"The packages to compare, up to {MAX_PACKAGE_BATCH} at a time. Each is answered "
            "the way the first response answers it"
        ),
    )


class AppVersionDiffPackagesResponse(BaseModel):
    """The packages of one pair that were asked for, compared."""

    project_key: str
    repository_slug: str
    source_ref: str = Field(..., description="Earlier release of the pair")
    target_ref: str = Field(..., description="Later release of the pair")
    packages: list[AppVersionDiffPackageComparison] = Field(
        default_factory=list,
        description=(
            "One entry per package asked for, in the shape the first response uses, so a page "
            "replaces a deferred entry with the answer rather than re-rendering the row"
        ),
    )
