"""Tests for explicit user-to-repository visibility grants."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.endpoints import repository_access as access_endpoint
from src.core.database import get_db_session
from src.core.exceptions import NotFoundException, ValidationException
from src.core.permissions import get_current_user_with_token
from src.main import app
from src.models.auth_user import AuthUser
from src.models.project import Project
from src.models.project_registry import ProjectRegistry
from src.models.repository import Repository
from src.models.user import User
from src.services.rbac_service import RBACService
from src.services.repository_access_service import RepositoryAccessService
from src.utils.password import hash_password


@pytest.fixture
async def access_data(db: AsyncSession) -> dict:
    git_user = User(
        user_id=101,
        username="alice",
        display_name="Alice",
        email_address="alice@test.com",
    )
    linked = AuthUser(
        username="alice",
        email="alice@test.com",
        password_hash=hash_password("password123"),
    )
    unlinked = AuthUser(
        username="bob",
        email="bob@test.com",
        password_hash=hash_password("password123"),
    )
    db.add_all([git_user, linked, unlinked])
    await db.flush()
    linked.user_id = git_user.id

    project = Project(
        project_id=1,
        project_name="Project One",
        project_key="PROJ",
        project_url="https://example.com/PROJ",
    )
    db.add(project)
    await db.flush()

    db.add_all(
        [
            Repository(
                repository_id=11,
                project_id=project.project_id,
                repository_name="Repo One",
                repository_slug="repo-one",
                repository_url="https://example.com/PROJ/repo-one",
            ),
            Repository(
                repository_id=12,
                project_id=project.project_id,
                repository_name="Repo Two",
                repository_slug="repo-two",
                repository_url="https://example.com/PROJ/repo-two",
            ),
            ProjectRegistry(
                app_name="App", project_key="PROJ", repository_slug="repo-one"
            ),
            ProjectRegistry(
                app_name="App", project_key="PROJ", repository_slug="repo-two"
            ),
        ]
    )
    await db.commit()
    return {
        "git_user": git_user,
        "linked": linked,
        "unlinked": unlinked,
        "project": project,
    }


@pytest.mark.asyncio
async def test_unbound_system_user_sees_no_repository(db: AsyncSession, access_data: dict):
    service = RepositoryAccessService(db)
    assert await service.allowed_pairs(access_data["unlinked"].id) == set()


@pytest.mark.asyncio
async def test_replace_access_is_idempotent_and_rejects_unknown_repositories(
    db: AsyncSession, access_data: dict
):
    service = RepositoryAccessService(db)
    subject_id = access_data["linked"].id

    first = await service.replace_access(
        "auth_user", subject_id, {("PROJ", "repo-one")}, granted_by=1
    )
    assert len(first) == 1

    second = await service.replace_access(
        "auth_user", subject_id, {("PROJ", "repo-one")}, granted_by=1
    )
    assert len(second) == 1

    with pytest.raises(ValidationException):
        await service.replace_access("auth_user", subject_id, {("PROJ", "missing")}, 1)


@pytest.mark.asyncio
async def test_replace_access_syncs_the_linked_subject(db: AsyncSession, access_data: dict):
    """Saving either side of a linked pair rewrites the other side too."""
    service = RepositoryAccessService(db)

    await service.replace_access(
        "git_user", access_data["git_user"].id, {("PROJ", "repo-one")}, 1
    )
    assert await service.allowed_pairs(access_data["linked"].id) == {("PROJ", "repo-one")}

    # stale grants on the git user must not survive a system-user save
    await service.replace_access(
        "auth_user", access_data["linked"].id, {("PROJ", "repo-two")}, 1
    )
    assert await service.allowed_pairs(access_data["linked"].id) == {("PROJ", "repo-two")}
    git_rows = await service.list_access("git_user", access_data["git_user"].id)
    assert {(r["project_key"], r["repository_slug"]) for r in git_rows} == {
        ("PROJ", "repo-two")
    }

    # a system user without a linked git user is untouched by other subjects
    await service.replace_access(
        "auth_user", access_data["unlinked"].id, {("PROJ", "repo-one")}, 1
    )
    assert await service.allowed_pairs(access_data["linked"].id) == {("PROJ", "repo-two")}


@pytest.mark.asyncio
async def test_assign_reviewer_auto_grants_the_repository(db: AsyncSession, access_data: dict):
    """Assigning a task grants the reviewer's linked subjects the repository."""
    from src.models.pull_request import PullRequestReviewBase
    from src.schemas.review import AssignReviewerRequest
    from src.services.multi_reviewer_service import MultiReviewerService

    review = PullRequestReviewBase(
        pull_request_id="PR-1",
        project_key="PROJ",
        repository_slug="repo-one",
        source_branch="feature",
        target_branch="main",
        pull_request_status="OPEN",
        pull_request_user="alice",
    )
    db.add(review)
    await db.commit()

    service = MultiReviewerService()
    result = await service.assign_reviewer(
        db=db,
        review_base_id=review.id,
        assignment_data=AssignReviewerRequest(reviewer="alice"),
        assigned_by="admin",
        granted_by_id=999,
    )
    assert result["message"] == "Reviewer assigned successfully"

    access = RepositoryAccessService(db)
    assert ("PROJ", "repo-one") in await access.allowed_pairs(access_data["linked"].id)
    git_rows = await access.list_access("git_user", access_data["git_user"].id)
    assert {(r["project_key"], r["repository_slug"]) for r in git_rows} == {
        ("PROJ", "repo-one")
    }
    assert git_rows[0]["granted_by"] == 999

    # a repeat assign is a no-op on the assignment but keeps the grant in place
    await service.assign_reviewer(
        db=db,
        review_base_id=review.id,
        assignment_data=AssignReviewerRequest(reviewer="alice"),
    )
    assert ("PROJ", "repo-one") in await access.allowed_pairs(access_data["linked"].id)


