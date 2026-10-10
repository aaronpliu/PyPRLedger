"""Tests for comparing the releases of one application.

The dependency source is answered by a fake client, so no third-party service is
contacted and every case - an unreachable source included - can be produced.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.core.config import settings
from src.core.exceptions import DependencyApiException
from src.schemas.app_version_diff import (
    AppVersionDiffPackageRequest,
    AppVersionDiffPackagesRequest,
    AppVersionDiffRequest,
)
from src.schemas.release_diff import ReleaseCompareRequest, ReleaseCompareResponse
from src.services.app_version_diff_service import (
    AppVersionDiffService,
    DependencyRepository,
    compare_versions,
    parse_version,
)
from src.services.dependency_graph_service import DependencyGraphService


APP = "mylang"
PROJECT = "CORE"
REPOSITORY = "app"


class FakeCache:
    """A cache that keeps what it is given, so the second read is a hit."""

    def __init__(self) -> None:
        self.stored: dict[str, Any] = {}
        self.writes = 0

    async def get_json(self, key: str) -> Any:
        return self.stored.get(key)

    async def set_json(self, key: str, value: Any, expire: int | None = None) -> None:
        self.writes += 1
        self.stored[key] = value


class FakeClient:
    """A dependency source holding exactly the records it was handed."""

    def __init__(self, records: dict[tuple[str, str], dict[str, Any]]) -> None:
        self.records = records
        self.reads = 0

    async def get_app_release_info(
        self, app_name: str, tag_or_branch: str
    ) -> dict[str, Any] | None:
        self.reads += 1
        return self.records.get((app_name, tag_or_branch))


class UnreachableClient:
    """A dependency source that cannot be reached."""

    async def get_app_release_info(
        self, app_name: str, tag_or_branch: str
    ) -> dict[str, Any] | None:
        raise DependencyApiException("dependency database is down")


class FakeProvider:
    """A git provider answering with the tags it was handed."""

    def __init__(self, tags: list[dict[str, Any]] | None = None) -> None:
        self.tags = tags or []
        self.listings = 0

    async def list_tags_with_commits(
        self, project_key: str, repository_slug: str, limit: int = 1000
    ) -> list[dict[str, Any]]:
        self.listings += 1
        return self.tags


def record(
    ref: str,
    created_at: str | None,
    dependencies: dict[str, str],
    packages: list[dict[str, Any]] | None = None,
    app_name: str = APP,
    app_version: str | None = None,
) -> dict[str, Any]:
    """One release record in the shape the dependency source answers with.

    ``app_version`` is the application's own version, which the record holds
    under its key; it defaults to the ref, and a test that cares about the
    dependencies alone can hold it still across two releases.
    """
    return {
        "app_name": app_name,
        "tagOrBranch": app_version or ref,
        "created_at": created_at,
        "dependencies": dependencies,
        "packages": packages or [],
    }


class FakeDiff:
    """The repository comparison, answering with what it was handed."""

    def __init__(self, added: int = 0, missing: int = 0, fail: str | None = None) -> None:
        self.added = added
        self.missing = missing
        self.fail = fail
        self.calls: list[tuple[str, str]] = []
        self.requests: list[ReleaseCompareRequest] = []

    async def compare_releases(self, request: ReleaseCompareRequest) -> ReleaseCompareResponse:
        self.calls.append((request.source_ref, request.target_ref))
        self.requests.append(request)
        if self.fail:
            raise RuntimeError(self.fail)
        return ReleaseCompareResponse(
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            git_provider="bitbucket_server",
            source_ref=request.source_ref,
            target_ref=request.target_ref,
            verdict="contained",
            scan_complete=True,
            added_count=self.added,
            missing_count=self.missing,
        )


def build_service(
    records: dict[tuple[str, str], dict[str, Any]],
    tags: list[dict[str, Any]] | None = None,
    client: Any | None = None,
    diff: FakeDiff | None = None,
) -> tuple[AppVersionDiffService, FakeCache, FakeProvider]:
    cache = FakeCache()
    provider = FakeProvider(tags)
    graph = DependencyGraphService(cache=FakeCache(), client=client or FakeClient(records))
    service = AppVersionDiffService(
        cache=cache,
        graph_service=graph,
        diff_service=diff or FakeDiff(),
        provider_factory=lambda name: provider,
    )
    return service, cache, provider


def request(*refs: str, refresh: bool = False, include_code: bool = True) -> AppVersionDiffRequest:
    return AppVersionDiffRequest(
        project_key=PROJECT,
        repository_slug=REPOSITORY,
        git_provider="bitbucket_server",
        refs=list(refs),
        refresh=refresh,
        include_code=include_code,
    )


# ---------------------------------------------------------------------- #
# Reading a version
# ---------------------------------------------------------------------- #


def test_a_patch_bump_is_an_upgrade():
    assert compare_versions("1.0.0", "1.0.1") == ("changed", "upgrade", True)


def test_a_lower_patch_is_a_downgrade():
    assert compare_versions("2.2601.1", "2.2601.0") == ("changed", "downgrade", True)


def test_a_prerelease_sorts_before_its_release():
    assert compare_versions("1.2.0-rc.0", "1.2.0") == ("changed", "upgrade", True)
    assert compare_versions("1.2.0", "1.2.0-rc.0") == ("changed", "downgrade", True)


def test_numeric_components_are_compared_numerically():
    # lexically "2.9.0" would look newer than "2.2601.0", which is the wrong way round
    assert compare_versions("2.9.0", "2.2601.0") == ("changed", "upgrade", True)


def test_a_prerelease_number_is_read_as_a_number():
    assert parse_version("2.2602.1-demo-rc.2") == (2, 2602, 1, ("demo-rc", "2"))


def test_a_value_that_is_not_a_version_has_no_direction():
    state, direction, orderable = compare_versions(">=1.0.0 <1.9.0", ">=1.1.0 <2.0.0")

    assert state == "changed"
    assert direction is None
    assert orderable is False


def test_one_version_written_twice_is_a_change_without_a_direction():
    assert compare_versions("1.0", "1.0.0") == ("changed", None, True)


def test_a_missing_side_is_added_or_removed():
    assert compare_versions(None, "0.9.0")[0] == "added"
    assert compare_versions("0.9.0", None)[0] == "removed"


def test_the_same_version_is_unchanged():
    assert compare_versions("1.0.0", "1.0.0") == ("unchanged", None, True)


# ---------------------------------------------------------------------- #
# The matrix and the comparisons
# ---------------------------------------------------------------------- #


async def test_every_declared_package_gets_a_row():
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"b": "1.0.0", "a": "1.0.0"}),
            (APP, "1.1.0"): record("1.1.0", "2026-10-01", {"a": "1.0.0", "c": "0.1.0"}),
        }
    )

    result = await service.compare(request("1.0.0", "1.1.0"), app_name=APP)

    # the application first, then the union of both releases in one stable order
    assert result.rows[0].kind == "application"
    assert result.rows[0].name == APP
    assert [row.name for row in result.rows[1:]] == ["a", "b", "c"]
    versions = {row.name: row.versions for row in result.rows}
    assert versions["a"] == ["1.0.0", "1.0.0"]
    assert versions["b"] == ["1.0.0", None]
    assert versions["c"] == [None, "0.1.0"]


async def test_the_application_is_the_first_row_and_carries_its_own_version():
    service, _, _ = build_service(
        {
            (APP, "1.0.0_10000"): record("1.0.0_10000", "2026-09-01", {"packageA": "1.0.0"}),
            (APP, "1.1.0_10000"): record("1.1.0_10000", "2026-10-01", {"packageA": "1.0.0"}),
        }
    )

    result = await service.compare(request("1.0.0_10000", "1.1.0_10000"), app_name=APP)

    application = result.rows[0]
    assert application.kind == "application"
    assert application.name == APP
    assert application.versions == ["1.0.0_10000", "1.1.0_10000"]
    # classified like any other row, and marked as not a dependency
    assert application.moves[0].state == "changed"
    assert application.moves[0].direction == "upgrade"
    assert all(row.kind == "dependency" for row in result.rows[1:])
    # the only dependency did not move, so the pair's dependency reading is false
    assert result.intervals[0].dependencies_moved is False
    # while the summary still counts the application's own move
    assert result.intervals[0].summary["changed"] == 1
    assert result.verdict == "changed"


async def test_every_change_says_which_kind_of_row_it_was():
    """The page lists what moved in a pair, so the application has to be told apart."""
    service, _, _ = build_service(
        {
            (APP, "1.0.0_10000"): record(
                "1.0.0_10000", "2026-09-01", {"packageA": "1.0.0", "packageB": "2.0.0"}
            ),
            (APP, "1.1.0_10000"): record(
                "1.1.0_10000", "2026-10-01", {"packageA": "1.2.0", "packageB": "2.0.0"}
            ),
        }
    )

    result = await service.compare(request("1.0.0_10000", "1.1.0_10000"), app_name=APP)

    # in matrix row order: the application first, then its dependencies
    assert [(change.kind, change.name) for change in result.intervals[0].changes] == [
        ("application", APP),
        ("dependency", "packageA"),
    ]
    # and each change carries the two versions it is about, which is what is read
    application, dependency = result.intervals[0].changes
    assert (application.source_version, application.target_version) == (
        "1.0.0_10000",
        "1.1.0_10000",
    )
    assert (dependency.source_version, dependency.target_version) == ("1.0.0", "1.2.0")
    assert dependency.direction == "upgrade"


async def test_a_build_number_moves_the_row_without_a_direction():
    service, _, _ = build_service(
        {
            (APP, "1.0.0_10000"): record("1.0.0_10000", "2026-09-01", {"packageA": "1.0.0"}),
            (APP, "1.0.0_20000"): record("1.0.0_20000", "2026-10-01", {"packageA": "1.0.0"}),
        }
    )

    result = await service.compare(request("1.0.0_10000", "1.0.0_20000"), app_name=APP)

    move = result.rows[0].moves[0]
    assert move.state == "changed"
    # a build number carries no precedence, so it must never read as an upgrade
    assert move.direction is None
    assert result.intervals[0].summary["upgrade"] == 0


async def test_a_version_move_is_classified_and_counted():
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record(
                "1.0.0",
                "2026-09-01",
                {
                    "packageA": "1.0.0",
                    "packageB": "1.0.0",
                    "packageC": "1.1.0",
                    "packageD": "1.1.0",
                },
            ),
            (APP, "1.1.0"): record(
                "1.1.0",
                "2026-10-01",
                {
                    "packageA": "1.0.0",
                    "packageB": "1.0.1",
                    "packageC": "1.1.0",
                    "packageF": "0.9.0",
                },
            ),
        }
    )

    result = await service.compare(request("1.0.0", "1.1.0"), app_name=APP)

    moves = {row.name: row.moves[0] for row in result.rows}
    # the application's own version moved too, and is counted with the rest
    assert moves[APP].state == "changed"
    assert moves["packageA"].state == "unchanged"
    assert (moves["packageB"].state, moves["packageB"].direction) == ("changed", "upgrade")
    assert moves["packageC"].state == "unchanged"
    assert moves["packageD"].state == "removed"
    assert moves["packageF"].state == "added"

    interval = result.intervals[0]
    assert interval.complete is True
    assert interval.dependencies_moved is True
    # six rows: the application, four dependencies, and one the later release added
    assert interval.summary["unchanged"] == 2
    # changed counts what moved within both releases: the application and packageB
    assert interval.summary["changed"] == 2
    assert interval.summary["upgrade"] == 2
    assert interval.summary["downgrade"] == 0
    assert interval.summary["added"] == 1
    assert interval.summary["removed"] == 1
    assert result.verdict == "changed"


async def test_a_downgrade_is_reported_as_one():
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "2.2601.1"}),
            (APP, "1.1.0"): record("1.1.0", "2026-10-01", {"packageA": "2.2601.0"}),
        }
    )

    result = await service.compare(request("1.0.0", "1.1.0"), app_name=APP)

    move = result.rows[1].moves[0]
    assert move.name == "packageA"
    assert move.direction == "downgrade"
    assert result.intervals[0].summary["downgrade"] == 1


async def test_an_unorderable_move_is_never_counted_as_an_upgrade():
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record(
                "1.0.0", "2026-09-01", {"packageA": ">=1.0.0 <1.9.0"}, app_version="3.0.0"
            ),
            (APP, "1.1.0"): record(
                "1.1.0", "2026-10-01", {"packageA": ">=1.1.0 <2.0.0"}, app_version="3.0.0"
            ),
        }
    )

    result = await service.compare(request("1.0.0", "1.1.0"), app_name=APP)

    move = result.rows[1].moves[0]
    assert move.state == "changed"
    assert move.direction is None
    assert move.orderable is False
    assert result.intervals[0].summary["upgrade"] == 0
    assert result.intervals[0].summary["downgrade"] == 0


async def test_only_the_applications_direct_dependencies_are_compared():
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record(
                "1.0.0",
                "2026-09-01",
                {"packageA": "1.0.0"},
                packages=[{"package_name": "packageA", "version": "1.0.0", "dependencies": {}}],
                app_version="3.0.0",
            ),
            (APP, "1.1.0"): record(
                "1.1.0",
                "2026-10-01",
                {"packageA": "1.0.0"},
                # a transitive package moves, and must not enter the matrix
                packages=[{"package_name": "packageA", "version": "9.9.9", "dependencies": {}}],
                app_version="3.0.0",
            ),
        }
    )

    result = await service.compare(request("1.0.0", "1.1.0"), app_name=APP)

    # the application, then the one dependency it declares - the transitive
    # package that moved is not part of this comparison
    assert [row.name for row in result.rows] == [APP, "packageA"]
    assert result.intervals[0].dependencies_moved is False
    assert result.verdict == "identical"


async def test_releases_that_match_everywhere_read_as_identical():
    # the application holds its own version still as well: nothing moved at all
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record(
                "1.0.0", "2026-09-01", {"packageA": "1.0.0"}, app_version="2.0.0"
            ),
            (APP, "1.1.0"): record(
                "1.1.0", "2026-10-01", {"packageA": "1.0.0"}, app_version="2.0.0"
            ),
        }
    )

    result = await service.compare(request("1.0.0", "1.1.0"), app_name=APP)

    assert result.verdict == "identical"
    assert result.intervals[0].changes == []
    assert result.summary["changed"] == 0
    assert result.rows[0].moves[0].state == "unchanged"


# ---------------------------------------------------------------------- #
# The release datetime timeline
# ---------------------------------------------------------------------- #


async def test_the_releases_are_ordered_by_their_datetimes():
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "1.0.0"}),
            (APP, "1.1.0"): record("1.1.0", "2026-10-01", {"packageA": "1.0.0"}),
            (APP, "1.2.0"): record("1.2.0", "2026-11-01", {"packageA": "1.0.0"}),
        }
    )

    # supplied backwards, presented forwards
    result = await service.compare(request("1.2.0", "1.0.0", "1.1.0"), app_name=APP)

    assert [release.ref for release in result.releases] == ["1.0.0", "1.1.0", "1.2.0"]
    assert [(i.source_ref, i.target_ref) for i in result.intervals] == [
        ("1.0.0", "1.1.0"),
        ("1.1.0", "1.2.0"),
    ]


async def test_a_release_without_a_record_is_placed_by_its_tag_date():
    service, _, provider = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "1.0.0"}),
            (APP, "1.1.0"): record("1.1.0", "2026-11-01", {"packageA": "1.0.0"}),
        },
        # 1.9.0 has no record, so its tag is the only thing that can place it
        tags=[{"name": "1.9.0", "sha": "b" * 40, "date": 1790812800000}],
    )

    result = await service.compare(request("1.1.0", "1.0.0", "1.9.0"), app_name=APP)

    assert provider.listings == 1
    releases = {release.ref: release for release in result.releases}
    # 1.0.0 (2026-09-01), then 1.9.0 by its tag date (2026-10-01), then 1.1.0
    assert [release.ref for release in result.releases] == ["1.0.0", "1.9.0", "1.1.0"]
    assert releases["1.9.0"].released_at == "2026-10-01"
    assert releases["1.9.0"].has_record is False


async def test_a_release_with_neither_date_keeps_its_relative_position():
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "1.0.0"}),
        },
        tags=[],
    )

    result = await service.compare(request("main", "develop", "1.0.0"), app_name=APP)

    # dated first; the two undated branches keep the order they were chosen in
    assert [release.ref for release in result.releases] == ["1.0.0", "main", "develop"]
    assert all(release.released_at is None for release in result.releases if release.ref != "1.0.0")


async def test_the_tag_dates_are_not_read_when_every_release_has_a_record():
    service, _, provider = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "1.0.0"}),
            (APP, "1.1.0"): record("1.1.0", "2026-10-01", {"packageA": "1.0.0"}),
        }
    )

    await service.compare(request("1.0.0", "1.1.0"), app_name=APP)

    assert provider.listings == 0


# ---------------------------------------------------------------------- #
# A release the source holds no record for
# ---------------------------------------------------------------------- #


async def test_a_missing_record_marks_the_column_and_its_intervals():
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "1.0.0"}),
            (APP, "1.1.0"): record("1.1.0", "2026-10-01", {"packageA": "1.0.1"}),
        }
    )

    result = await service.compare(request("1.0.0", "1.1.0", "1.2.0"), app_name=APP)

    releases = {release.ref: release for release in result.releases}
    assert releases["1.2.0"].has_record is False

    intervals = {(i.source_ref, i.target_ref): i for i in result.intervals}
    assert intervals[("1.0.0", "1.1.0")].complete is True
    assert intervals[("1.1.0", "1.2.0")].complete is False
    assert result.verdict == "incomplete"


async def test_an_incomplete_interval_is_never_reported_as_no_changes():
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "1.0.0"}),
        }
    )

    result = await service.compare(request("1.0.0", "1.9.0"), app_name=APP)

    interval = result.intervals[0]
    assert interval.complete is False
    assert interval.changes == []
    assert interval.dependencies_moved is False
    # nothing is known, so nothing is counted and nothing is claimed
    assert sum(interval.summary.values()) == 0
    assert result.verdict == "incomplete"
    assert result.rows[0].moves == [None]


async def test_the_intervals_that_can_be_compared_are_still_reported():
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record(
                "1.0.0", "2026-09-01", {"packageA": "1.0.0"}, app_version="3.0.0"
            ),
            (APP, "1.1.0"): record(
                "1.1.0", "2026-10-01", {"packageA": "1.0.1"}, app_version="3.0.0"
            ),
        }
    )

    result = await service.compare(request("1.0.0", "1.1.0", "2.0.0"), app_name=APP)

    complete = [i for i in result.intervals if i.complete]
    assert len(complete) == 1
    assert complete[0].summary["upgrade"] == 1
    # the totals count only what could be compared
    assert result.summary["upgrade"] == 1
    assert result.verdict == "incomplete"


async def test_an_application_the_source_does_not_know_has_no_columns():
    service, _, _ = build_service({})

    result = await service.compare(request("1.0.0", "1.1.0"), app_name=APP)

    assert result.rows == []
    assert all(release.has_record is False for release in result.releases)
    assert result.verdict == "incomplete"


async def test_an_unreachable_source_is_reported_rather_than_emptied():
    service, _, _ = build_service({}, client=UnreachableClient())

    with pytest.raises(DependencyApiException):
        await service.compare(request("1.0.0", "1.1.0"), app_name=APP)


# ---------------------------------------------------------------------- #
# Cache
# ---------------------------------------------------------------------- #


async def test_a_repeated_comparison_is_served_from_the_cache():
    service, cache, _ = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "1.0.0"}),
            (APP, "1.1.0"): record("1.1.0", "2026-10-01", {"packageA": "1.0.1"}),
        }
    )

    first = await service.compare(request("1.0.0", "1.1.0"), app_name=APP)
    second = await service.compare(request("1.1.0", "1.0.0"), app_name=APP)

    assert cache.writes == 1
    # the refs supplied in another order are the same comparison
    assert second.model_dump() == first.model_dump()


async def test_refresh_reads_the_source_again():
    service, cache, _ = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "1.0.0"}),
            (APP, "1.1.0"): record("1.1.0", "2026-10-01", {"packageA": "1.0.1"}),
        }
    )

    await service.compare(request("1.0.0", "1.1.0"), app_name=APP)
    await service.compare(request("1.0.0", "1.1.0", refresh=True), app_name=APP)

    assert cache.writes == 2


# ---------------------------------------------------------------------- #
# The code axis
# ---------------------------------------------------------------------- #


def three_releases() -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "1.0.0"}),
        (APP, "1.1.0"): record("1.1.0", "2026-10-01", {"packageA": "1.0.0"}),
        (APP, "1.2.0"): record("1.2.0", "2026-11-01", {"packageA": "1.0.1"}),
    }


async def test_the_code_axis_runs_for_every_pair_that_can_be_compared():
    diff = FakeDiff(added=3)
    service, _, _ = build_service(three_releases(), diff=diff)

    result = await service.compare(request("1.0.0", "1.1.0", "1.2.0"), app_name=APP)

    # one comparison per pair, in timeline order
    assert diff.calls == [("1.0.0", "1.1.0"), ("1.1.0", "1.2.0")]
    assert result.intervals[0].code.added_count == 3
    assert result.intervals[1].code.added_count == 3
    # the counts are exact; only the rendered lists are capped
    assert diff.requests[0].render_limit == 30


async def test_a_pair_with_no_dependency_change_still_reports_its_commits():
    # the case the code axis exists for: a tag was rebuilt, its versions did not move
    diff = FakeDiff(added=7)
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record(
                "1.0.0", "2026-09-01", {"packageA": "1.0.0"}, app_version="3.0.0"
            ),
            (APP, "1.1.0"): record(
                "1.1.0", "2026-10-01", {"packageA": "1.0.0"}, app_version="3.0.0"
            ),
        },
        diff=diff,
    )

    result = await service.compare(request("1.0.0", "1.1.0"), app_name=APP)

    interval = result.intervals[0]
    assert interval.summary["changed"] == 0
    assert interval.summary["added"] == 0
    assert interval.summary["removed"] == 0
    assert interval.dependencies_moved is False
    # so the page can say that commits moved while the dependencies did not
    assert interval.code.added_count == 7


async def test_a_pair_whose_commits_cannot_be_read_keeps_its_dependencies():
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record(
                "1.0.0", "2026-09-01", {"packageA": "1.0.0"}, app_version="3.0.0"
            ),
            (APP, "1.1.0"): record(
                "1.1.0", "2026-10-01", {"packageA": "1.0.1"}, app_version="3.0.0"
            ),
        },
        diff=FakeDiff(fail="provider unreachable"),
    )

    result = await service.compare(request("1.0.0", "1.1.0"), app_name=APP)

    interval = result.intervals[0]
    # the reason is carried rather than an empty commit list that reads as "none"
    assert interval.code.unavailable == "provider unreachable"
    assert interval.code.added_commits == []
    # and the dependency axis stands
    assert interval.summary["upgrade"] == 1
    assert result.rows[1].moves[0].direction == "upgrade"


async def test_an_incomplete_pair_is_not_asked_for_its_commits():
    diff = FakeDiff(added=1)
    service, _, _ = build_service(
        {(APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "1.0.0"})},
        diff=diff,
    )

    result = await service.compare(request("1.0.0", "1.9.0"), app_name=APP)

    assert diff.calls == []
    assert result.intervals[0].complete is False
    assert result.intervals[0].code is None


async def test_the_code_axis_is_skipped_when_it_is_not_asked_for():
    diff = FakeDiff(added=1)
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "1.0.0"}),
            (APP, "1.1.0"): record("1.1.0", "2026-10-01", {"packageA": "1.0.0"}),
        },
        diff=diff,
    )

    result = await service.compare(request("1.0.0", "1.1.0", include_code=False), app_name=APP)

    assert diff.calls == []
    assert result.intervals[0].code is None


async def test_a_comparison_without_the_code_axis_is_cached_apart():
    service, cache, _ = build_service(three_releases(), diff=FakeDiff(added=1))

    without = await service.compare(request("1.0.0", "1.1.0", include_code=False), app_name=APP)
    with_code = await service.compare(request("1.0.0", "1.1.0"), app_name=APP)

    assert without.intervals[0].code is None
    # the answer to the other request is not served as if it carried the commits
    assert with_code.intervals[0].code is not None
    assert cache.writes == 2


async def test_refresh_reaches_the_provider_comparison_too():
    diff = FakeDiff(added=1)
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "1.0.0"}),
            (APP, "1.1.0"): record("1.1.0", "2026-10-01", {"packageA": "1.0.0"}),
        },
        diff=diff,
    )

    await service.compare(request("1.0.0", "1.1.0", refresh=True), app_name=APP)

    assert diff.requests[0].refresh is True


# ---------------------------------------------------------------------- #
# The dependency axis: each package's own two versions, compared
# ---------------------------------------------------------------------- #


def package_resolver(**repositories: DependencyRepository) -> Any:
    """A resolver answering with the repository each package name was handed.

    A package it was not handed is one the project registry does not know, which
    is what an external library looks like.
    """

    async def resolve(name: str) -> DependencyRepository:
        return repositories.get(
            name, DependencyRepository(reason=f"no repository is registered as '{name}'")
        )

    return resolve


async def test_the_application_is_compared_at_the_tag_its_record_names():
    """The reader picks a release; the record names the tag the build was cut from."""
    diff = FakeDiff(added=1)
    service, _, _ = build_service(
        {
            (APP, "v1.0.0"): record(
                "v1.0.0", "2026-09-01", {"packageA": "1.0.0"}, app_version="1.0.0_10000"
            ),
            (APP, "v1.1.0"): record(
                "v1.1.0", "2026-10-01", {"packageA": "1.0.0"}, app_version="1.1.0_10000"
            ),
        },
        diff=diff,
    )

    await service.compare(request("v1.0.0", "v1.1.0"), app_name=APP)

    assert (diff.requests[0].source_ref, diff.requests[0].target_ref) == (
        "1.0.0_10000",
        "1.1.0_10000",
    )


async def test_a_moved_dependency_is_compared_in_its_own_repository():
    """A package's version is the tag it was released under, so it is the ref to compare."""
    diff = FakeDiff(added=2)
    service, _, _ = build_service(
        {
            (APP, "1.0.0_10000"): record("1.0.0_10000", "2026-09-01", {"packageA": "1.0.0"}),
            (APP, "1.1.0_10000"): record("1.1.0_10000", "2026-10-01", {"packageA": "1.1.0"}),
        },
        diff=diff,
    )

    result = await service.compare(
        request("1.0.0_10000", "1.1.0_10000"),
        app_name=APP,
        resolve_dependency_repository=package_resolver(
            packageA=DependencyRepository(
                project_key="CORE", repository_slug="pkg-a", git_provider="bitbucket_server"
            )
        ),
    )

    packages = result.intervals[0].packages
    assert [(entry.name, entry.state) for entry in packages] == [("packageA", "changed")]
    entry = packages[0]
    assert (entry.project_key, entry.repository_slug, entry.git_provider) == (
        "CORE",
        "pkg-a",
        "bitbucket_server",
    )
    assert (entry.source_version, entry.target_version) == ("1.0.0", "1.1.0")
    assert entry.code.verdict == "contained"
    assert entry.code.added_count == 2

    # the package was asked of its own repository, at its two versions as refs
    package_request = next(item for item in diff.requests if item.repository_slug == "pkg-a")
    assert (package_request.source_ref, package_request.target_ref) == ("1.0.0", "1.1.0")
    # while the application's own axis stays the application's repository
    application_request = next(
        item for item in diff.requests if item.repository_slug == REPOSITORY
    )
    assert application_request.project_key == PROJECT


