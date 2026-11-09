"""Regression tests for repository-scoped visibility on the read path."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token, get_repository_access
from src.core.repository_access import access_scope, repository_pair_condition
from src.main import app
from src.models.auth_user import AuthUser
from src.models.project import Project
from src.models.project_registry import ProjectRegistry
from src.models.pull_request import PullRequestReviewBase
from src.models.repository import Repository
from src.services.project_service import ProjectService
from src.services.sse_broker import _is_user_involved_in_review


@pytest.fixture
async def catalog(db: AsyncSession):
    db.add_all(
        [
            Project(project_id=1, project_key="ONE", project_name="One", project_url="https://x/ONE"),
            Project(project_id=2, project_key="TWO", project_name="Two", project_url="https://x/TWO"),
        ]
    )
    await db.flush()
    db.add_all(
        [
            Repository(
                repository_id=11,
                project_id=1,
                repository_name="A",
                repository_slug="a",
                repository_url="https://x/ONE/a",
            ),
            Repository(
                repository_id=12,
                project_id=1,
                repository_name="Hidden",
                repository_slug="hidden",
                repository_url="https://x/ONE/hidden",
            ),
            Repository(
                repository_id=22,
                project_id=2,
                repository_name="B",
                repository_slug="b",
                repository_url="https://x/TWO/b",
            ),
            ProjectRegistry(app_name="App One", project_key="ONE", repository_slug="a"),
            ProjectRegistry(app_name="App Two", project_key="TWO", repository_slug="b"),
        ]
    )
    await db.commit()


@pytest.fixture
def scoped_client(async_client: AsyncClient, db_session: AsyncSession):
    async def _user():
        return AuthUser(id=1, username="scoped", email="scoped@example.com")

    async def _db():
        yield db_session

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_current_user_with_token] = _user
    yield async_client
    for dependency in (get_db_session, get_current_user_with_token, get_repository_access):
        app.dependency_overrides.pop(dependency, None)


@pytest.mark.asyncio
async def test_project_service_only_returns_granted_projects(db: AsyncSession, catalog):
    service = ProjectService(allowed_project_keys={"ONE"})
    projects, total = await service.list_projects(db, use_cache=False)
    assert total == 1
    assert [project.project_key for project in projects] == ["ONE"]


@pytest.mark.asyncio
async def test_project_service_without_grants_returns_nothing(db: AsyncSession, catalog):
    service = ProjectService(allowed_project_keys=set())
    projects, total = await service.list_projects(db, use_cache=False)
    assert (projects, total) == ([], 0)


@pytest.mark.asyncio
async def test_projects_endpoint_requires_authentication(
    async_client: AsyncClient, db_session: AsyncSession, catalog
):
    async def _db():
        yield db_session

    app.dependency_overrides[get_db_session] = _db
    try:
        response = await async_client.get("/api/v1/projects")
    finally:
        app.dependency_overrides.pop(get_db_session, None)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_projects_endpoint_without_grants_returns_empty_list(
    scoped_client: AsyncClient, db_session: AsyncSession, catalog
):
    app.dependency_overrides[get_repository_access] = lambda: set()
    response = await scoped_client.get("/api/v1/projects")
    assert response.status_code == 200
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_projects_endpoint_rejects_ungranted_project(
    scoped_client: AsyncClient, db_session: AsyncSession, catalog
):
    app.dependency_overrides[get_repository_access] = lambda: {("ONE", "a")}
    response = await scoped_client.get("/api/v1/projects/key/TWO/repositories")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_project_repositories_endpoint_hides_ungranted_slugs(
    scoped_client: AsyncClient, db_session: AsyncSession, catalog
):
    app.dependency_overrides[get_repository_access] = lambda: {("ONE", "a")}
    response = await scoped_client.get("/api/v1/projects/key/ONE/repositories")
    assert response.status_code == 200
    assert [item["repository_slug"] for item in response.json()] == ["a"]


@pytest.mark.asyncio
async def test_reviews_endpoint_without_grants_returns_empty_list(
    scoped_client: AsyncClient, db_session: AsyncSession, catalog
):
    app.dependency_overrides[get_repository_access] = lambda: set()
    response = await scoped_client.get("/api/v1/reviews")
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_sse_events_require_a_granted_repository():
    review = {
        "project_key": "ONE",
        "repository_slug": "a",
        "pull_request_user": "author",
    }
    assert _is_user_involved_in_review(review, None, True, {("ONE", "a")})
    assert not _is_user_involved_in_review(review, None, True, set())
    assert not _is_user_involved_in_review(review, None, True, {("TWO", "b")})


def test_access_scope_separates_cache_entries():
    assert access_scope(None) == "all"
    assert access_scope(set()) == "none"
    assert access_scope({("ONE", "a")}) != access_scope({("ONE", "a"), ("TWO", "b")})


def test_pair_condition_restricts_both_columns():
    condition = repository_pair_condition(
        PullRequestReviewBase.project_key,
        PullRequestReviewBase.repository_slug,
        {("ONE", "a"), ("TWO", "b")},
    )
    compiled = condition.compile()
    statement = str(compiled)
    assert "project_key" in statement
    assert "repository_slug" in statement
    assert {"ONE", "TWO", "a", "b"} <= {str(value) for value in compiled.params.values()}
