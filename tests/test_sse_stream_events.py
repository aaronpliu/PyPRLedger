"""Tests for the stream events scores and assignments publish.

A score landing or an assignment changing is the same news to a watching page
as a review changing - its reading went stale - so both ride the review stream
under their own event name. The tests check the helper that names the frame and
the two write paths that announce themselves.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.models.project import Project
from src.models.pull_request import PullRequestReviewAssignment, PullRequestReviewBase
from src.models.repository import Repository
from src.models.user import User
from src.schemas.pull_request import ReviewScoreCreate
from src.services.multi_reviewer_service import MultiReviewerService
from src.services.review_score_service import ReviewScoreService
from src.services.sse_broker import REVIEW_CREATED_CHANNEL, publish_stream_event
from src.utils.timezone import get_current_time


class RecordingRedis:
    """A Redis that remembers what was published."""

    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, channel: str, message: str) -> int:
        self.published.append((channel, json.loads(message)))
        return 1


class EventRecorder:
    """Stands in for the stream publisher at a service's seam."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def __call__(self, event: str, payload: dict[str, Any]) -> bool:
        self.events.append((event, payload))
        return True


async def seed_scope(db_session, *, project_key: str = "CORE", repository_slug: str = "app"):
    """The project and repository rows that keep entity sync off the network."""
    project = Project(
        project_id=1001,
        project_name="Core",
        project_key=project_key,
        project_url="https://example.com/projects/core",
    )
    db_session.add(project)
    await db_session.flush()
    repository = Repository(
        repository_id=2001,
        project_id=project.project_id,
        repository_name="App",
        repository_slug=repository_slug,
        repository_url="https://example.com/repos/app",
    )
    db_session.add(repository)
    await db_session.flush()
    user = User(
        user_id=3001,
        username="alice",
        display_name="Alice",
        email_address="alice@example.com",
        is_reviewer=True,
        active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return project, repository


@pytest.mark.asyncio
async def test_the_helper_names_the_frame_and_rides_the_review_channel(monkeypatch):
    redis = RecordingRedis()
    monkeypatch.setattr("src.services.sse_broker.get_redis_client", lambda: redis)

    sent = await publish_stream_event(
        "score_updated",
        payload={
            "review_id": 5,
            "project_key": "CORE",
            "repository_slug": "app",
            "pull_request_id": "42",
            "created_date": get_current_time(),  # a raw ORM datetime is fine
        },
    )

    assert sent is True
    channel, frame = redis.published[0]
    assert channel == REVIEW_CREATED_CHANNEL
    assert frame["event"] == "score_updated"
    assert frame["project_key"] == "CORE"
    assert frame["repository_slug"] == "app"
    assert frame["pull_request_id"] == "42"
    assert isinstance(frame["created_date"], str)  # serialised for the wire


@pytest.mark.asyncio
async def test_the_helper_reports_a_failure_instead_of_raising(monkeypatch):
    class BrokenRedis:
        async def publish(self, channel: str, message: str) -> int:
            raise RuntimeError("redis down")

    monkeypatch.setattr("src.services.sse_broker.get_redis_client", lambda: BrokenRedis())

    assert await publish_stream_event("score_updated", payload={}) is False


@pytest.mark.asyncio
async def test_submitting_a_score_announces_the_score(db_session, monkeypatch):
    recorder = EventRecorder()
    monkeypatch.setattr(
        "src.services.review_score_service.publish_stream_event", recorder
    )

    await seed_scope(db_session)
    base = PullRequestReviewBase(
        pull_request_id="42",
        pull_request_commit_id="c1",
        project_key="CORE",
        repository_slug="app",
        source_branch="feature",
        target_branch="main",
        pull_request_status="open",
    )
    db_session.add(base)
    await db_session.flush()

    await ReviewScoreService().upsert_score(
        ReviewScoreCreate(
            pull_request_id="42",
            pull_request_commit_id="c1",
            project_key="CORE",
            repository_slug="app",
            reviewer="alice",
            score=8.0,
        ),
        db_session,
        review_base_id=base.id,
    )

    assert [event for event, _ in recorder.events] == ["score_updated"]
    event, payload = recorder.events[0]
    assert (payload["project_key"], payload["repository_slug"]) == ("CORE", "app")
    assert payload["pull_request_id"] == "42"


@pytest.mark.asyncio
async def test_a_score_that_completes_an_assignment_announces_both(db_session, monkeypatch):
    recorder = EventRecorder()
    monkeypatch.setattr(
        "src.services.review_score_service.publish_stream_event", recorder
    )

    await seed_scope(db_session)
    base = PullRequestReviewBase(
        pull_request_id="42",
        pull_request_commit_id="c1",
        project_key="CORE",
        repository_slug="app",
        source_branch="feature",
        target_branch="main",
        pull_request_status="open",
    )
    db_session.add(base)
    await db_session.flush()
    db_session.add(
        PullRequestReviewAssignment(
            review_base_id=base.id,
            reviewer="alice",
            assignment_status="in_progress",
            assignment_source="manual",
        )
    )
    await db_session.flush()

    await ReviewScoreService().upsert_score(
        ReviewScoreCreate(
            pull_request_id="42",
            pull_request_commit_id="c1",
            project_key="CORE",
            repository_slug="app",
            reviewer="alice",
            score=8.0,
        ),
        db_session,
        review_base_id=base.id,
    )

    # the score lands, and the assignment it answers moves to completed
    assert [event for event, _ in recorder.events] == [
        "score_updated",
        "assignment_updated",
    ]


@pytest.mark.asyncio
async def test_moving_an_assignment_status_announces_the_assignment(db_session, monkeypatch):
    recorder = EventRecorder()
    monkeypatch.setattr(
        "src.services.multi_reviewer_service.publish_stream_event", recorder
    )

    base = PullRequestReviewBase(
        pull_request_id="42",
        pull_request_commit_id="c1",
        project_key="CORE",
        repository_slug="app",
        source_branch="feature",
        target_branch="main",
        pull_request_status="open",
    )
    db_session.add(base)
    await db_session.flush()
    assignment = PullRequestReviewAssignment(
        review_base_id=base.id,
        reviewer="alice",
        assignment_status="assigned",
        assignment_source="manual",
    )
    db_session.add(assignment)
    await db_session.flush()

    await MultiReviewerService().update_assignment_status(
        db_session, assignment.id, "in_progress"
    )

    assert [event for event, _ in recorder.events] == ["assignment_updated"]
    _, payload = recorder.events[0]
    assert payload["review_id"] == base.id
    assert (payload["project_key"], payload["repository_slug"]) == ("CORE", "app")


@pytest.mark.asyncio
async def test_an_assignment_for_a_missing_review_is_not_announced(db_session, monkeypatch):
    """A dangling assignment has no repository pair to name - say nothing."""
    recorder = EventRecorder()
    monkeypatch.setattr(
        "src.services.multi_reviewer_service.publish_stream_event", recorder
    )

    assignment = PullRequestReviewAssignment(
        review_base_id=99999,  # no base row behind it
        reviewer="alice",
        assignment_status="assigned",
        assignment_source="manual",
    )
    db_session.add(assignment)
    await db_session.flush()

    await MultiReviewerService().update_assignment_status(
        db_session, assignment.id, "in_progress"
    )

    assert recorder.events == []