async def test_a_dependency_with_no_registered_repository_is_reported_not_compared():
    """An external package has no repository here, which is not a package that matched."""
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "1.0.0"}),
            (APP, "1.1.0"): record("1.1.0", "2026-10-01", {"packageA": "1.1.0"}),
        }
    )

    result = await service.compare(
        request("1.0.0", "1.1.0"),
        app_name=APP,
        resolve_dependency_repository=package_resolver(),
    )

    entry = result.intervals[0].packages[0]
    assert entry.project_key is None
    assert entry.code.verdict == "inconclusive"
    assert entry.code.unavailable == "no repository is registered as 'packageA'"
    assert (entry.code.added_count, entry.code.missing_count) == (0, 0)


async def test_an_added_dependency_has_no_pair_of_versions_to_compare():
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {}),
            (APP, "1.1.0"): record("1.1.0", "2026-10-01", {"packageD": "0.9.0"}),
        }
    )

    result = await service.compare(
        request("1.0.0", "1.1.0"),
        app_name=APP,
        resolve_dependency_repository=package_resolver(
            packageD=DependencyRepository(project_key="CORE", repository_slug="pkg-d")
        ),
    )

    entry = result.intervals[0].packages[0]
    assert entry.state == "added"
    assert "only one version is recorded" in (entry.code.unavailable or "")
    assert entry.code.verdict == "inconclusive"


