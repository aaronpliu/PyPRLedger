from __future__ import annotations

from typing import Any

import pytest

from src.core.exceptions import DependencyGraphNotFoundException
from src.services.dependency_graph_service import DependencyGraphService
from src.services.dependency_mock_data import (
    MOCK_APP_NAME,
    MOCK_BRANCH,
    MOCK_SECOND_APP_NAME,
    MOCK_SECOND_TAG,
    MOCK_TAG,
)


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


class UnknownClient:
    """A dependency database that holds no record for the application."""

    async def get_app_release_info(
        self, app_name: str, tag_or_branch: str
    ) -> dict[str, Any] | None:
        return None


@pytest.fixture
def service() -> DependencyGraphService:
    return DependencyGraphService(cache=FakeCache())


def packages_of(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["id"]: entry for entry in graph["packages"]}


async def build(
    service: DependencyGraphService,
    ref: str = MOCK_TAG,
    app_name: str = MOCK_APP_NAME,
) -> dict[str, Any]:
    return await service.build(
        app_name=app_name, project_key="CORE", repository_slug="app", ref=ref
    )


async def test_the_application_pins_the_modules_it_declared(service):
    graph = await build(service)

    assert graph["schema_version"] == "1.0"
    assert graph["project_key"] == "CORE"
    assert graph["repository_slug"] == "app"
    assert graph["ref"] == {"name": MOCK_TAG, "type": "tag"}
    # the record names when it was taken, so the page can say when it shipped
    assert graph["generated_at"] == "2026-09-30"

    app = packages_of(graph)[MOCK_APP_NAME]
    assert app["category"] == 0
    assert app["version"] == MOCK_TAG
    # an exact version each: the only edges that carry one
    assert app["dependencies"] == {
        "packageA": "1.0.0",
        "packageB": "1.0.0",
        "packageC": "1.1.0",
    }


async def test_a_declared_module_reads_differently_from_a_transitive_one(service):
    packages = packages_of(await build(service))

    # declared by the application: what it ships
    assert packages["packageA"]["category"] == 2
    assert packages["packageA"]["version"] == "1.0.0"
    assert packages["packageA"]["dependencies"] == {"packageD": ">=1.0.0 <1.9.0"}

    # only ever named by another package, and described by the record all the same
    assert packages["packageD"]["category"] == 1
    assert packages["packageD"]["version"] == "1.5.0"
    assert packages["packageD"]["dependencies"] == {"packageA": ">=1.0.0 <2.0.0"}


async def test_a_package_only_named_by_a_map_becomes_a_leaf(service):
    packages = packages_of(await build(service))

    # no entry describes packageE, so it carries the relationship alone
    assert packages["packageE"]["category"] == 1
    assert packages["packageE"]["version"] == ""
    assert packages["packageE"]["dependencies"] == {}


async def test_every_package_of_the_record_reaches_the_graph(service):
    graph = await build(service)

    assert sorted(packages_of(graph)) == [
        MOCK_APP_NAME,
        "packageA",
        "packageB",
        "packageC",
        "packageD",
        "packageE",
    ]


async def test_the_cycle_between_two_packages_is_carried_through(service):
    packages = packages_of(await build(service))

    # packageA names packageD, and packageD reaches back
    assert "packageD" in packages["packageA"]["dependencies"]
    assert "packageA" in packages["packageD"]["dependencies"]


async def test_a_branch_reads_its_own_record(service):
    graph = await build(service, MOCK_BRANCH)
    packages = packages_of(graph)

    assert graph["ref"] == {"name": MOCK_BRANCH, "type": "branch"}
    assert graph["generated_at"] == "2026-10-01"
    assert "packageF" in packages[MOCK_APP_NAME]["dependencies"]
    assert packages["packageF"]["dependencies"] == {"packageE": ">=0.8.0 <1.0.0"}


async def test_another_application_reads_its_own_graph(service):
    graph = await build(service, MOCK_SECOND_TAG, MOCK_SECOND_APP_NAME)
    packages = packages_of(graph)

    assert graph["ref"]["name"] == MOCK_SECOND_TAG
    assert graph["generated_at"] == "2026-09-28"
    assert packages[MOCK_SECOND_APP_NAME]["category"] == 0
    assert packages[MOCK_SECOND_APP_NAME]["dependencies"] == {
        "mcpCore": "0.1.0",
        "mcpTransport": "0.2.0",
    }

    # two modules over a shared core, and nothing of the other application
    assert sorted(packages) == [
        "mcpCommon",
        "mcpCore",
        "mcpProtocol",
        "mcpTransport",
        MOCK_SECOND_APP_NAME,
    ]
    assert packages["mcpCore"]["category"] == 2
    assert packages["mcpCore"]["dependencies"] == {
        "mcpProtocol": ">=0.1.0 <0.2.0",
        "mcpCommon": ">=0.1.0 <0.2.0",
    }
    # named by three packages and described by none: a leaf
    assert packages["mcpCommon"]["category"] == 1
    assert packages["mcpCommon"]["dependencies"] == {}


async def test_the_graph_is_served_from_the_cache_the_second_time():
    cache = FakeCache()
    service = DependencyGraphService(cache=cache)

    first = await build(service)
    second = await build(service)

    assert first == second
    assert cache.writes == 1


async def test_an_application_the_database_does_not_know_is_reported():
    service = DependencyGraphService(cache=FakeCache(), client=UnknownClient())

    with pytest.raises(DependencyGraphNotFoundException):
        await build(service)
