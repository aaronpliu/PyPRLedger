"""Tests for the App Diff endpoint.

The dependency source is answered from the canned data of the client, so no
third-party service is contacted.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.api.v1.endpoints.app_version_diff import (
    get_app_version_diff_service,
    get_registry_service,
)
from src.core.config import settings
from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.main import app
from src.models.auth_user import AuthUser
from src.schemas.app_version_diff import MAX_PACKAGE_BATCH
from src.schemas.release_diff import ReleaseCompareRequest, ReleaseCompareResponse
from src.services.app_version_diff_service import AppVersionDiffService
from src.services.dependency_graph_service import DependencyGraphService
from src.services.dependency_mock_data import MOCK_APP_NAME, MOCK_BRANCH, MOCK_TAG
from src.services.project_registry_service import ProjectRegistryService, dependency_app_name


class FakeCache:
    def __init__(self) -> None:
        self.stored: dict[str, Any] = {}

    async def get_json(self, key: str) -> Any:
        return self.stored.get(key)

    async def set_json(self, key: str, value: Any, expire: int | None = None) -> None:
        self.stored[key] = value


class FakeRegistry(ProjectRegistryService):
    """A registry mapping the repository onto an application name and its alias."""

    def __init__(self, app_name: str = MOCK_APP_NAME, app_alias: str | None = None) -> None:
        self.app_name = app_name
        self.app_alias = app_alias

    async def get_app_name(self, project_key: str, repository_slug: str, db: Any) -> str:
        return self.app_name

    async def get_dependency_app_name(
        self, project_key: str, repository_slug: str, db: Any
    ) -> str:
        # the endpoint's own resolution, so a test states a registration and reads
        # the name the page asks the database for
        return dependency_app_name(self.app_name, self.app_alias)


class FakeDiff:
    """The repository comparison, so the endpoint never reaches a git provider."""

    def __init__(self, added: int = 4) -> None:
        self.added = added
        self.calls: list[tuple[str, str]] = []
        # the whole request, so a test can read which repository and which refs were asked
        self.requests: list[ReleaseCompareRequest] = []

    async def compare_releases(self, request: ReleaseCompareRequest) -> ReleaseCompareResponse:
        self.calls.append((request.source_ref, request.target_ref))
        self.requests.append(request)
        return ReleaseCompareResponse(
            project_key=request.project_key,
            repository_slug=request.repository_slug,
            git_provider="bitbucket_server",
            source_ref=request.source_ref,
            target_ref=request.target_ref,
            verdict="contained",
            scan_complete=True,
            added_count=self.added,
        )


@pytest.fixture
def fake_diff() -> FakeDiff:
    return FakeDiff()


@pytest.fixture
def authenticated_client(db_session, fake_diff):
    """Test client with auth, the registry and the comparison service overridden."""

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    async def _db_session() -> Any:
        yield db_session

    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_db_session] = _db_session
    app.dependency_overrides[get_registry_service] = lambda: FakeRegistry()
    app.dependency_overrides[get_app_version_diff_service] = lambda: AppVersionDiffService(
        cache=FakeCache(),
        graph_service=DependencyGraphService(cache=FakeCache()),
        diff_service=fake_diff,
    )
    yield
    for dependency in (
        get_current_user_with_token,
        get_db_session,
        get_registry_service,
        get_app_version_diff_service,
    ):
        app.dependency_overrides.pop(dependency, None)


def payload(*refs: str, **extra: Any) -> dict[str, Any]:
    return {
        "project_key": "CORE",
        "repository_slug": "app",
        "git_provider": "bitbucket_server",
        "refs": list(refs),
        **extra,
    }


async def test_endpoint_compares_two_releases(async_client, authenticated_client) -> None:
    response = await async_client.post(
        "/api/v1/release/apps/diff", json=payload(MOCK_TAG, MOCK_BRANCH)
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["project_key"] == "CORE"
    assert body["repository_slug"] == "app"
    assert body["app_name"] == MOCK_APP_NAME
    assert body["git_provider"] == "bitbucket_server"

    # the releases are presented by their datetimes, not by the order supplied
    assert [release["ref"] for release in body["releases"]] == [MOCK_TAG, MOCK_BRANCH]
    assert body["releases"][0]["released_at"] == "2026-09-30"
    assert body["releases"][1]["released_at"] == "2026-10-01"
    assert all(release["has_record"] for release in body["releases"])

    # the application's own version is the first row, and the dependencies follow
    assert body["rows"][0]["kind"] == "application"
    assert body["rows"][0]["name"] == MOCK_APP_NAME
    assert body["rows"][0]["versions"] == [MOCK_TAG, MOCK_BRANCH]

    rows = {row["name"]: row for row in body["rows"]}
    # the branch added a module the tag did not declare
    assert rows["packageF"]["versions"] == [None, "0.9.0"]
    assert rows["packageF"]["moves"][0]["state"] == "added"
    assert rows["packageA"]["moves"][0]["state"] == "unchanged"

    interval = body["intervals"][0]
    assert interval["source_ref"] == MOCK_TAG
    assert interval["target_ref"] == MOCK_BRANCH
    assert interval["complete"] is True
    assert interval["dependencies_moved"] is True
    assert interval["summary"]["added"] == 1
    assert body["verdict"] == "changed"


async def test_endpoint_asks_the_database_with_a_lower_case_app_name(
    async_client, authenticated_client
) -> None:
    """The registry keeps the casing an administrator typed; the database is an enum."""
    app.dependency_overrides[get_registry_service] = lambda: FakeRegistry("MyLang")

    response = await async_client.post(
        "/api/v1/release/apps/diff", json=payload(MOCK_TAG, MOCK_BRANCH)
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["app_name"] == MOCK_APP_NAME
    assert all(release["has_record"] for release in body["releases"])


async def test_endpoint_orders_the_releases_by_datetime(async_client, authenticated_client) -> None:
    response = await async_client.post(
        "/api/v1/release/apps/diff", json=payload(MOCK_BRANCH, MOCK_TAG)
    )

    assert response.status_code == 200, response.text
    assert [release["ref"] for release in response.json()["releases"]] == [
        MOCK_TAG,
        MOCK_BRANCH,
    ]


async def test_endpoint_compares_more_than_two_releases(async_client, authenticated_client) -> None:
    response = await async_client.post(
        "/api/v1/release/apps/diff",
        json={
            "project_key": "CORE",
            "repository_slug": "app",
            "git_provider": "bitbucket_server",
            # the canned database answers a ref it does not hold with its newest
            # record, so this is three columns over two distinct shapes
            "refs": [MOCK_TAG, MOCK_BRANCH, "9.9.9"],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["releases"]) == 3
    assert len(body["intervals"]) == 2


async def test_endpoint_reports_the_commits_between_a_pair(
    async_client, authenticated_client, fake_diff
) -> None:
    response = await async_client.post(
        "/api/v1/release/apps/diff", json=payload(MOCK_TAG, MOCK_BRANCH)
    )

    assert response.status_code == 200, response.text
    body = response.json()

    # the pair is the two releases in timeline order
    assert fake_diff.calls == [(MOCK_TAG, MOCK_BRANCH)]
    interval = body["intervals"][0]
    assert interval["code"]["verdict"] == "contained"
    assert interval["code"]["added_count"] == 4
    assert interval["code"]["unavailable"] is None


async def test_endpoint_leaves_the_code_axis_out_when_not_asked(
    async_client, authenticated_client, fake_diff
) -> None:
    response = await async_client.post(
        "/api/v1/release/apps/diff",
        json={
            "project_key": "CORE",
            "repository_slug": "app",
            "git_provider": "bitbucket_server",
            "refs": [MOCK_TAG, MOCK_BRANCH],
            "include_code": False,
        },
    )

    assert response.status_code == 200, response.text
    assert fake_diff.calls == []
    assert response.json()["intervals"][0]["code"] is None


async def test_endpoint_reads_the_budget_the_page_asked_for(
    async_client, authenticated_client
) -> None:
    """A page may ask to read deeper, and is answered with what it actually got."""
    response = await async_client.post(
        "/api/v1/release/apps/diff",
        json=payload(
            MOCK_TAG,
            MOCK_BRANCH,
            max_package_comparisons=25,
            max_total_package_comparisons=200,
        ),
    )

    assert response.status_code == 200, response.text
    budget = response.json()["package_comparisons"]
    assert (budget["per_pair"], budget["page_total"]) == (25, 200)
    # the batch to ask in, and what of the allowance this response left
    assert budget["batch"] == settings.APP_DIFF_PACKAGE_COMPARISON_BATCH_SIZE
    assert 0 <= budget["remaining"] <= 200


async def test_endpoint_answers_a_budget_above_the_ceiling_with_the_ceiling(
    async_client, authenticated_client
) -> None:
    """A dial cannot talk the server into reading without end."""
    response = await async_client.post(
        "/api/v1/release/apps/diff",
        json=payload(
            MOCK_TAG,
            MOCK_BRANCH,
            max_package_comparisons=5000,
            max_total_package_comparisons=50000,
        ),
    )

    assert response.status_code == 200, response.text
    budget = response.json()["package_comparisons"]
    assert budget["per_pair"] == settings.APP_DIFF_PACKAGE_COMPARISONS_CEILING
    assert budget["page_total"] == settings.APP_DIFF_PAGE_COMPARISONS_CEILING


async def test_endpoint_rejects_a_single_release(async_client, authenticated_client) -> None:
    response = await async_client.post("/api/v1/release/apps/diff", json=payload(MOCK_TAG))

    assert response.status_code == 422


async def test_endpoint_rejects_a_repeated_release(async_client, authenticated_client) -> None:
    # two entries that are the same release are one release, which is not a comparison
    response = await async_client.post(
        "/api/v1/release/apps/diff", json=payload(MOCK_TAG, f" {MOCK_TAG} ")
    )

    assert response.status_code == 422


async def test_endpoint_rejects_an_empty_release_name(async_client, authenticated_client) -> None:
    response = await async_client.post("/api/v1/release/apps/diff", json=payload(MOCK_TAG, "   "))

    assert response.status_code == 422


class FakeDependencyClient:
    """A dependency source holding exactly the records it was handed."""

    def __init__(self, records: dict[tuple[str, str], dict[str, Any]]) -> None:
        self.records = records

    async def get_app_release_info(
        self, app_name: str, tag_or_branch: str
    ) -> dict[str, Any] | None:
        return self.records.get((app_name, tag_or_branch))


def record_with(ref: str, created_at: str, dependencies: dict[str, str]) -> dict[str, Any]:
    """One release record in the shape the dependency source answers with."""
    return {
        "app_name": MOCK_APP_NAME,
        "tagOrBranch": ref,
        "created_at": created_at,
        "dependencies": dependencies,
        "packages": [],
    }


async def test_a_moved_package_is_compared_in_the_repository_the_registry_names(
    async_client, authenticated_client, db_session
) -> None:
    """The dependency record names no repository: the registry is what resolves one."""
    registry = ProjectRegistryService()
    await registry.register_project(MOCK_APP_NAME, "CORE", "app", db=db_session)
    # the package is known to the database by a name of its own, which the registry holds
    await registry.register_project(
        "pkg-a-app", "CORE", "pkg-a", db=db_session, app_alias="packageA"
    )

    diff = FakeDiff(added=3)
    client = FakeDependencyClient(
        {
            (MOCK_APP_NAME, MOCK_TAG): record_with(
                MOCK_TAG, "2026-09-30", {"packageA": "1.0.0"}
            ),
            (MOCK_APP_NAME, MOCK_BRANCH): record_with(
                MOCK_BRANCH, "2026-10-01", {"packageA": "1.1.0"}
            ),
        }
    )
    app.dependency_overrides[get_registry_service] = lambda: registry
    app.dependency_overrides[get_app_version_diff_service] = lambda: AppVersionDiffService(
        cache=FakeCache(),
        graph_service=DependencyGraphService(cache=FakeCache(), client=client),
        diff_service=diff,
    )

    response = await async_client.post(
        "/api/v1/release/apps/diff", json=payload(MOCK_TAG, MOCK_BRANCH)
    )

    assert response.status_code == 200, response.text
    packages = response.json()["intervals"][0]["packages"]
    assert [entry["name"] for entry in packages] == ["packageA"]
    entry = packages[0]
    assert (entry["project_key"], entry["repository_slug"]) == ("CORE", "pkg-a")
    assert (entry["source_version"], entry["target_version"]) == ("1.0.0", "1.1.0")
    assert entry["code"]["verdict"] == "contained"
    assert entry["code"]["added_count"] == 3

    # compared in its own repository, at its two versions used as the refs
    package_request = next(
        request for request in diff.requests if request.repository_slug == "pkg-a"
    )
    assert (package_request.source_ref, package_request.target_ref) == ("1.0.0", "1.1.0")
    # and the application itself stays in its own repository
    assert any(request.repository_slug == "app" for request in diff.requests)


def package_batch_payload(*packages: tuple[str, str, str], **extra: Any) -> dict[str, Any]:
    """A batch request in the shape the page sends it."""
    return {
        "project_key": "CORE",
        "repository_slug": "app",
        "git_provider": "bitbucket_server",
        "source_ref": MOCK_TAG,
        "target_ref": MOCK_BRANCH,
        "packages": [
            {"name": name, "source_version": source, "target_version": target}
            for name, source, target in packages
        ],
        **extra,
    }


async def test_a_batch_compares_the_deferred_packages_of_a_pair(
    async_client, authenticated_client, db_session
) -> None:
    """The page asks for what the first response deferred, a batch at a time."""
    registry = ProjectRegistryService()
    await registry.register_project(MOCK_APP_NAME, "CORE", "app", db=db_session)
    await registry.register_project(
        "pkg-a-app", "CORE", "pkg-a", db=db_session, app_alias="packageA"
    )

    diff = FakeDiff(added=3)
    app.dependency_overrides[get_registry_service] = lambda: registry
    app.dependency_overrides[get_app_version_diff_service] = lambda: AppVersionDiffService(
        cache=FakeCache(),
        graph_service=DependencyGraphService(cache=FakeCache()),
        diff_service=diff,
    )

    response = await async_client.post(
        "/api/v1/release/apps/diff/packages",
        json=package_batch_payload(("packageA", "1.0.0", "1.1.0")),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["source_ref"], body["target_ref"]) == (MOCK_TAG, MOCK_BRANCH)
    assert len(body["packages"]) == 1
    entry = body["packages"][0]
    assert entry["name"] == "packageA"
    assert (entry["project_key"], entry["repository_slug"]) == ("CORE", "pkg-a")
    assert (entry["source_version"], entry["target_version"]) == ("1.0.0", "1.1.0")
    assert entry["code"]["verdict"] == "contained"
    assert entry["code"]["added_count"] == 3
    assert entry["code"]["deferred"] is False

    # read at its two versions, in the repository the registry resolved for it
    package_request = next(item for item in diff.requests if item.repository_slug == "pkg-a")
    assert (package_request.source_ref, package_request.target_ref) == ("1.0.0", "1.1.0")


async def test_a_batch_answers_for_a_package_no_repository_is_known_for(
    async_client, authenticated_client
) -> None:
    """An external library is reported, not dropped: the batch answers about it too."""
    response = await async_client.post(
        "/api/v1/release/apps/diff/packages",
        json=package_batch_payload(("packageX", "1.0.0", "1.1.0")),
    )

    assert response.status_code == 200, response.text
    entry = response.json()["packages"][0]
    assert entry["name"] == "packageX"
    assert entry["code"]["verdict"] == "inconclusive"
    assert "packageX" in (entry["code"]["unavailable"] or "")
    assert entry["code"]["deferred"] is False


async def test_a_batch_rejects_an_empty_package_list(
    async_client, authenticated_client
) -> None:
    response = await async_client.post(
        "/api/v1/release/apps/diff/packages",
        json=package_batch_payload(),
    )

    assert response.status_code == 422


async def test_a_batch_rejects_more_packages_than_a_batch_may_carry(
    async_client, authenticated_client
) -> None:
    """A batch is a few packages: a larger request is the ceiling asked around."""
    oversized = [f"package{index}" for index in range(MAX_PACKAGE_BATCH + 1)]

    response = await async_client.post(
        "/api/v1/release/apps/diff/packages",
        json=package_batch_payload(*[(name, "1.0.0", "1.1.0") for name in oversized]),
    )

    assert response.status_code == 422