async def test_a_pairs_first_packages_are_read_and_the_rest_deferred(monkeypatch):
    """A release that moved a dozen packages is drawn from its first few.

    What the ceiling leaves out has to read as what it is: a comparison waiting its
    turn, not one that was made and found equal, and not one that cannot be made.
    """
    monkeypatch.setattr(settings, "APP_DIFF_MAX_PACKAGE_COMPARISONS", 1)
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record(
                "1.0.0", "2026-09-01", {"packageA": "1.0.0", "packageB": "1.0.0"}
            ),
            (APP, "1.1.0"): record(
                "1.1.0", "2026-10-01", {"packageA": "1.1.0", "packageB": "1.1.0"}
            ),
        }
    )

    result = await service.compare(
        request("1.0.0", "1.1.0"),
        app_name=APP,
        resolve_dependency_repository=package_resolver(
            packageA=DependencyRepository(project_key="CORE", repository_slug="pkg-a"),
            packageB=DependencyRepository(project_key="CORE", repository_slug="pkg-b"),
        ),
    )

    entries = {entry.name: entry for entry in result.intervals[0].packages}
    # the pair's first package is read
    assert entries["packageA"].code.unavailable is None
    assert entries["packageA"].code.deferred is False
    # the rest is deferred, carrying where it lives so it can still be asked for
    assert entries["packageB"].code.deferred is True
    assert entries["packageB"].code.unavailable is None
    assert entries["packageB"].repository_slug == "pkg-b"
    # and the page is told how much more it may read on its own
    assert result.auto_compare_remaining == settings.APP_DIFF_MAX_TOTAL_PACKAGE_COMPARISONS - 1


