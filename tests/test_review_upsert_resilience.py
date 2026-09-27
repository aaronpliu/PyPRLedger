"""Regression tests for POST /api/v1/reviews when the entity sync hits the database.

Two things used to go wrong on a payload whose project was already stored under a
different business key:

* the same remote project (Bitbucket workspace / Server project / GitHub org) was
  inserted again and failed on the unique ``project.project_id``;
* the failed flush left the transaction unusable, so recording the failure raised
  ``PendingRollbackError`` ("This Session's transaction has been rolled back ...")
  and hid the real cause (duplicate entry).

No HTTP and no git traffic: the provider is stubbed and the database is the
in-memory SQLite fixture.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import src.services.entity_sync_service as entity_sync_module
from src.models.project import Project
from src.models.pull_request import PullRequestReviewBase, PullRequestReviewRaw
from src.schemas.pull_request import ReviewCreate
from src.services.entity_sync_service import EntitySyncService
from src.services.review_service import ReviewService


WORKSPACE = "aaronpliu"
PROJECT_ID = 30379242


class StubProvider:
    """Bits of a Bitbucket Cloud provider: one workspace, one repository, one user."""

    name = "bitbucket_cloud"

    def __init__(self) -> None:
        self.workspace_lookups: list[str] = []

    async def get_project_info(self, workspace: str) -> dict[str, Any]:
        self.workspace_lookups.append(workspace)
        return {
            "project_id": PROJECT_ID,
            "project_name": workspace,
            "project_key": workspace,
            "project_url": f"https://bitbucket.org/{WORKSPACE}/",
        }

    async def get_repository_info(self, workspace: str, repo_slug: str) -> dict[str, Any]:
        return {
            "repository_id": 4242,
            "repository_name": repo_slug,
            "repository_slug": repo_slug,
            "repository_url": f"https://bitbucket.org/{workspace}/{repo_slug}",
        }

    async def get_user_info(self, username: str) -> dict[str, Any]:
        return {
            "user_id": 99,
            "username": username,
            "display_name": username,
            "email_address": f"{username}@example.com",
        }


@pytest.fixture
def provider(monkeypatch) -> StubProvider:
    stub = StubProvider()
    monkeypatch.setattr(entity_sync_module, "get_git_provider", lambda *_: stub)
    return stub


def review_payload(**overrides: Any) -> ReviewCreate:
    data: dict[str, Any] = {
        "pull_request_id": "42",
        "project_key": "AI",
        "repository_slug": "pylang",
        "pull_request_user": "alice",
        "source_branch": "feature/pylang",
        "target_branch": "main",
        "git_provider": "bitbucket_cloud",
        "workspace_slug": WORKSPACE,
    }
    data.update(overrides)
    return ReviewCreate(**data)


async def test_review_accepts_a_workspace_addressed_under_a_new_business_key(
    db_session: AsyncSession, provider: StubProvider
) -> None:
    """The duplicate key error must not happen again for the same remote project."""
    service = ReviewService()

    _, created = await service.upsert_review(review_payload(), db_session)
    assert created is True

    # the very same workspace, addressed with a new business key and a new PR
    response, created_again = await service.upsert_review(
        review_payload(project_key="web-development", pull_request_id="43"), db_session
    )

    assert created_again is True
    # the caller's business key is kept on the review (and echoed back)
    assert response.project_key == "web-development"

    projects = (await db_session.execute(select(Project))).scalars().all()
    assert [project.project_key for project in projects] == ["AI"]

    # both payloads were processed successfully - nothing left to replay
    raw = (await db_session.execute(select(PullRequestReviewRaw))).scalars().all()
    assert raw == []


async def test_retrying_an_aliased_payload_updates_its_own_review(
    db_session: AsyncSession, provider: StubProvider
) -> None:
    """A retry must update the row written for those business keys.

    Looking the review up by the stored project key (the alias) would either
    rewrite the review of the other key or add a duplicate.
    """
    service = ReviewService()

    # the workspace is stored under another business key first
    await service.upsert_review(review_payload(project_key="AI"), db_session)

    _, created = await service.upsert_review(
        review_payload(project_key="web-development"), db_session
    )
    assert created is True

    _, created_again = await service.upsert_review(
        review_payload(project_key="web-development"), db_session
    )
    assert created_again is False

    bases = (await db_session.execute(select(PullRequestReviewBase))).scalars().all()
    assert sorted(base.project_key for base in bases) == ["AI", "web-development"]


async def test_a_failed_flush_keeps_the_cause_and_is_recorded(
    db_session: AsyncSession, provider: StubProvider, monkeypatch
) -> None:
    """A broken flush must surface the original error, not a PendingRollbackError."""
    service = ReviewService()
    await service.upsert_review(review_payload(), db_session)

    async def conflicting_sync(self: EntitySyncService, project_key: str) -> None:
        # a second row for an already stored project_id: the flush fails for real
        self.db.add(
            Project(
                project_id=PROJECT_ID,
                project_name="duplicate",
                project_key="OTHER",
                project_url="https://bitbucket.org/other/",
                git_provider="bitbucket_cloud",
            )
        )
        await self.db.flush()
        return None

    monkeypatch.setattr(EntitySyncService, "sync_project", conflicting_sync)

    with pytest.raises(IntegrityError) as excinfo:
        await service.upsert_review(review_payload(pull_request_id="99"), db_session)

    assert "project.project_id" in str(excinfo.value)

    # the failure is recorded in a fresh transaction and the session stays usable
    failed = [
        record
        for record in (await db_session.execute(select(PullRequestReviewRaw))).scalars().all()
        if record.status == "failed"
    ]
    assert len(failed) == 1
    assert failed[0].request_payload["pull_request_id"] == "99"
    assert "project.project_id" in (failed[0].error_message or "")
    assert failed[0].processed_date is not None
    assert failed[0].error_details is not None
    assert failed[0].error_details["error_type"] == "IntegrityError"
