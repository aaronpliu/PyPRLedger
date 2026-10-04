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


class AppVersionDiffPackage(BaseModel):
    """One row of the matrix: a package across every selected release."""

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
        description="Counts per state: unchanged, changed, upgrade, downgrade, added, removed",
    )
    changes: list[AppVersionDiffMove] = Field(
        default_factory=list,
        description="Every package that moved in this interval, in matrix row order",
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
    packages: list[AppVersionDiffPackage] = Field(default_factory=list)
    intervals: list[AppVersionDiffInterval] = Field(default_factory=list)
