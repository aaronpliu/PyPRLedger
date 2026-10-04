"""Tests for resolving a repository's git provider and workspace.

No git provider is contacted: the factory hands back a stub, so what is
asserted is which provider a request ends up addressed to, and under which
workspace.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.api.v1.endpoints.release_diff import get_release_diff_service
from src.core.database import get_db_session
from src.core.git_provider import GitProvider
from src.core.permissions import get_current_user_with_token
from src.main import app
from src.models.auth_user import AuthUser
from src.models.project import Project
from src.models.project_registry import ProjectRegistry
from src.models.repository import Repository
from src.schemas.release_diff import ReleaseRefsRequest
from src.services.git_provider_resolver import (
    registered_provider,
    registered_workspace_slug,
    with_repository_provider,
)
from src.services.release_diff_service import ReleaseDiffService


CLOUD_URL = "https://bitbucket.org/aaronpliu/pylang.git"
SERVER_URL = "http://localhost:7990/rest/api/latest/projects/AI/repos/pylang"


class Coordinates(BaseModel):
    """The coordinates every release request carries."""

    project_key: str
    repository_slug: str
    git_provider: str | None = None
    workspace_slug: str | None = None


class FakeRegistry:
    def __init__(self, provider: str | None) -> None:
        self.provider = provider
        self.asked: list[tuple[str, str]] = []

    async def get_git_provider(self, project_key: str, repository_slug: str, db: Any) -> str | None:
        self.asked.append((project_key, repository_slug))
        return self.provider


class FakeCache:
    async def get_json(self, key: str) -> Any:
        return None

    async def set_json(self, key: str, value: Any, expire: int | None = None) -> None:
        return None


class StubProvider:
    """A provider that lists nothing, recording how it was addressed."""

    def __init__(self) -> None:
        self.keys: list[str] = []

    async def list_refs(self, project_key: str, repository_slug: str, limit: int = 100) -> dict:
        self.keys.append(project_key)
        return {"tags": [], "branches": []}


async def seed_repository(
    db_session: Any,
    *,
    provider: str = GitProvider.BITBUCKET_CLOUD.value,
    url: str = CLOUD_URL,
) -> None:
    """Store the repository the release pages ask about."""
    db_session.add(
        Project(
            project_id=1,
            project_name="AI",
            project_key="AI",
            project_url="https://bitbucket.org/aaronpliu",
            git_provider=provider,
        )
    )
    db_session.add(
        Repository(
            repository_id=1,
            project_id=1,
            repository_name="pylang",
            repository_slug="pylang",
            repository_url=url,
        )
    )
    await db_session.flush()


# --------------------------------------------------------------------------- #
# The provider
# --------------------------------------------------------------------------- #


async def test_the_registry_answers_when_the_request_names_no_provider():
    registry = FakeRegistry(GitProvider.BITBUCKET_CLOUD.value)
    payload = Coordinates(project_key="AI", repository_slug="pylang")

    resolved = await with_repository_provider(payload, None, registry)

    assert resolved.git_provider == GitProvider.BITBUCKET_CLOUD.value
    assert registry.asked == [("AI", "pylang")]
    # the request handed in is left as it was
    assert payload.git_provider is None


async def test_a_named_provider_is_taken_at_its_word():
    registry = FakeRegistry(GitProvider.BITBUCKET_CLOUD.value)
    payload = Coordinates(
        project_key="AI", repository_slug="pylang", git_provider="github_enterprise"
    )

    resolved = await with_repository_provider(payload, None, registry)

    assert resolved.git_provider == "github_enterprise"
    assert registry.asked == []


async def test_an_unregistered_repository_keeps_the_configured_default():
    payload = Coordinates(project_key="AI", repository_slug="ghost")

    resolved = await with_repository_provider(payload, None, FakeRegistry(None))

    assert resolved.git_provider is None


async def test_an_unknown_registered_provider_is_not_propagated():
    registry = FakeRegistry("bitbucket_team")

    assert await registered_provider("AI", "pylang", None, registry) is None


async def test_a_request_model_keeps_its_own_type():
    payload = ReleaseRefsRequest(project_key="AI", repository_slug="pylang")

    resolved = await with_repository_provider(
        payload, None, FakeRegistry(GitProvider.BITBUCKET_CLOUD.value)
    )

    assert isinstance(resolved, ReleaseRefsRequest)
    assert resolved.git_provider == GitProvider.BITBUCKET_CLOUD.value


# --------------------------------------------------------------------------- #
# The workspace
# --------------------------------------------------------------------------- #


async def test_the_workspace_comes_from_the_repository_url(db_session):
    await seed_repository(db_session)

    assert await registered_workspace_slug("AI", "pylang", db_session) == "aaronpliu"


async def test_a_repository_url_that_is_not_cloud_names_no_workspace(db_session):
    await seed_repository(
        db_session,
        provider=GitProvider.BITBUCKET_SERVER.value,
        url=SERVER_URL,
    )

    assert await registered_workspace_slug("AI", "pylang", db_session) is None


async def test_a_repository_nobody_stored_names_no_workspace(db_session):
    assert await registered_workspace_slug("AI", "ghost", db_session) is None


async def test_a_cloud_request_carries_the_workspace_of_its_repository(db_session):
    await seed_repository(db_session)
    payload = Coordinates(project_key="AI", repository_slug="pylang")

    resolved = await with_repository_provider(
        payload, db_session, FakeRegistry(GitProvider.BITBUCKET_CLOUD.value)
    )

    assert resolved.git_provider == GitProvider.BITBUCKET_CLOUD.value
    # the project key is an alias, not the workspace
    assert resolved.workspace_slug == "aaronpliu"


async def test_a_server_request_never_gains_a_workspace(db_session):
    await seed_repository(
        db_session,
        provider=GitProvider.BITBUCKET_SERVER.value,
        url=SERVER_URL,
    )
    payload = Coordinates(project_key="AI", repository_slug="pylang")

    resolved = await with_repository_provider(
        payload, db_session, FakeRegistry(GitProvider.BITBUCKET_SERVER.value)
    )

    assert resolved.workspace_slug is None


async def test_a_workspace_the_caller_named_is_left_alone(db_session):
    await seed_repository(db_session)
    payload = Coordinates(project_key="AI", repository_slug="pylang", workspace_slug="chosen")

    resolved = await with_repository_provider(
        payload, db_session, FakeRegistry(GitProvider.BITBUCKET_CLOUD.value)
    )

    assert resolved.workspace_slug == "chosen"


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


def override(provider: StubProvider, db_session: Any) -> list[str]:
    """Wire the client, capturing the provider names the service was built for."""
    names: list[str] = []

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    async def _db_session() -> Any:
        yield db_session

    def _factory(name: str) -> StubProvider:
        names.append(name)
        return provider

    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_db_session] = _db_session
    app.dependency_overrides[get_release_diff_service] = lambda: ReleaseDiffService(
        cache=FakeCache(), provider_factory=_factory
    )
    return names


def clear_overrides() -> None:
    for dependency in (
        get_current_user_with_token,
        get_db_session,
        get_release_diff_service,
    ):
        app.dependency_overrides.pop(dependency, None)


async def test_the_refs_endpoint_addresses_cloud_by_workspace(async_client, db_session) -> None:
    """Nothing named a provider or a workspace, and Cloud needs both."""
    await seed_repository(db_session)
    db_session.add(
        ProjectRegistry(
            app_name="mylang",
            project_key="AI",
            repository_slug="pylang",
            git_provider=GitProvider.BITBUCKET_CLOUD.value,
        )
    )
    await db_session.flush()

    provider = StubProvider()
    names = override(provider, db_session)
    try:
        response = await async_client.post(
            "/api/v1/release/diff/refs",
            json={"project_key": "AI", "repository_slug": "pylang"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["git_provider"] == GitProvider.BITBUCKET_CLOUD.value
    assert names == [GitProvider.BITBUCKET_CLOUD.value]
    # addressed by the workspace the repository lives in, not by the project key
    assert provider.keys == ["aaronpliu"]


async def test_the_refs_endpoint_keeps_the_default_for_an_unregistered_repository(
    async_client, db_session
) -> None:
    provider = StubProvider()
    override(provider, db_session)
    try:
        response = await async_client.post(
            "/api/v1/release/diff/refs",
            json={"project_key": "AI", "repository_slug": "unregistered"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["git_provider"] == GitProvider.BITBUCKET_SERVER.value
    # nothing stored the repository, so the project key stands in
    assert provider.keys == ["AI"]
