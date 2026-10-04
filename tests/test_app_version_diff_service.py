"""Tests for comparing the releases of one application.

The dependency source is answered by a fake client, so no third-party service is
contacted and every case - an unreachable source included - can be produced.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.core.exceptions import DependencyApiException
from src.schemas.app_version_diff import AppVersionDiffRequest
from src.services.app_version_diff_service import (
    AppVersionDiffService,
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
) -> dict[str, Any]:
    """One release record in the shape the dependency source answers with."""
    return {
        "app_name": app_name,
        "tagOrBranch": ref,
        "created_at": created_at,
        "dependencies": dependencies,
        "packages": packages or [],
    }


def build_service(
    records: dict[tuple[str, str], dict[str, Any]],
    tags: list[dict[str, Any]] | None = None,
    client: Any | None = None,
) -> tuple[AppVersionDiffService, FakeCache, FakeProvider]:
    cache = FakeCache()
    provider = FakeProvider(tags)
    graph = DependencyGraphService(cache=FakeCache(), client=client or FakeClient(records))
    service = AppVersionDiffService(
        cache=cache, graph_service=graph, provider_factory=lambda name: provider
    )
    return service, cache, provider


def request(*refs: str, refresh: bool = False) -> AppVersionDiffRequest:
    return AppVersionDiffRequest(
        project_key=PROJECT,
        repository_slug=REPOSITORY,
        git_provider="bitbucket_server",
        refs=list(refs),
        refresh=refresh,
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

    # the union of both releases, in one stable order, with empty cells kept
    assert [package.name for package in result.packages] == ["a", "b", "c"]
    versions = {package.name: package.versions for package in result.packages}
    assert versions["a"] == ["1.0.0", "1.0.0"]
    assert versions["b"] == ["1.0.0", None]
    assert versions["c"] == [None, "0.1.0"]


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

    moves = {package.name: package.moves[0] for package in result.packages}
    assert moves["packageA"].state == "unchanged"
    assert (moves["packageB"].state, moves["packageB"].direction) == ("changed", "upgrade")
    assert moves["packageC"].state == "unchanged"
    assert moves["packageD"].state == "removed"
    assert moves["packageF"].state == "added"

    interval = result.intervals[0]
    assert interval.complete is True
    assert interval.summary["unchanged"] == 2
    assert interval.summary["changed"] == 1
    assert interval.summary["upgrade"] == 1
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

    move = result.packages[0].moves[0]
    assert move.direction == "downgrade"
    assert result.intervals[0].summary["downgrade"] == 1


async def test_an_unorderable_move_is_never_counted_as_an_upgrade():
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": ">=1.0.0 <1.9.0"}),
            (APP, "1.1.0"): record("1.1.0", "2026-10-01", {"packageA": ">=1.1.0 <2.0.0"}),
        }
    )

    result = await service.compare(request("1.0.0", "1.1.0"), app_name=APP)

    move = result.packages[0].moves[0]
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
            ),
            (APP, "1.1.0"): record(
                "1.1.0",
                "2026-10-01",
                {"packageA": "1.0.0"},
                # a transitive package moves, and must not enter the matrix
                packages=[{"package_name": "packageA", "version": "9.9.9", "dependencies": {}}],
            ),
        }
    )

    result = await service.compare(request("1.0.0", "1.1.0"), app_name=APP)

    assert [package.name for package in result.packages] == ["packageA"]
    assert result.verdict == "identical"


async def test_releases_that_match_everywhere_read_as_identical():
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "1.0.0"}),
            (APP, "1.1.0"): record("1.1.0", "2026-10-01", {"packageA": "1.0.0"}),
        }
    )

    result = await service.compare(request("1.0.0", "1.1.0"), app_name=APP)

    assert result.verdict == "identical"
    assert result.intervals[0].changes == []
    assert result.summary["changed"] == 0


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
    # nothing is known, so nothing is counted and nothing is claimed
    assert sum(interval.summary.values()) == 0
    assert result.verdict == "incomplete"
    assert result.packages[0].moves == [None]


async def test_the_intervals_that_can_be_compared_are_still_reported():
    service, _, _ = build_service(
        {
            (APP, "1.0.0"): record("1.0.0", "2026-09-01", {"packageA": "1.0.0"}),
            (APP, "1.1.0"): record("1.1.0", "2026-10-01", {"packageA": "1.0.1"}),
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

    assert result.packages == []
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
