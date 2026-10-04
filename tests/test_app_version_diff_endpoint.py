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
from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.main import app
from src.models.auth_user import AuthUser
from src.services.app_version_diff_service import AppVersionDiffService
from src.services.dependency_graph_service import DependencyGraphService
from src.services.dependency_mock_data import MOCK_APP_NAME, MOCK_BRANCH, MOCK_TAG
from src.services.project_registry_service import ProjectRegistryService


class FakeCache:
    def __init__(self) -> None:
        self.stored: dict[str, Any] = {}

    async def get_json(self, key: str) -> Any:
        return self.stored.get(key)

    async def set_json(self, key: str, value: Any, expire: int | None = None) -> None:
        self.stored[key] = value


class FakeRegistry(ProjectRegistryService):
    """A registry mapping the repository onto an application name."""

    def __init__(self, app_name: str = MOCK_APP_NAME) -> None:
        self.app_name = app_name

    async def get_app_name(self, project_key: str, repository_slug: str, db: Any) -> str:
        return self.app_name


@pytest.fixture
def authenticated_client(db_session):
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

    packages = {package["name"]: package for package in body["packages"]}
    # the branch added a module the tag did not declare
    assert packages["packageF"]["versions"] == [None, "0.9.0"]
    assert packages["packageF"]["moves"][0]["state"] == "added"
    assert packages["packageA"]["moves"][0]["state"] == "unchanged"

    interval = body["intervals"][0]
    assert interval["source_ref"] == MOCK_TAG
    assert interval["target_ref"] == MOCK_BRANCH
    assert interval["complete"] is True
    assert interval["summary"]["added"] == 1
    assert body["verdict"] == "changed"


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
