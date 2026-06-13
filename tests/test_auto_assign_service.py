"""Tests for the auto-assignment service and rule matching logic"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.database import Base
from src.models.auto_assign_rule import PullRequestReviewAutoAssignmentRule
from src.models.pull_request import (
    PullRequestReviewBase,
)
from src.models.user import User
from src.schemas.pull_request import ReviewCreate
from src.services.auto_assign_service import AutoTaskAssignmentService
from src.utils.timezone import get_current_time


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def auto_service() -> AutoTaskAssignmentService:
    return AutoTaskAssignmentService()


@pytest.fixture
def review_data() -> ReviewCreate:
    """Standard review data for testing conditions"""
    return ReviewCreate(
        pull_request_id="PR-42",
        project_key="PROJ-A",
        repository_slug="frontend-store",
        pull_request_user="alice",
        source_branch="feature/checkout",
        target_branch="main",
        pull_request_status="open",
    )


# ======================================================================
# 2.5 Unit tests for rule_matches()
# ======================================================================


class TestRuleMatches:
    """Tests for AutoTaskAssignmentService.rule_matches()"""

    def _make_rule(self, conditions: dict, **kwargs) -> PullRequestReviewAutoAssignmentRule:
        """Helper to create a rule object with given conditions"""
        return PullRequestReviewAutoAssignmentRule(
            name="test-rule",
            priority=100,
            conditions=conditions,
            assign_to=["reviewer1"],
            created_by="admin",
            created_at=get_current_time(),
            updated_at=get_current_time(),
            **kwargs,
        )

    def test_exact_project_key_match(self, auto_service, review_data):
        """Rule matches when project_key is in the list"""
        rule = self._make_rule({"project_key": ["PROJ-A", "PROJ-B"]})
        assert auto_service.rule_matches(rule, review_data) is True

    def test_exact_project_key_no_match(self, auto_service, review_data):
        """Rule does NOT match when project_key is not in the list"""
        rule = self._make_rule({"project_key": ["PROJ-C"]})
        assert auto_service.rule_matches(rule, review_data) is False

    def test_multiple_conditions_and(self, auto_service, review_data):
        """All conditions must match (AND logic)"""
        rule = self._make_rule(
            {
                "project_key": ["PROJ-A"],
                "repository_slug": ["frontend-store"],
            }
        )
        assert auto_service.rule_matches(rule, review_data) is True

    def test_multiple_conditions_no_match(self, auto_service, review_data):
        """Rule does NOT match when one AND condition fails"""
        rule = self._make_rule(
            {
                "project_key": ["PROJ-A"],
                "repository_slug": ["backend-api"],
            }
        )
        assert auto_service.rule_matches(rule, review_data) is False

    def test_source_branch_prefix_match(self, auto_service, review_data):
        """Rule matches when source_branch starts with the prefix"""
        rule = self._make_rule({"source_branch_prefix": "feature/"})
        assert auto_service.rule_matches(rule, review_data) is True

    def test_source_branch_prefix_no_match(self, auto_service, review_data):
        """Rule does NOT match when source_branch doesn't start with the prefix"""
        rule = self._make_rule({"source_branch_prefix": "hotfix/"})
        assert auto_service.rule_matches(rule, review_data) is False

    def test_pull_request_user_match(self, auto_service, review_data):
        """Rule matches when pull_request_user is in the list"""
        rule = self._make_rule({"pull_request_user": ["alice", "bob"]})
        assert auto_service.rule_matches(rule, review_data) is True

    def test_pull_request_user_no_match(self, auto_service, review_data):
        """Rule does NOT match when pull_request_user is not in the list"""
        rule = self._make_rule({"pull_request_user": ["charlie"]})
        assert auto_service.rule_matches(rule, review_data) is False

    def test_target_branch_match(self, auto_service, review_data):
        """Rule matches when target_branch is in the list"""
        rule = self._make_rule({"target_branch": ["main", "master"]})
        assert auto_service.rule_matches(rule, review_data) is True

    def test_target_branch_no_match(self, auto_service, review_data):
        """Rule does NOT match when target_branch is not in the list"""
        rule = self._make_rule({"target_branch": ["develop"]})
        assert auto_service.rule_matches(rule, review_data) is False

    def test_pull_request_status_match(self, auto_service, review_data):
        """Rule matches when pull_request_status is in the list"""
        rule = self._make_rule({"pull_request_status": ["open", "draft"]})
        assert auto_service.rule_matches(rule, review_data) is True

    def test_pull_request_status_no_match(self, auto_service, review_data):
        """Rule does NOT match when pull_request_status is not in the list"""
        rule = self._make_rule({"pull_request_status": ["merged"]})
        assert auto_service.rule_matches(rule, review_data) is False

    def test_empty_conditions_no_match(self, auto_service, review_data):
        """Empty conditions dict matches nothing (safe default)"""
        rule = self._make_rule({})
        assert auto_service.rule_matches(rule, review_data) is False

    def test_missing_condition_key_is_wildcard(self, auto_service, review_data):
        """Missing condition keys act as wildcards (no filter on that dimension)"""
        rule = self._make_rule({"project_key": ["PROJ-A"]})
        assert auto_service.rule_matches(rule, review_data) is True

    def test_extra_unmatched_field_no_effect(self, auto_service, review_data):
        """Extra condition keys that don't match cause the rule to fail"""
        # source_branch doesn't start with "main/" so this should fail
        rule = self._make_rule(
            {
                "project_key": ["PROJ-A"],
                "source_branch_prefix": "main/",
            }
        )
        assert auto_service.rule_matches(rule, review_data) is False

    def test_null_pull_request_user_handled(self, auto_service):
        """Rule handles null pull_request_user gracefully"""
        data = ReviewCreate(
            pull_request_id="PR-0",
            project_key="PROJ-A",
            repository_slug="repo",
            pull_request_user=None,
            source_branch="main",
            target_branch="main",
            pull_request_status="open",
        )
        rule = self._make_rule({"pull_request_user": ["alice"]})
        assert auto_service.rule_matches(rule, data) is False


