"""Tests for the repository insights endpoint."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token, get_repository_access
from src.main import app
from src.models.auth_user import AuthUser
from src.models.pull_request import PullRequestReviewAssignment, PullRequestReviewBase
from src.utils.timezone import get_current_time


PROJECT = "CORE"
REPOSITORY = "app"


@pytest.fixture
def insights_client(db_session):
    """A client whose caller holds one grant, so the scope rules can be read."""

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    async def _db_session() -> Any:
        yield db_session

    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_db_session] = _db_session
    app.dependency_overrides[get_repository_access] = lambda: {(PROJECT, REPOSITORY)}
    yield
    for dependency in (
        get_current_user_with_token,
        get_db_session,
        get_repository_access,
    ):
        app.dependency_overrides.pop(dependency, None)


def review_base(pr_id: str, commit: str, status: str = "open") -> PullRequestReviewBase:
    created = get_current_time() - timedelta(days=1)
    return PullRequestReviewBase(
        pull_request_id=pr_id,
        pull_request_commit_id=commit,
        project_key=PROJECT,
        repository_slug=REPOSITORY,
        source_branch="feature",
        target_branch="main",
        pull_request_status=status,
        created_date=created,
        updated_date=created,
    )


@pytest.mark.asyncio
async def test_answers_one_reading_for_the_page(async_client, insights_client, db_session):
    first = review_base("1", "c1")
    db_session.add_all([first, review_base("2", "c2", status="merged")])
    await db_session.flush()
    db_session.add(
        PullRequestReviewAssignment(
            review_base_id=first.id,
            reviewer="alice",
            assignment_status="in_progress",
            assignment_source="manual",
            created_date=get_current_time() - timedelta(days=1),
            updated_date=get_current_time() - timedelta(days=1),
        )
    )
    await db_session.flush()

    response = await async_client.get(
        "/api/v1/insights/repository",
        params={"project_key": PROJECT, "repository_slug": REPOSITORY, "days": 30},
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["scope"]["project_key"] == PROJECT
    assert body["scope"]["repository_slug"] == REPOSITORY
    assert body["scope"]["period"] == "weekly"
    assert body["kpis"]["reviews_total"] == 2
    assert body["kpis"]["reviews_open"] == 1
    assert body["kpis"]["assigned_in_progress"] == 1
    assert body["kpis"]["unassigned_count"] == 1
    assert body["breakdown"]["by_status"]
    assert len(body["recent"]) == 2


@pytest.mark.asyncio
async def test_reads_nothing_outside_the_callers_grants(async_client, insights_client):
    response = await async_client.get(
        "/api/v1/insights/repository", params={"project_key": "PAY"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["kpis"]["reviews_total"] == 0


@pytest.mark.asyncio
async def test_rejects_a_trend_bucket_it_does_not_draw(async_client, insights_client):
    response = await async_client.get(
        "/api/v1/insights/repository", params={"project_key": PROJECT, "period": "yearly"}
    )

    assert response.status_code == 422