async def test_each_pair_gets_its_own_share_of_the_ceiling(monkeypatch):
    """One pair must not spend the read of the pairs beside it."""
    monkeypatch.setattr(settings, "APP_DIFF_MAX_PACKAGE_COMPARISONS", 1)
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "1.0.0"}),
            (APP, "1.1.0"): record("1.1.0", "2026-10-01", {"packageA": "1.1.0"}),
            (APP, "1.2.0"): record("1.2.0", "2026-11-01", {"packageA": "1.2.0"}),
        }
    )

    result = await service.compare(
        request("1.0.0", "1.1.0", "1.2.0"),
        app_name=APP,
        resolve_dependency_repository=package_resolver(
            packageA=DependencyRepository(project_key="CORE", repository_slug="pkg-a"),
        ),
    )

    assert [interval.packages[0].code.deferred for interval in result.intervals] == [False, False]


async def test_a_downgrade_is_read_before_an_upgrade(monkeypatch):
    """The ceiling must never be what hides a package that moved backwards."""
    monkeypatch.setattr(settings, "APP_DIFF_MAX_PACKAGE_COMPARISONS", 1)
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record(
                "1.0.0", "2026-09-01", {"aUp": "1.0.0", "zDown": "2.0.0"}
            ),
            (APP, "1.1.0"): record(
                "1.1.0", "2026-10-01", {"aUp": "1.1.0", "zDown": "1.0.0"}
            ),
        }
    )

    result = await service.compare(
        request("1.0.0", "1.1.0"),
        app_name=APP,
        resolve_dependency_repository=package_resolver(
            aUp=DependencyRepository(project_key="CORE", repository_slug="pkg-up"),
            zDown=DependencyRepository(project_key="CORE", repository_slug="pkg-down"),
        ),
    )

    entries = {entry.name: entry for entry in result.intervals[0].packages}
    # the downgrade is read although the matrix order would have read the upgrade
    assert entries["zDown"].code.deferred is False
    assert entries["aUp"].code.deferred is True