# ======================================================================
# 6.3 Edge case: No matching rule
# ======================================================================


class TestAutoAssignIntegration:
    """Integration tests for the full auto-assignment flow"""

    @pytest.mark.asyncio
    async def test_no_matching_rule_leaves_unassigned(self, auto_service, review_data):
        """When no rule matches, the review should have no auto-assignments"""
        engine = create_async_engine(TEST_DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            # Create a review base first (simulating create_review flow)
            review_base = PullRequestReviewBase(
                pull_request_id="PR-42",
                project_key="PROJ-A",
                repository_slug="frontend-store",
                pull_request_user="alice",
                source_branch="feature/checkout",
                target_branch="main",
                pull_request_status="open",
            )
            session.add(review_base)
            await session.flush()

            # Run auto-assignment (no rules exist, so nothing should happen)
            assignments = await auto_service.auto_assign(
                db=session,
                review_base=review_base,
                review_data=review_data,
            )

            assert len(assignments) == 0, "No assignments should be created when no rules exist"

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_rule_matches_and_creates_assignments(self, auto_service, review_data):
        """A matching rule should create assignments with correct fields"""
        engine = create_async_engine(TEST_DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            # Create a reviewer user
            reviewer = User(
                user_id=9999,
                username="alice",
                display_name="Alice",
                email_address="alice@example.com",
                is_reviewer=True,
                active=True,
            )
            session.add(reviewer)
            await session.flush()

            # Create an active rule
            rule = PullRequestReviewAutoAssignmentRule(
                name="FE Team",
                priority=10,
                conditions={"project_key": ["PROJ-A"]},
                assign_to=["alice", "bob"],
                max_assignments=0,
                is_active=True,
                created_by="admin",
                created_at=get_current_time(),
                updated_at=get_current_time(),
            )
            session.add(rule)
            await session.flush()

            # Create a review base
            review_base = PullRequestReviewBase(
                pull_request_id="PR-42",
                project_key="PROJ-A",
                repository_slug="frontend-store",
                pull_request_user="alice",
                source_branch="feature/checkout",
                target_branch="main",
                pull_request_status="open",
            )
            session.add(review_base)
            await session.flush()

            # Run auto-assignment
            assignments = await auto_service.auto_assign(
                db=session,
                review_base=review_base,
                review_data=review_data,
            )

            assert len(assignments) == 1, "Only alice exists in User table, bob should be skipped"

            # Verify assignment fields
            assignment = assignments[0]
            assert assignment.reviewer == "alice"
            assert assignment.assigned_by is None  # NULL because FK references user(username)
            assert assignment.assignment_status == "pending"
            assert assignment.review_base_id == review_base.id

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_max_assignments_limits_reviewers(self, auto_service, review_data):
        """max_assignments should limit how many reviewers get assigned"""
        engine = create_async_engine(TEST_DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            # Create reviewer users
            for uname in ["reviewer1", "reviewer2", "reviewer3"]:
                user = User(
                    user_id=hash(uname) % 100000,
                    username=uname,
                    display_name=uname.replace("-", " ").title(),
                    email_address=f"{uname}@example.com",
                    is_reviewer=True,
                    active=True,
                )
                session.add(user)
            await session.flush()

            # Rule with max_assignments=2
            rule = PullRequestReviewAutoAssignmentRule(
                name="Limited",
                priority=10,
                conditions={"project_key": ["PROJ-A"]},
                assign_to=["reviewer1", "reviewer2", "reviewer3"],
                max_assignments=2,
                is_active=True,
                created_by="admin",
                created_at=get_current_time(),
                updated_at=get_current_time(),
            )
            session.add(rule)
            await session.flush()

            review_base = PullRequestReviewBase(
                pull_request_id="PR-42",
                project_key="PROJ-A",
                repository_slug="frontend-store",
                pull_request_user="alice",
                source_branch="feature/checkout",
                target_branch="main",
                pull_request_status="open",
            )
            session.add(review_base)
            await session.flush()

            assignments = await auto_service.auto_assign(
                db=session, review_base=review_base, review_data=review_data
            )

            assert len(assignments) == 2, "Only 2 reviewers should be assigned (max_assignments=2)"

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_disabled_rule_not_evaluated(self, auto_service, review_data):
        """A disabled rule should NOT be evaluated during auto-assignment"""
        engine = create_async_engine(TEST_DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            # Create reviewer
            user = User(
                user_id=1001,
                username="alice",
                display_name="Alice",
                email_address="alice@example.com",
                is_reviewer=True,
                active=True,
            )
            session.add(user)
            await session.flush()

            # Create a DISABLED rule
            rule = PullRequestReviewAutoAssignmentRule(
                name="Disabled Rule",
                priority=10,
                conditions={"project_key": ["PROJ-A"]},
                assign_to=["alice"],
                is_active=False,
                created_by="admin",
                created_at=get_current_time(),
                updated_at=get_current_time(),
            )
            session.add(rule)
            await session.flush()

            review_base = PullRequestReviewBase(
                pull_request_id="PR-42",
                project_key="PROJ-A",
                repository_slug="frontend-store",
                pull_request_user="alice",
                source_branch="feature/checkout",
                target_branch="main",
                pull_request_status="open",
            )
            session.add(review_base)
            await session.flush()

            assignments = await auto_service.auto_assign(
                db=session, review_base=review_base, review_data=review_data
            )

            assert len(assignments) == 0, "Disabled rule should not trigger assignments"

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_expired_rule_not_evaluated(self, auto_service, review_data):
        """A rule outside its date range should NOT be evaluated"""
        engine = create_async_engine(TEST_DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            user = User(
                user_id=1001,
                username="alice",
                display_name="Alice",
                email_address="alice@example.com",
                is_reviewer=True,
                active=True,
            )
            session.add(user)
            await session.flush()

            # Rule with expires_at in the past
            rule = PullRequestReviewAutoAssignmentRule(
                name="Expired Rule",
                priority=10,
                conditions={"project_key": ["PROJ-A"]},
                assign_to=["alice"],
                is_active=True,
                expires_at=datetime.now(UTC) - timedelta(days=1),
                created_by="admin",
                created_at=get_current_time(),
                updated_at=get_current_time(),
            )
            session.add(rule)
            await session.flush()

            review_base = PullRequestReviewBase(
                pull_request_id="PR-42",
                project_key="PROJ-A",
                repository_slug="frontend-store",
                pull_request_user="alice",
                source_branch="feature/checkout",
                target_branch="main",
                pull_request_status="open",
            )
            session.add(review_base)
            await session.flush()

            assignments = await auto_service.auto_assign(
                db=session, review_base=review_base, review_data=review_data
            )

            assert len(assignments) == 0, "Expired rule should not trigger assignments"

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_first_match_wins_by_priority(self, auto_service, review_data):
        """The highest-priority matching rule should be the only one applied"""
        engine = create_async_engine(TEST_DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            for uname in ["alice", "bob", "carol"]:
                user = User(
                    user_id=hash(uname) % 100000,
                    username=uname,
                    display_name=uname.title(),
                    email_address=f"{uname}@example.com",
                    is_reviewer=True,
                    active=True,
                )
                session.add(user)
            await session.flush()

            # Rule A: priority 10, assigns alice
            rule_a = PullRequestReviewAutoAssignmentRule(
                name="High Priority",
                priority=10,
                conditions={"project_key": ["PROJ-A"]},
                assign_to=["alice"],
                is_active=True,
                created_by="admin",
                created_at=get_current_time(),
                updated_at=get_current_time(),
            )
            session.add(rule_a)

            # Rule B: priority 20, assigns bob and carol
            rule_b = PullRequestReviewAutoAssignmentRule(
                name="Low Priority",
                priority=20,
                conditions={"project_key": ["PROJ-A"]},
                assign_to=["bob", "carol"],
                is_active=True,
                created_by="admin",
                created_at=get_current_time(),
                updated_at=get_current_time(),
            )
            session.add(rule_b)
            await session.flush()

            review_base = PullRequestReviewBase(
                pull_request_id="PR-42",
                project_key="PROJ-A",
                repository_slug="frontend-store",
                pull_request_user="alice",
                source_branch="feature/checkout",
                target_branch="main",
                pull_request_status="open",
            )
            session.add(review_base)
            await session.flush()

            assignments = await auto_service.auto_assign(
                db=session, review_base=review_base, review_data=review_data
            )

            # Only rule A (priority 10) should be applied — assigns alice only
            assert len(assignments) == 1
            assert assignments[0].reviewer == "alice"

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
