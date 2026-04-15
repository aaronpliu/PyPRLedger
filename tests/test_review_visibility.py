from __future__ import annotations

from uuid import uuid4

import anyio
import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.v1.endpoints.reviews import upsert_score as upsert_score_endpoint
from src.core.database import Base
from src.models.auth_user import AuthUser
from src.models.project import Project
from src.models.pull_request import PullRequestReviewAssignment, PullRequestReviewBase
from src.models.rbac import UserRoleAssignment
from src.models.repository import Repository
from src.models.role import Role
from src.models.user import User
from src.schemas.pull_request import ReviewFilter, ReviewScoreCreate
from src.services.multi_reviewer_service import MultiReviewerService
from src.services.review_score_service import ReviewScoreService
from src.services.review_service import ReviewService
from src.utils.password import hash_password


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


async def _run_with_test_session(test_func) -> None:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await test_func(session)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


async def _create_project_repository(db: AsyncSession, suffix: str) -> tuple[Project, Repository]:
    project = Project(
        project_id=1000 + len(suffix),
        project_name=f"Project {suffix}",
        project_key=f"PRJ{suffix[:6]}",
        project_url=f"https://example.com/projects/{suffix}",
    )
    db.add(project)
    await db.flush()

    repository = Repository(
        repository_id=2000 + len(suffix),
        project_id=project.project_id,
        repository_name=f"Repo {suffix}",
        repository_slug=f"repo-{suffix}",
        repository_url=f"https://example.com/repos/{suffix}",
    )
    db.add(repository)
    await db.flush()
    return project, repository