async def test_the_total_ceiling_bounds_a_whole_page(monkeypatch):
    """Two pairs do not buy two ceilings: a page reads a bounded number, and says so."""
    monkeypatch.setattr(settings, "APP_DIFF_MAX_PACKAGE_COMPARISONS", 5)
    monkeypatch.setattr(settings, "APP_DIFF_MAX_TOTAL_PACKAGE_COMPARISONS", 1)
    diff = FakeDiff()
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "1.0.0"}),
            (APP, "1.1.0"): record("1.1.0", "2026-10-01", {"packageA": "1.1.0"}),
            (APP, "1.2.0"): record("1.2.0", "2026-11-01", {"packageA": "1.2.0"}),
        },
        diff=diff,
    )

    result = await service.compare(
        request("1.0.0", "1.1.0", "1.2.0"),
        app_name=APP,
        resolve_dependency_repository=package_resolver(
            packageA=DependencyRepository(project_key="CORE", repository_slug="pkg-a"),
        ),
    )

    package_reads = [item for item in diff.requests if item.repository_slug == "pkg-a"]
    assert len(package_reads) == 1
    assert result.auto_compare_remaining == 0
    # the pair that did not get its read says so, and is still askable
    deferred = [
        entry
        for interval in result.intervals
        for entry in interval.packages
        if entry.code.deferred
    ]
    assert [entry.name for entry in deferred] == ["packageA"]


