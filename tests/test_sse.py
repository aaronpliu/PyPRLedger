"""
Integration tests for the SSE (Server-Sent Events) streaming endpoint.

Covers:
- Authentication failures (invalid token, expired token)
- Authorization failure (no linked Bitbucket user)
- Rate limiting (connection limit exceeded)
- Infrastructure failure (Redis unavailable → 503)
- Happy path (200 + event stream)
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.auth_user import AuthUser
from src.models.user import User
from src.services.auth_service import AuthService
from src.utils.jwt import create_access_token
from src.utils.password import hash_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_token(
    auth_user_id: int,
    *,
    username: str = "testuser",
    expires_in_minutes: int | None = None,
    extra_data: dict | None = None,
) -> str:
    """Create a signed JWT access token for testing."""
    payload: dict = {
        "sub": str(auth_user_id),
        "username": username,
        "sid": uuid.uuid4().hex,
        "typ": "access",
    }
    if extra_data:
        payload.update(extra_data)
    expires_delta = (
        timedelta(minutes=expires_in_minutes) if expires_in_minutes is not None else None
    )
    return create_access_token(
        subject=auth_user_id, expires_delta=expires_delta, extra_data=payload
    )


async def _seed_user(
    db: AsyncSession,
    *,
    auth_username: str | None = None,
    git_username: str | None = None,
    is_active: bool = True,
) -> tuple[AuthUser, User]:
    """Insert an AuthUser + linked User row with auto-generated unique IDs.

    Because the session-scoped in-memory SQLite engine persists data across
    tests, we derive the next IDs from the current maximum to avoid UNIQUE
    constraint conflicts on repeated runs.
    """
    from sqlalchemy import func, select

    # Determine next free User ID to avoid UNIQUE constraint conflicts
    max_user = (await db.execute(select(func.max(User.id)))).scalar() or 0
    next_user_id = max_user + 1

    suffix = uuid.uuid4().hex[:6]
    auth_username = auth_username or f"testuser-{suffix}"
    git_username = git_username or f"testuser-{suffix}"

    auth_user = AuthUser(
        username=auth_username,
        email=f"{auth_username}@test.com",
        password_hash=hash_password("testpassword"),
        user_id=next_user_id,
        is_active=is_active,
    )
    db.add(auth_user)

    git_user = User(
        user_id=2000 + next_user_id,
        username=git_username,
        display_name=git_username.title(),
        email_address=f"{git_username}@bitbucket.test",
        active=True,
        is_reviewer=True,
    )
    db.add(git_user)

    await db.flush()
    await db.refresh(auth_user)
    await db.refresh(git_user)

    await db.commit()
    return auth_user, git_user


def _reset_sse_connections() -> None:
    """Clear the module-level SSE connection tracker between tests."""
    from src.api.v1.endpoints import sse as sse_module

    sse_module._sse_connections.clear()


@pytest.fixture(autouse=True)
def clean_sse_connections():
    """Automatically reset SSE connection tracker before and after every test."""
    _reset_sse_connections()
    yield
    _reset_sse_connections()


# ---------------------------------------------------------------------------
# Redis / DB fixtures
# ---------------------------------------------------------------------------
#
# The test ASGI app does not run the lifespan hooks that call init_redis() or
# init_db(), so the global ``_redis_client`` and ``_async_session_maker`` are
# ``None`` in tests.  We fix both here:
#
# 1. **Redis** — Every module that does ``from src.utils.redis import
#    get_redis_client`` holds its own *local name binding* at import time.
#    ``patch("src.utils.redis.get_redis_client")`` cannot update those
#    already-imported copies.  We must patch **each caller's own module
#    namespace** explicitly.
#
# 2. **Database** — The conftest ``db_session`` fixture creates sessions
#    directly (bypassing ``init_db()``), so ``get_db_context()`` (which calls
#    ``get_session_maker()``) raises RuntimeError.  We redirect ``get_db_context``
#    to yield the test ``db_session`` instead.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def mock_redis(db_session: AsyncSession):
    """Provide a working Redis mock and a patched DB context for every test."""
    mock_redis = MagicMock()

    # Default pubsub: subscribe/unsubscribe/close are async no-ops; listen is
    # an empty async generator so the SSE stream closes cleanly.
    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()

    async def _empty_listen():
        if False:
            yield  # pragma: no cover
        return

    mock_pubsub.listen = MagicMock(return_value=_empty_listen())
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock()
    mock_redis.ttl = AsyncMock(return_value=60)
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock(return_value=True)
    mock_redis.close = AsyncMock()

    @asynccontextmanager
    async def _fake_db_context():
        """Yield the test session in place of the real get_db_context()."""
        yield db_session

    _mock_session_data = json.dumps(
        {
            "auth_user_id": 1,
            "username": "testuser",
            "refresh_token_hash": "deadbeef",
            "created_at": "2026-01-01T00:00:00+00:00",
            "last_activity_at": "2026-01-01T00:00:00+00:00",
            "ip_address": "127.0.0.1",
            "user_agent": "test",
        }
    )

    # Patch every module that holds a stale local binding of get_redis_client,
    # and patch get_db_context in both the database module and the SSE endpoint
    # module (which has its own local binding from the import).
    #
    # Also patch AuthService._get_refresh_session so tokens with any session ID
    # are treated as having a valid, active refresh session.  This lets the
    # endpoint logic advance past the session check to the branch under test.
    # Tests that need the session to be ABSENT (expired-session scenario) can
    # re-patch _get_refresh_session inside the test body.
    with (
        patch("src.utils.redis.get_redis_client", return_value=mock_redis),
        patch("src.core.middleware.get_redis_client", return_value=mock_redis),
        patch("src.api.v1.endpoints.sse.get_redis_client", return_value=mock_redis),
        patch("src.services.auth_service.get_redis_client", return_value=mock_redis),
        patch("src.core.database.get_db_context", side_effect=_fake_db_context),
        patch("src.api.v1.endpoints.sse.get_db_context", side_effect=_fake_db_context),
        patch.object(AuthService, "_get_refresh_session", return_value=_mock_session_data),
    ):
        yield mock_redis


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sse_returns_401_on_invalid_token(
    async_client: AsyncClient, db_session: AsyncSession
):
    """GET /api/v1/reviews/stream with an obviously invalid token → 401."""
    await _seed_user(db_session)

    response = await async_client.get(
        "/api/v1/reviews/stream",
        params={"token": "this-is-not-a-valid-jwt-token"},
    )

    assert response.status_code == 401
    body = response.json()
    # http_exception_handler wraps HTTPException.detail under "detail"
    assert body["detail"]["error"] == "INVALID_TOKEN"
    assert "Invalid token" in body["detail"]["message"]


@pytest.mark.asyncio
async def test_sse_returns_401_on_expired_token(
    async_client: AsyncClient, db_session: AsyncSession
):
    """GET /api/v1/reviews/stream with an expired token → 401."""
    auth_user, _ = await _seed_user(db_session)

    expired_token = _make_token(auth_user.id, expires_in_minutes=-10)

    response = await async_client.get(
        "/api/v1/reviews/stream",
        params={"token": expired_token},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["detail"]["error"] == "TOKEN_EXPIRED"
    assert "Token expired" in body["detail"]["message"]


@pytest.mark.asyncio
async def test_sse_allows_non_admin_without_git_binding(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Non-admin user without git binding can connect (gets 200) but receives no events."""
    from src.models.rbac import UserRoleAssignment
    from src.models.role import Role

    # Create a non-admin user with viewer role
    auth_user = AuthUser(
        username=f"viewer-{uuid.uuid4().hex[:6]}",
        email=f"viewer-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("testpassword"),
        user_id=None,  # ← no Bitbucket account linked
        is_active=True,
    )
    db_session.add(auth_user)
    await db_session.flush()
    await db_session.refresh(auth_user)

    # Assign viewer role (non-admin)
    stmt = select(Role).where(Role.name == "viewer")
    result = await db_session.execute(stmt)
    existing_role = result.scalar_one_or_none()
    if not existing_role:
        viewer_role = Role(
            name="viewer",
            description="Read-only access",
            permissions={"reviews": ["read"], "scores": ["read"]},
        )
        db_session.add(viewer_role)
        await db_session.flush()
        await db_session.refresh(viewer_role)
    else:
        viewer_role = existing_role

    assignment = UserRoleAssignment(
        auth_user_id=auth_user.id,
        role_id=viewer_role.id,
        resource_type="global",
        resource_id=None,
    )
    db_session.add(assignment)
    await db_session.flush()
    await db_session.commit()

    token = _make_token(auth_user.id, username=auth_user.username)

    # Should get 200 OK (no 403) - connection succeeds but no events streamed
    response = await async_client.get(
        "/api/v1/reviews/stream",
        params={"token": token},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    # Non-admin users without git binding won't receive actual events


@pytest.mark.asyncio
async def test_sse_allows_admin_without_git_binding_receives_all_events(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Admin user without git binding gets 200 and receives all review events."""
    from src.models.rbac import UserRoleAssignment
    from src.models.role import Role

    # Create admin user without git binding
    auth_user = AuthUser(
        username=f"admin-{uuid.uuid4().hex[:6]}",
        email=f"admin-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("testpassword"),
        user_id=None,  # ← no Bitbucket account linked
        is_active=True,
    )
    db_session.add(auth_user)
    await db_session.flush()
    await db_session.refresh(auth_user)

    # Assign system_admin role
    stmt = select(Role).where(Role.name == "system_admin")
    result = await db_session.execute(stmt)
    admin_role = result.scalar_one_or_none()
    if not admin_role:
        admin_role = Role(
            name="system_admin",
            description="Full system admin",
            permissions={"reviews": ["read", "create", "update", "delete"]},
        )
        db_session.add(admin_role)
        await db_session.flush()
        await db_session.refresh(admin_role)

    assignment = UserRoleAssignment(
        auth_user_id=auth_user.id,
        role_id=admin_role.id,
        resource_type="global",
        resource_id=None,
    )
    db_session.add(assignment)
    await db_session.flush()
    await db_session.commit()

    token = _make_token(auth_user.id, username=auth_user.username)

    # Build a review event that admin should receive
    review_event = {
        "review_id": 42,
        "project_key": "PROJ",
        "repository_slug": "my-repo",
        "pull_request_id": "PR-123",
        "created_date": "2025-01-01T00:00:00+00:00",
        "pull_request_user": "someone",
        "reviewer": "someone_else",
        "assigned_by": "assigner",
    }
    event_data = json.dumps(
        {
            "review_id": review_event["review_id"],
            "project_key": review_event["project_key"],
            "repository_slug": review_event["repository_slug"],
            "pull_request_id": review_event["pull_request_id"],
            "created_date": review_event["created_date"],
        }
    )
    expected_sse = f"event: review_created\ndata: {event_data}\n\n"

    mock_message = {"type": "message", "data": json.dumps(review_event)}

    async def _mock_listen():
        yield mock_message

    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.listen = MagicMock(return_value=_mock_listen())
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()

    with patch("src.api.v1.endpoints.sse.get_redis_client") as mock_get:
        mock_redis = MagicMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        mock_get.return_value = mock_redis

        response = await async_client.get(
            "/api/v1/reviews/stream",
            params={"token": token},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    raw_body = response.text
    assert expected_sse in raw_body, (
        f"Expected admin to receive all events.\nExpected: {expected_sse!r}\nGot: {raw_body!r}"
    )

    mock_pubsub.subscribe.assert_awaited_once_with("reviews:created")
    mock_pubsub.unsubscribe.assert_awaited_once_with("reviews:created")
    mock_pubsub.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_sse_returns_429_when_connection_limit_exceeded(
    async_client: AsyncClient, db_session: AsyncSession
):
    """4th concurrent SSE connection for the same user → 429."""
    auth_user, _ = await _seed_user(db_session)
    token = _make_token(auth_user.id)

    # Seed 3 existing connections to fill the per-user limit.
    from src.api.v1.endpoints import sse as sse_module

    sse_module._sse_connections[auth_user.username] = {"conn-1", "conn-2", "conn-3"}

    try:
        response = await async_client.get(
            "/api/v1/reviews/stream",
            params={"token": token},
        )
    finally:
        sse_module._sse_connections.pop(auth_user.username, None)

    assert response.status_code == 429
    body = response.json()
    assert body["detail"]["error"] == "CONNECTION_LIMIT_EXCEEDED"
    assert "Maximum 3 concurrent" in body["detail"]["message"]


@pytest.mark.asyncio
async def test_sse_returns_503_when_redis_unavailable(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Redis pub/sub init failure → 503 (validates Fix 1).

    The autouse ``mock_redis`` fixture provides a working default; we override
    ``pubsub()`` here so that ``subscribe`` raises a ``ConnectionError`` before
    the StreamingResponse is created.
    """
    auth_user, _ = await _seed_user(db_session)
    token = _make_token(auth_user.id)

    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock(side_effect=ConnectionError("Redis connection refused"))

    # Override only the pubsub part of the default mock.
    with patch("src.api.v1.endpoints.sse.get_redis_client") as mock_get:
        mock_redis = MagicMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        mock_get.return_value = mock_redis

        response = await async_client.get(
            "/api/v1/reviews/stream",
            params={"token": token},
        )

    assert response.status_code == 503
    body = response.json()
    assert body["detail"]["error"] == "SSE_UNAVAILABLE"
    assert "Real-time service temporarily unavailable" in body["detail"]["message"]


@pytest.mark.asyncio
async def test_sse_returns_200_and_streams_events_on_valid_connection(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Happy path: valid token → 200, text/event-stream, at least one SSE event."""
    auth_user, _ = await _seed_user(db_session)
    token = _make_token(auth_user.id)

    # Build a single well-formed review_created event
    review_event = {
        "review_id": 42,
        "project_key": "PROJ",
        "repository_slug": "my-repo",
        "pull_request_id": "PR-123",
        "created_date": "2025-01-01T00:00:00+00:00",
        "pull_request_user": auth_user.username,  # ← involved user
        "reviewer": auth_user.username,
        "assigned_by": auth_user.username,
    }
    event_data = json.dumps(
        {
            "review_id": review_event["review_id"],
            "project_key": review_event["project_key"],
            "repository_slug": review_event["repository_slug"],
            "pull_request_id": review_event["pull_request_id"],
            "created_date": review_event["created_date"],
        }
    )
    expected_sse = f"event: review_created\ndata: {event_data}\n\n"

    # ----- mock pub/sub -----
    mock_message = {"type": "message", "data": json.dumps(review_event)}

    async def _mock_listen():
        """Yield one message then stop — httpx reads the whole body and exits."""
        yield mock_message

    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.listen = MagicMock(return_value=_mock_listen())
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()

    # Override the autouse mock_redis pubsub for this test.
    with patch("src.api.v1.endpoints.sse.get_redis_client") as mock_get:
        mock_redis = MagicMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        mock_get.return_value = mock_redis

        response = await async_client.get(
            "/api/v1/reviews/stream",
            params={"token": token},
        )

    # ----- status + headers -----
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    assert response.headers["content-type"].startswith("text/event-stream")

    # ----- body -----
    raw_body = response.text
    assert expected_sse in raw_body, (
        f"Expected SSE event not found in response.\nExpected: {expected_sse!r}\nGot: {raw_body!r}"
    )

    # ----- pub/sub lifecycle -----
    mock_pubsub.subscribe.assert_awaited_once_with("reviews:created")
    mock_pubsub.unsubscribe.assert_awaited_once_with("reviews:created")
    mock_pubsub.close.assert_awaited_once()