@pytest.mark.asyncio
async def test_author_auto_bind_is_idempotent_and_links_system_user(
    db: AsyncSession, access_data: dict
):
    service = RepositoryAccessService(db)

    await service.ensure_author_grants("PROJ", "repo-two", "alice")
    await db.commit()
    await service.ensure_author_grants("PROJ", "repo-two", "alice")
    await db.commit()

    git_rows = await service.list_access("git_user", access_data["git_user"].id)
    assert len(git_rows) == 1
    assert (git_rows[0]["project_key"], git_rows[0]["repository_slug"]) == (
        "PROJ",
        "repo-two",
    )

    linked_rows = await service.list_access("auth_user", access_data["linked"].id)
    assert len(linked_rows) == 1


@pytest.mark.asyncio
async def test_auto_bind_ignores_unknown_author(db: AsyncSession, access_data: dict):
    service = RepositoryAccessService(db)
    await service.ensure_author_grants("PROJ", "repo-two", "nobody")
    await db.commit()
    assert await service.allowed_pairs(access_data["linked"].id) == set()


@pytest.mark.asyncio
async def test_subject_validation(db: AsyncSession, access_data: dict):
    service = RepositoryAccessService(db)
    with pytest.raises(NotFoundException):
        await service.replace_access("auth_user", 99999, set(), 1)
    with pytest.raises(ValidationException):
        await service.replace_access("other", 1, set(), 1)


@pytest.mark.asyncio
async def test_catalog_lists_every_registered_pair(db: AsyncSession, access_data: dict):
    service = RepositoryAccessService(db)
    catalog = await service.list_catalog()
    pairs = {(item["project_key"], item["repository_slug"]) for item in catalog}
    assert {("PROJ", "repo-one"), ("PROJ", "repo-two")} <= pairs


@pytest.fixture
def access_client(async_client: AsyncClient, db_session: AsyncSession):
    class OpenRBACService(RBACService):
        async def require_permission(self, *args, **kwargs) -> None:
            return None

    async def _service() -> RBACService:
        return OpenRBACService(db_session)

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="admin", email="admin@example.com")

    async def _db_session():
        yield db_session

    app.dependency_overrides[access_endpoint.get_rbac_service] = _service
    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_db_session] = _db_session
    yield async_client
    for dependency in (
        access_endpoint.get_rbac_service,
        get_current_user_with_token,
        get_db_session,
    ):
        app.dependency_overrides.pop(dependency, None)


@pytest.mark.asyncio
async def test_catalog_endpoint(access_client: AsyncClient, access_data: dict):
    response = await access_client.get("/api/v1/repository-access/catalog")
    assert response.status_code == 200
    pairs = {(item["project_key"], item["repository_slug"]) for item in response.json()}
    assert ("PROJ", "repo-one") in pairs


@pytest.mark.asyncio
async def test_replace_endpoint(access_client: AsyncClient, access_data: dict):
    subject_id = access_data["linked"].id
    response = await access_client.put(
        f"/api/v1/repository-access/auth_user/{subject_id}",
        json={"items": [{"project_key": "PROJ", "repository_slug": "repo-one"}]},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = await access_client.get(f"/api/v1/repository-access/auth_user/{subject_id}")
    assert response.status_code == 200
    assert response.json()["items"][0]["repository_slug"] == "repo-one"


@pytest.mark.asyncio
async def test_replace_endpoint_rejects_unknown_subject(
    access_client: AsyncClient, access_data: dict
):
    response = await access_client.put(
        "/api/v1/repository-access/auth_user/99999", json={"items": []}
    )
    assert response.status_code == 404
