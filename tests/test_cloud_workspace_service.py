"""Tests for Bitbucket Cloud workspace suggestions.

No HTTP traffic: the provider is replaced by a stub, the database is the shared
in-memory SQLite fixture.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.git_provider import GitProvider
from src.models.project import Project
from src.models.repository import Repository
from src.services.cloud_workspace_service import (
    CloudWorkspaceService,
    workspace_from_repository_url,
)
from src.services.git_providers.base import BaseGitProvider


class StubProvider(BaseGitProvider):
    """Provider whose workspace discovery result is chosen by the test."""

    def __init__(self, workspaces: list[dict[str, Any]] | None = None, fail: bool = False) -> None:
        self._workspaces = workspaces or []
        self._fail = fail
        self.calls = 0

    @property
    def name(self) -> str:
        return GitProvider.BITBUCKET_CLOUD.value

    async def list_workspaces(self) -> list[dict[str, Any]]:
        self.calls += 1
        if self._fail:
            raise RuntimeError("bitbucket.org unreachable")
        return self._workspaces

    async def get_project_info(self, project_key: str) -> dict[str, Any] | None:
        return None

    async def get_repository_info(self, workspace: str, repo_slug: str) -> dict[str, Any] | None:
        return None

    async def get_user_info(self, username: str) -> dict[str, Any] | None:
        return None


def build_service(provider: StubProvider, configured: str = "") -> CloudWorkspaceService:
    return CloudWorkspaceService(
        provider_factory=lambda _name: provider, configured_workspaces=configured
    )


# --------------------------------------------------------------------------- #
# URL parsing
# --------------------------------------------------------------------------- #


def test_workspace_from_repository_url() -> None:
    assert (
        workspace_from_repository_url("https://bitbucket.org/aaronpliu/pylang.git") == "aaronpliu"
    )
    assert workspace_from_repository_url("https://bitbucket.org/aaronpliu/pylang") == "aaronpliu"
    assert workspace_from_repository_url(
        "https://aaronpliu@bitbucket.org/aaronpliu/pylang.git"
    ) == ("aaronpliu")


def test_workspace_from_repository_url_ignores_other_hosts() -> None:
    assert workspace_from_repository_url("http://localhost:7990/scm/PROJ/repo.git") is None
    assert workspace_from_repository_url("https://github.com/aaronpliu/pyledger") is None
    assert workspace_from_repository_url("https://bitbucket.org/only-one-segment") is None
    assert workspace_from_repository_url(None) is None


# --------------------------------------------------------------------------- #
# Suggestion merging
# --------------------------------------------------------------------------- #


async def test_config_workspaces_come_first_and_are_deduplicated() -> None:
    provider = StubProvider()
    service = build_service(provider, configured=" aaronpliu , acme ,aaronpliu")

    options = await service.list_workspaces()

    assert [option.slug for option in options] == ["aaronpliu", "acme"]
    assert {option.source for option in options} == {"config"}
    assert provider.calls == 1  # the API is still consulted for extra workspaces


async def test_api_workspaces_are_labeled_and_merged() -> None:
    provider = StubProvider(
        [
            {"slug": "aaronpliu", "name": "Aaron Liu"},
            {"slug": "acme", "name": "Acme Corp"},
        ]
    )
    service = build_service(provider, configured="aaronpliu")

    options = await service.list_workspaces()

    assert [option.slug for option in options] == ["aaronpliu", "acme"]
    assert options[0].source == "config"
    assert options[1].source == "api"
    assert options[1].name == "Acme Corp"


async def test_api_failure_does_not_break_the_suggestions() -> None:
    service = build_service(StubProvider(fail=True), configured="aaronpliu")

    options = await service.list_workspaces()

    assert [option.slug for option in options] == ["aaronpliu"]


async def test_database_workspaces_come_from_repository_urls(db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            Project(
                project_id=1,
                project_key="AI",
                project_name="AI",
                project_url="https://bitbucket.org/aaronpliu",
                git_provider=GitProvider.BITBUCKET_CLOUD.value,
            ),
            Project(
                project_id=2,
                project_key="LEGACY",
                project_name="LEGACY",
                project_url="https://bitbucket.org/legacy",
                git_provider=GitProvider.BITBUCKET_CLOUD.value,
            ),
            Project(
                project_id=3,
                project_key="PROJ",
                project_name="PROJ",
                project_url="http://localhost:7990/projects/PROJ",
                git_provider=GitProvider.BITBUCKET_SERVER.value,
            ),
        ]
    )
    db_session.add_all(
        [
            Repository(
                repository_id=1,
                project_id=1,
                repository_name="pylang",
                repository_slug="pylang",
                repository_url="https://bitbucket.org/aaronpliu/pylang.git",
            ),
            Repository(
                repository_id=2,
                project_id=3,
                repository_name="pyledger",
                repository_slug="pyledger",
                repository_url="http://localhost:7990/scm/PROJ/pyledger.git",
            ),
        ]
    )
    await db_session.flush()

    options = await build_service(StubProvider()).list_workspaces(db_session)

    # `aaronpliu` comes from the repository URL, `LEGACY` from the project without
    # a repository, and the Bitbucket Server project is ignored entirely.
    assert [option.slug for option in options] == ["aaronpliu", "LEGACY"]
    assert {option.source for option in options} == {"database"}


async def test_aliased_cloud_project_key_is_not_offered_as_workspace(
    db_session: AsyncSession,
) -> None:
    """A Cloud project key may be a business alias - the URL holds the true workspace."""
    db_session.add(
        Project(
            project_id=10,
            project_key="AI",
            project_name="AI",
            project_url="https://bitbucket.org/aaronpliu",
            git_provider=GitProvider.BITBUCKET_CLOUD.value,
        )
    )
    db_session.add(
        Repository(
            repository_id=10,
            project_id=10,
            repository_name="pylang",
            repository_slug="pylang",
            repository_url="https://bitbucket.org/aaronpliu/pylang.git",
        )
    )
    await db_session.flush()

    options = await build_service(StubProvider()).list_workspaces(db_session)

    assert [option.slug for option in options] == ["aaronpliu"]


# --------------------------------------------------------------------------- #
# Endpoint
# --------------------------------------------------------------------------- #


async def test_endpoint_returns_workspace_suggestions(async_client, db_session) -> None:
    from src.api.v1.endpoints.projects import get_cloud_workspace_service
    from src.core.database import get_db_session
    from src.main import app

    service = build_service(StubProvider(), configured="aaronpliu")

    async def _db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = _db_session
    app.dependency_overrides[get_cloud_workspace_service] = lambda: service
    try:
        response = await async_client.get("/api/v1/projects/cloud-workspaces")
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_cloud_workspace_service, None)

    assert response.status_code == 200
    assert [option["slug"] for option in response.json()["workspaces"]] == ["aaronpliu"]
    assert response.json()["workspaces"][0]["source"] == "config"


async def test_endpoint_route_is_not_shadowed_by_project_id(async_client, db_session) -> None:
    """``/projects/cloud-workspaces`` must not be parsed as a project id."""
    from src.api.v1.endpoints.projects import get_cloud_workspace_service
    from src.core.database import get_db_session
    from src.main import app

    async def _db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = _db_session
    app.dependency_overrides[get_cloud_workspace_service] = lambda: build_service(StubProvider())
    try:
        response = await async_client.get("/api/v1/projects/cloud-workspaces")
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_cloud_workspace_service, None)

    assert response.status_code == 200
    assert response.json() == {"workspaces": []}
