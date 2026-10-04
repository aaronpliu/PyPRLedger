"""Tests for the release dependency graph read endpoint.

The dependency database is answered from the canned data of the client - no
third-party service is contacted.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.api.v1.endpoints.release_dependency_graph import (
    get_dependency_graph_service,
    get_registry_service,
)
from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.main import app
from src.models.auth_user import AuthUser
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
    """Test client with auth, the registry and the graph service overridden."""

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    async def _db_session() -> Any:
        yield db_session

    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_db_session] = _db_session
    app.dependency_overrides[get_registry_service] = lambda: FakeRegistry()
    app.dependency_overrides[get_dependency_graph_service] = lambda: DependencyGraphService(
        cache=FakeCache()
    )
    yield
    for dependency in (
        get_current_user_with_token,
        get_db_session,
        get_registry_service,
        get_dependency_graph_service,
    ):
        app.dependency_overrides.pop(dependency, None)


async def test_endpoint_reads_the_graph_of_a_tag(async_client, authenticated_client) -> None:
    response = await async_client.post(
        "/api/v1/release/dependency-graph/read",
        json={"project_key": "CORE", "repository_slug": "app", "ref": MOCK_TAG},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "1.0"
    assert body["project_key"] == "CORE"
    assert body["repository_slug"] == "app"
    assert body["ref"] == {"name": MOCK_TAG, "type": "tag", "commit": None}
    assert body["generated_at"] == "2026-09-30"

    packages = {entry["id"]: entry for entry in body["packages"]}
    assert packages[MOCK_APP_NAME]["category"] == 0
    assert packages[MOCK_APP_NAME]["dependencies"] == {
        "packageA": "1.0.0",
        "packageB": "1.0.0",
        "packageC": "1.1.0",
    }
    # a declared module carries the version it shipped and the range it declares
    assert packages["packageA"]["category"] == 2
    assert packages["packageA"]["dependencies"] == {"packageD": ">=1.0.0 <1.9.0"}
    # a package only named by a map is a leaf
    assert packages["packageE"]["category"] == 1
    assert packages["packageE"]["dependencies"] == {}


async def test_endpoint_reads_a_branch(async_client, authenticated_client) -> None:
    response = await async_client.post(
        "/api/v1/release/dependency-graph/read",
        json={"project_key": "CORE", "repository_slug": "app", "ref": MOCK_BRANCH},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ref"]["type"] == "branch"
    assert body["generated_at"] == "2026-10-01"


async def test_endpoint_reports_an_application_the_database_does_not_know(
    async_client, authenticated_client
) -> None:
    # A repository that is not registered resolves to a name with no record
    app.dependency_overrides[get_registry_service] = lambda: FakeRegistry("Unknown")

    response = await async_client.post(
        "/api/v1/release/dependency-graph/read",
        json={"project_key": "CORE", "repository_slug": "unregistered", "ref": MOCK_TAG},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "dependency_graph_not_found"


async def test_endpoint_rejects_a_request_without_a_ref(async_client, authenticated_client) -> None:
    response = await async_client.post(
        "/api/v1/release/dependency-graph/read",
        json={"project_key": "CORE", "repository_slug": "app"},
    )

    assert response.status_code == 422


async def test_endpoint_requires_authentication(async_client) -> None:
    async def _db_session() -> None:
        return None  # 401 is raised before any query runs

    app.dependency_overrides[get_db_session] = _db_session
    try:
        response = await async_client.post(
            "/api/v1/release/dependency-graph/read",
            json={"project_key": "CORE", "repository_slug": "app", "ref": MOCK_TAG},
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 401