async def _create_bitbucket_user(
    db: AsyncSession,
    *,
    suffix: str,
    username: str,
    is_reviewer: bool,
) -> User:
    user = User(
        user_id=100000 + abs(hash((suffix, username))) % 100000,
        username=username,
        display_name=username.replace("-", " ").title(),
        email_address=f"{username}@example.com",
        is_reviewer=is_reviewer,
        active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _create_auth_user(
    db: AsyncSession,
    *,
    username: str,
    linked_user: User | None,
) -> AuthUser:
    auth_user = AuthUser(
        username=username,
        email=f"{username}@example.com",
        password_hash=hash_password("password123"),
        user_id=linked_user.id if linked_user else None,
    )
    db.add(auth_user)
    await db.flush()
    return auth_user


async def _create_reviewer_role(db: AsyncSession) -> Role:
    role = Role(
        name=f"reviewer-{uuid4().hex[:8]}",
        description="Test reviewer role",
        permissions={
            "reviews": ["read"],
            "scores": ["read", "create", "update"],
        },
    )
    db.add(role)
    await db.flush()
    return role


async def _assign_role(db: AsyncSession, auth_user: AuthUser, role: Role) -> None:
    assignment = UserRoleAssignment(
        auth_user_id=auth_user.id,
        role_id=role.id,
        resource_type="global",
        resource_id=None,
    )
    db.add(assignment)
    await db.flush()


async def _create_review_base(
    db: AsyncSession,
    *,
    project: Project,
    repository: Repository,
    pull_request_id: str,
    commit_id: str,
    owner_username: str,
    source_filename: str | None = None,
) -> PullRequestReviewBase:
    review_base = PullRequestReviewBase(
        pull_request_id=pull_request_id,
        pull_request_commit_id=commit_id,
        project_key=project.project_key,
        repository_slug=repository.repository_slug,
        source_filename=source_filename,
        source_branch="feature/test",
        target_branch="main",
        git_code_diff="diff --git a/file.py b/file.py",
        ai_suggestions=None,
        pull_request_status="open",
        pull_request_user=owner_username,
    )
    db.add(review_base)
    await db.flush()
    return review_base


async def _assign_review(
    db: AsyncSession,
    *,
    review_base: PullRequestReviewBase,
    reviewer_username: str,
) -> PullRequestReviewAssignment:
    assignment = PullRequestReviewAssignment(
        review_base_id=review_base.id,
        reviewer=reviewer_username,
        assignment_status="assigned",
    )
    db.add(assignment)
    await db.flush()
    return assignment


async def _test_review_service_lists_assigned_and_self_raised_reviews(
    db_session: AsyncSession,
) -> None:
    suffix = uuid4().hex[:8]
    project, repository = await _create_project_repository(db_session, suffix)

    alice = await _create_bitbucket_user(
        db_session, suffix=suffix, username=f"alice-{suffix}", is_reviewer=True
    )
    bob = await _create_bitbucket_user(
        db_session, suffix=suffix, username=f"bob-{suffix}", is_reviewer=True
    )
    carol = await _create_bitbucket_user(
        db_session, suffix=suffix, username=f"carol-{suffix}", is_reviewer=False
    )

    assigned_to_alice = await _create_review_base(
        db_session,
        project=project,
        repository=repository,
        pull_request_id=f"pr-assigned-{suffix}",
        commit_id=f"a{suffix}1",
        owner_username=carol.username,
        source_filename="src/assigned.py",
    )
    await _assign_review(
        db_session, review_base=assigned_to_alice, reviewer_username=alice.username
    )

    self_raised_other_reviewer = await _create_review_base(
        db_session,
        project=project,
        repository=repository,
        pull_request_id=f"pr-owned-{suffix}",
        commit_id=f"b{suffix}2",
        owner_username=alice.username,
        source_filename="src/owned.py",
    )
    await _assign_review(
        db_session,
        review_base=self_raised_other_reviewer,
        reviewer_username=bob.username,
    )

    self_raised_unassigned = await _create_review_base(
        db_session,
        project=project,
        repository=repository,
        pull_request_id=f"pr-unassigned-{suffix}",
        commit_id=f"c{suffix}3",
        owner_username=alice.username,
        source_filename="src/unassigned.py",
    )

    excluded = await _create_review_base(
        db_session,
        project=project,
        repository=repository,
        pull_request_id=f"pr-excluded-{suffix}",
        commit_id=f"d{suffix}4",
        owner_username=carol.username,
        source_filename="src/excluded.py",
    )
    await _assign_review(db_session, review_base=excluded, reviewer_username=bob.username)

    await db_session.commit()

    service = ReviewService()
    reviews, total = await service.list_reviews(
        ReviewFilter(visible_to_username=alice.username),
        db_session,
        page=1,
        page_size=20,
        use_cache=False,
    )

    assert total == 3
    assert {review["pull_request_id"] for review in reviews} == {
        assigned_to_alice.pull_request_id,
        self_raised_other_reviewer.pull_request_id,
        self_raised_unassigned.pull_request_id,
    }
    assert any(review["reviewer"] == alice.username for review in reviews)
    assert not any(review["reviewer"] == bob.username for review in reviews)
    assert sum(1 for review in reviews if review["reviewer"] is None) == 2


def test_review_service_lists_assigned_and_self_raised_reviews():
    anyio.run(_run_with_test_session, _test_review_service_lists_assigned_and_self_raised_reviews)


async def _test_review_service_hides_sibling_assignment_rows_for_reviewer(
    db_session: AsyncSession,
) -> None:
    suffix = uuid4().hex[:8]
    project, repository = await _create_project_repository(db_session, suffix)

    alice = await _create_bitbucket_user(
        db_session, suffix=suffix, username=f"alice-{suffix}", is_reviewer=True
    )
    bob = await _create_bitbucket_user(
        db_session, suffix=suffix, username=f"bob-{suffix}", is_reviewer=True
    )
    carol = await _create_bitbucket_user(
        db_session, suffix=suffix, username=f"carol-{suffix}", is_reviewer=False
    )

    shared_review = await _create_review_base(
        db_session,
        project=project,
        repository=repository,
        pull_request_id=f"pr-shared-{suffix}",
        commit_id=f"e{suffix}5",
        owner_username=carol.username,
        source_filename="src/shared.py",
    )
    await _assign_review(db_session, review_base=shared_review, reviewer_username=alice.username)
    await _assign_review(db_session, review_base=shared_review, reviewer_username=bob.username)
    await db_session.commit()

    service = ReviewService()
    reviews, total = await service.list_reviews(
        ReviewFilter(visible_to_username=alice.username),
        db_session,
        page=1,
        page_size=20,
        use_cache=False,
    )

    shared_reviews = [
        review for review in reviews if review["pull_request_id"] == shared_review.pull_request_id
    ]

    assert total == 1
    assert len(shared_reviews) == 1
    assert shared_reviews[0]["reviewer"] == alice.username


def test_review_service_hides_sibling_assignment_rows_for_reviewer():
    anyio.run(
        _run_with_test_session,
        _test_review_service_hides_sibling_assignment_rows_for_reviewer,
    )


async def _test_multi_reviewer_service_my_tasks_rule_uses_owner_or_assignment(
    db_session: AsyncSession,
) -> None:
    suffix = uuid4().hex[:8]
    project, repository = await _create_project_repository(db_session, suffix)

    alice = await _create_bitbucket_user(
        db_session, suffix=suffix, username=f"alice-{suffix}", is_reviewer=True
    )
    bob = await _create_bitbucket_user(
        db_session, suffix=suffix, username=f"bob-{suffix}", is_reviewer=True
    )

    assigned_to_alice = await _create_review_base(
        db_session,
        project=project,
        repository=repository,
        pull_request_id=f"task-assigned-{suffix}",
        commit_id=f"1{suffix}a",
        owner_username=bob.username,
    )
    await _assign_review(
        db_session, review_base=assigned_to_alice, reviewer_username=alice.username
    )

    self_raised = await _create_review_base(
        db_session,
        project=project,
        repository=repository,
        pull_request_id=f"task-owned-{suffix}",
        commit_id=f"2{suffix}b",
        owner_username=alice.username,
    )
    await _assign_review(db_session, review_base=self_raised, reviewer_username=bob.username)

    await db_session.commit()

    service = MultiReviewerService()
    reviews, total = await service.get_reviews(
        db=db_session,
        page=1,
        page_size=20,
        visible_to_username=alice.username,
    )

    assert total == 2
    assert {review.pull_request_id for review in reviews} == {
        assigned_to_alice.pull_request_id,
        self_raised.pull_request_id,
    }


def test_multi_reviewer_service_my_tasks_rule_uses_owner_or_assignment():
    anyio.run(
        _run_with_test_session,
        _test_multi_reviewer_service_my_tasks_rule_uses_owner_or_assignment,
    )


async def _test_score_submission_succeeds_for_assigned_self_raised_review(
    db_session: AsyncSession,
) -> None:
    suffix = uuid4().hex[:8]
    project, repository = await _create_project_repository(db_session, suffix)
    alice = await _create_bitbucket_user(
        db_session, suffix=suffix, username=f"alice-{suffix}", is_reviewer=True
    )
    auth_user = await _create_auth_user(
        db_session,
        username=f"login-{suffix}",
        linked_user=alice,
    )
    role = await _create_reviewer_role(db_session)
    await _assign_role(db_session, auth_user, role)

    review_base = await _create_review_base(
        db_session,
        project=project,
        repository=repository,
        pull_request_id=f"score-ok-{suffix}",
        commit_id=f"e{suffix}5",
        owner_username=alice.username,
        source_filename="src/score_ok.py",
    )
    await _assign_review(db_session, review_base=review_base, reviewer_username=alice.username)
    await db_session.commit()

    response = await upsert_score_endpoint(
        score_data=ReviewScoreCreate(
            pull_request_id=review_base.pull_request_id,
            pull_request_commit_id=review_base.pull_request_commit_id or "",
            project_key=project.project_key,
            repository_slug=repository.repository_slug,
            source_filename=review_base.source_filename,
            reviewer=alice.username,
            score=8.5,
            reviewer_comments="Assigned self-review allowed",
        ),
        db=db_session,
        score_service=ReviewScoreService(),
        current_user=auth_user,
    )

    assert response.reviewer == alice.username
    assert response.score == 8.5


def test_score_submission_succeeds_for_assigned_self_raised_review():
    anyio.run(
        _run_with_test_session,
        _test_score_submission_succeeds_for_assigned_self_raised_review,
    )


async def _test_score_submission_rejects_self_raised_review_without_assignment(
    db_session: AsyncSession,
) -> None:
    suffix = uuid4().hex[:8]
    project, repository = await _create_project_repository(db_session, suffix)
    alice = await _create_bitbucket_user(
        db_session, suffix=suffix, username=f"alice-{suffix}", is_reviewer=True
    )
    auth_user = await _create_auth_user(
        db_session,
        username=f"login-{suffix}",
        linked_user=alice,
    )
    role = await _create_reviewer_role(db_session)
    await _assign_role(db_session, auth_user, role)

    review_base = await _create_review_base(
        db_session,
        project=project,
        repository=repository,
        pull_request_id=f"score-blocked-{suffix}",
        commit_id=f"f{suffix}6",
        owner_username=alice.username,
        source_filename="src/score_blocked.py",
    )
    await db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await upsert_score_endpoint(
            score_data=ReviewScoreCreate(
                pull_request_id=review_base.pull_request_id,
                pull_request_commit_id=review_base.pull_request_commit_id or "",
                project_key=project.project_key,
                repository_slug=repository.repository_slug,
                source_filename=review_base.source_filename,
                reviewer=alice.username,
                score=5.0,
                reviewer_comments="Should be rejected",
            ),
            db=db_session,
            score_service=ReviewScoreService(),
            current_user=auth_user,
        )

    assert exc_info.value.status_code == 403
    assert (
        exc_info.value.detail["message"] == "You can only score reviews explicitly assigned to you."
    )


def test_score_submission_rejects_self_raised_review_without_assignment():
    anyio.run(
        _run_with_test_session,
        _test_score_submission_rejects_self_raised_review_without_assignment,
    )
