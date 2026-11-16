"""Tests for the repository insights reading.

The reading is one answer to a dashboard page, so the tests check the four things
a page asks of it: the numbers, who the scope covers, what the caller is allowed
to see, and that a poll does not repeat the queries.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from src.models.pull_request import (
    PullRequestReviewAssignment,
    PullRequestReviewBase,
    PullRequestScore,
)
from src.services.insights_service import InsightsService
from src.utils.timezone import get_current_time


PROJECT = "CORE"
REPOSITORY = "app"
OTHER_PROJECT = "PAY"
OTHER_REPOSITORY = "billing"
PAIRS = {(PROJECT, REPOSITORY)}


def review_base(
    pr_id: str,
    commit: str,
    *,
    project_key: str = PROJECT,
    repository_slug: str = REPOSITORY,
    status: str = "open",
    days_ago: int = 1,
) -> PullRequestReviewBase:
    """One review of a PR commit, the row the counts are read from."""
    created = get_current_time() - timedelta(days=days_ago)
    return PullRequestReviewBase(
        pull_request_id=pr_id,
        pull_request_commit_id=commit,
        project_key=project_key,
        repository_slug=repository_slug,
        source_branch="feature",
        target_branch="main",
        pull_request_status=status,
        created_date=created,
        updated_date=created,
    )


def score(
    pr_id: str,
    commit: str,
    value: float,
    *,
    project_key: str = PROJECT,
    repository_slug: str = REPOSITORY,
    days_ago: int = 1,
    active: bool = True,
) -> PullRequestScore:
    created = get_current_time() - timedelta(days=days_ago)
    return PullRequestScore(
        pull_request_id=pr_id,
        pull_request_commit_id=commit,
        project_key=project_key,
        repository_slug=repository_slug,
        reviewer="alice",
        score=value,
        active=active,
        created_date=created,
        updated_date=created,
    )


def assignment(
    base: PullRequestReviewBase,
    reviewer: str,
    *,
    status: str = "assigned",
    days_ago: int = 1,
) -> PullRequestReviewAssignment:
    created = get_current_time() - timedelta(days=days_ago)
    return PullRequestReviewAssignment(
        review_base_id=base.id,
        reviewer=reviewer,
        assignment_status=status,
        assignment_source="manual",
        created_date=created,
        updated_date=created,
    )


class CountingService(InsightsService):
    """The same reading, counting how often it went to the database."""

    reads = 0

    async def _read(self, *args, **kwargs):
        CountingService.reads += 1
        return await super()._read(*args, **kwargs)


@pytest.mark.asyncio
async def test_reads_only_the_repository_it_was_asked_for(db_session):
    db_session.add_all(
        [
            review_base("1", "c1"),
            review_base("2", "c2", status="merged"),
            review_base("3", "c3", project_key=OTHER_PROJECT, repository_slug=OTHER_REPOSITORY),
        ]
    )
    await db_session.flush()

    reading = await InsightsService(allowed_pairs=PAIRS).get_repository_insights(
        db_session, project_key=PROJECT, repository_slug=REPOSITORY
    )

    assert reading.kpis.reviews_total == 2
    assert reading.kpis.reviews_open == 1
    # a single repository reading does not break the numbers down per project
    assert reading.breakdown.by_status[0].key == "merged"
    assert reading.breakdown.by_project == []


@pytest.mark.asyncio
async def test_a_project_reading_merges_its_repositories_and_names_them(db_session):
    db_session.add_all(
        [
            review_base("1", "c1"),
            review_base("2", "c2", repository_slug="api"),
            review_base("3", "c3", project_key=OTHER_PROJECT, repository_slug=OTHER_REPOSITORY),
        ]
    )
    await db_session.flush()

    reading = await InsightsService(allowed_pairs=None).get_repository_insights(
        db_session, project_key=PROJECT
    )

    assert reading.kpis.reviews_total == 2
    assert [(item.key, item.count) for item in reading.breakdown.by_project] == [(PROJECT, 2)]


@pytest.mark.asyncio
async def test_reads_the_score_and_the_high_suggestion_rate(db_session):
    db_session.add(score("1", "c1", 9.0))
    db_session.add(score("2", "c2", 5.0))
    db_session.add(score("3", "c3", 1.0, active=False))  # a soft-deleted score is not read
    await db_session.flush()

    reading = await InsightsService(allowed_pairs=PAIRS).get_repository_insights(
        db_session, project_key=PROJECT, repository_slug=REPOSITORY
    )

    assert reading.kpis.avg_score == 7.0
    assert reading.kpis.good_suggestion_rate == 0.5


@pytest.mark.asyncio
async def test_says_what_is_assigned_and_what_nobody_holds(db_session):
    first = review_base("1", "c1")
    second = review_base("2", "c2")
    db_session.add_all([first, second])
    await db_session.flush()
    db_session.add(assignment(first, "alice", status="completed"))
    await db_session.flush()

    reading = await InsightsService(allowed_pairs=PAIRS).get_repository_insights(
        db_session, project_key=PROJECT, repository_slug=REPOSITORY
    )

    assert reading.kpis.unassigned_count == 1
    assert reading.kpis.assigned_pending == 0
    assert reading.kpis.active_reviewers == 1
    assert reading.breakdown.by_reviewer[0].reviewer == "alice"
    assert reading.breakdown.by_reviewer[0].completed == 1


@pytest.mark.asyncio
async def test_a_grant_set_limits_what_the_reading_covers(db_session):
    db_session.add_all(
        [
            review_base("1", "c1"),
            review_base("2", "c2", project_key=OTHER_PROJECT, repository_slug=OTHER_REPOSITORY),
        ]
    )
    await db_session.flush()

    # the caller holds a grant for CORE/app only, so a PAY reading is empty
    reading = await InsightsService(allowed_pairs=PAIRS).get_repository_insights(
        db_session, project_key=OTHER_PROJECT
    )

    assert reading.kpis.reviews_total == 0
    assert reading.recent == []


@pytest.mark.asyncio
async def test_an_empty_grant_set_answers_with_an_empty_reading(db_session):
    db_session.add(review_base("1", "c1"))
    await db_session.flush()

    reading = await InsightsService(allowed_pairs=set()).get_repository_insights(
        db_session, project_key=PROJECT
    )

    assert reading.kpis.reviews_total == 0
    assert reading.trends == []


@pytest.mark.asyncio
async def test_a_poll_does_not_repeat_the_queries(db_session):
    CountingService.reads = 0
    db_session.add(review_base("1", "c1"))
    await db_session.flush()

    service = CountingService(allowed_pairs=PAIRS)
    first = await service.get_repository_insights(
        db_session, project_key=PROJECT, repository_slug=REPOSITORY
    )
    second = await service.get_repository_insights(
        db_session, project_key=PROJECT, repository_slug=REPOSITORY
    )

    assert CountingService.reads == 1
    assert second.kpis.reviews_total == first.kpis.reviews_total


@pytest.mark.asyncio
async def test_reads_the_recent_reviews_newest_first(db_session):
    db_session.add_all(
        [
            review_base("1", "c1", days_ago=3),
            review_base("2", "c2", days_ago=1),
        ]
    )
    await db_session.flush()

    reading = await InsightsService(allowed_pairs=PAIRS).get_repository_insights(
        db_session, project_key=PROJECT, repository_slug=REPOSITORY
    )

    assert [item.pull_request_id for item in reading.recent] == ["2", "1"]


@pytest.mark.asyncio
async def test_trends_carry_reviews_and_scores_in_the_same_bucket(db_session):
    db_session.add_all([review_base("1", "c1"), score("1", "c1", 8.0)])
    await db_session.flush()

    reading = await InsightsService(allowed_pairs=PAIRS).get_repository_insights(
        db_session, project_key=PROJECT, repository_slug=REPOSITORY, period="daily"
    )

    assert reading.trends
    point = reading.trends[-1]
    assert point.reviews == 1
    assert point.avg_score == 8.0
    assert point.high_scores == 1