# ---------------------------------------------------------------------- #
# Reading the deferred packages in batches
# ---------------------------------------------------------------------- #


def package_batch(*packages: tuple[str, str, str]) -> AppVersionDiffPackagesRequest:
    """A batch request in the shape the page sends it."""
    return AppVersionDiffPackagesRequest(
        project_key=PROJECT,
        repository_slug=REPOSITORY,
        git_provider="bitbucket_server",
        source_ref="1.0.0",
        target_ref="1.1.0",
        packages=[
            AppVersionDiffPackageRequest(name=name, source_version=source, target_version=target)
            for name, source, target in packages
        ],
    )


async def test_a_batch_reads_the_packages_it_names():
    """A deferred package is read the way the first response reads one."""
    diff = FakeDiff(added=2)
    service, _, _ = build_service({}, diff=diff)

    response = await service.compare_packages(
        package_batch(("packageA", "1.0.0", "1.1.0")),
        resolve_dependency_repository=package_resolver(
            packageA=DependencyRepository(project_key="CORE", repository_slug="pkg-a")
        ),
    )

    assert (response.source_ref, response.target_ref) == ("1.0.0", "1.1.0")
    entry = response.packages[0]
    assert entry.name == "packageA"
    assert entry.state == "changed"
    assert entry.code.verdict == "contained"
    assert entry.code.added_count == 2
    assert entry.code.deferred is False
    # read at its two versions, in the repository the registry named for it
    assert diff.requests[-1].repository_slug == "pkg-a"
    assert (diff.requests[-1].source_ref, diff.requests[-1].target_ref) == ("1.0.0", "1.1.0")


async def test_a_batch_package_the_registry_cannot_place_is_reported_not_dropped():
    """A batch answers for every package it was asked about."""
    service, _, _ = build_service({}, diff=FakeDiff())

    response = await service.compare_packages(
        package_batch(("packageB", "1.0.0", "1.1.0")),
        resolve_dependency_repository=package_resolver(),
    )

    entry = response.packages[0]
    assert entry.name == "packageB"
    assert entry.code.verdict == "inconclusive"
    assert entry.code.unavailable == "no repository is registered as 'packageB'"
    assert entry.code.deferred is False
