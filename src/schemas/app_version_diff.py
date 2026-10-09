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


class AppVersionDiffRequest(BaseModel):
    """The application whose releases are compared, and which releases."""

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
    refresh: bool = Field(
        default=False,
        description=(
            "Bypass the cache and read every release from the dependency source again. A "
            "tag can be moved, so a reader who suspects one should not have to wait for the "
            "cache to expire."
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
