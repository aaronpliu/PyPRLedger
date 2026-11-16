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

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.auth_user import AuthUser
from src.models.user import User
from src.services.auth_service import AuthService
from src.services.sse_ticket_service import SSETicketService
from src.utils.jwt import create_access_token
from src.utils.password import hash_password


async def _ticket_for(auth_user_id: int) -> str:
    """Issue the one-shot ticket the stream now expects."""
    return await SSETicketService().issue(auth_user_id)


def _make_token(
    auth_user_id: int,
    *,
    username: str = "testuser",
    expires_in_minutes: int | None = None,
    extra_data: dict | None = None,
) -> str:
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
    from sqlalchemy import func, select

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
    from src.api.v1.endpoints import sse as sse_module

    sse_module._sse_connections.clear()


async def _reset_sse_broker() -> None:
    from src.services.sse_broker import SSEBroker

    broker = SSEBroker()
    await broker.stop()
    broker._clients.clear()
    broker._running = False


def _make_auto_disconnect_broker():
    """Create a mock broker that immediately sends None to terminate the stream."""
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    queue.put_nowait(None)
    broker = MagicMock()
    broker.register = AsyncMock(return_value=queue)
    broker.unregister = AsyncMock()
    return broker


@pytest.fixture(autouse=True)
async def clean_sse_state():
    _reset_sse_connections()
    await _reset_sse_broker()
    yield
    _reset_sse_connections()
    await _reset_sse_broker()


_mock_session_data = {
    "auth_user_id": "1",
    "username": "testuser",
    "refresh_token_hash": "deadbeef",
    "created_at": "2026-01-01T00:00:00+00:00",
    "last_activity_at": "2026-01-01T00:00:00+00:00",
    "ip_address": "127.0.0.1",
    "user_agent": "test",
}


def _make_mock_redis():
    mock_redis = MagicMock()
    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()
    mock_pubsub.get_message = AsyncMock(return_value=None)
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock()
    mock_redis.ttl = AsyncMock(return_value=60)
    mock_redis.close = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)

    # A key written by setex stays readable by get until it is deleted, which is
    # what the ticket flow relies on: the stream burns the ticket it is given.
    store: dict[str, str] = {}

    async def _setex(key: str, _ttl: int, value: str) -> bool:
        store[key] = value
        return True

    async def _get(key: str) -> str | None:
        return store.get(key)

    async def _delete(*keys: str) -> int:
        return sum(1 for key in keys if store.pop(key, None) is not None)

    mock_redis.setex = AsyncMock(side_effect=_setex)
    mock_redis.get = AsyncMock(side_effect=_get)
    mock_redis.delete = AsyncMock(side_effect=_delete)
    return mock_redis, mock_pubsub


@pytest.fixture(autouse=True)
async def mock_redis(db_session: AsyncSession):
    mock_redis, mock_pubsub = _make_mock_redis()

    def _fake_db_context_factory():
        @asynccontextmanager
        async def _ctx():
            yield db_session

        return _ctx()

    # Initialize the session maker so get_db_context / get_db_session work
    # even without calling init_db().  This is needed because middleware
    # and the SSE endpoint both access the DB through the session maker.
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    import src.core.database as db_mod

    test_session_maker = async_sessionmaker(
        db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    original_maker = db_mod._async_session_maker
    db_mod._async_session_maker = test_session_maker

    # Force RateLimitMiddleware to use the patched get_redis_client()
    # by clearing its cached redis_client reference.
    from src.main import app as fastapi_app

    _middleware_state = {}
    for mw in fastapi_app.user_middleware:
        if hasattr(mw, "cls") and mw.cls.__name__ == "RateLimitMiddleware":
            _middleware_state["mw"] = mw

    try:
        with (
            patch("src.utils.redis.get_redis_client", return_value=mock_redis),
            patch("src.core.middleware.get_redis_client", return_value=mock_redis),
            patch("src.services.sse_broker.get_redis_pubsub_client", return_value=mock_redis),
            patch("src.services.auth_service.get_redis_client", return_value=mock_redis),
            patch("src.services.sse_ticket_service.get_redis_client", return_value=mock_redis),
            patch("src.api.v1.endpoints.sse.get_db_context", side_effect=_fake_db_context_factory),
            patch.object(AuthService, "_get_refresh_session", return_value=_mock_session_data),
        ):
            yield mock_redis
    finally:
        db_mod._async_session_maker = original_maker


@pytest.mark.asyncio
async def test_sse_returns_401_without_a_valid_ticket(
    async_client: AsyncClient, db_session: AsyncSession
):
    await _seed_user(db_session)
    response = await async_client.get(
        "/api/v1/sse/stream",
        params={"ticket": "this-is-not-a-valid-ticket"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "TICKET_REQUIRED"


@pytest.mark.asyncio
async def test_sse_returns_401_when_nothing_is_sent(
    async_client: AsyncClient, db_session: AsyncSession
):
    await _seed_user(db_session)

    response = await async_client.get("/api/v1/sse/stream")

    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "TICKET_REQUIRED"


@pytest.mark.asyncio
async def test_sse_rejects_the_token_query_unless_the_legacy_flag_is_on(
    async_client: AsyncClient, db_session: AsyncSession
):
    auth_user, _ = await _seed_user(db_session)
    token = _make_token(auth_user.id, username=auth_user.username)

    response = await async_client.get("/api/v1/sse/stream", params={"token": token})

    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "TICKET_REQUIRED"


@pytest.mark.asyncio
async def test_ticket_endpoint_requires_authentication(async_client: AsyncClient):
    response = await async_client.post("/api/v1/sse/ticket")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ticket_is_spent_by_the_stream(async_client: AsyncClient, db_session: AsyncSession):
    auth_user, _ = await _seed_user(db_session)
    ticket = await _ticket_for(auth_user.id)

    with patch(
        "src.api.v1.endpoints.sse.get_sse_broker", return_value=_make_auto_disconnect_broker()
    ):
        first = await async_client.get("/api/v1/sse/stream", params={"ticket": ticket})
    second = await async_client.get("/api/v1/sse/stream", params={"ticket": ticket})

    assert first.status_code == 200
    assert second.status_code == 401
    assert second.json()["detail"]["error"] == "TICKET_REQUIRED"


@pytest.mark.asyncio
async def test_sse_returns_401_on_expired_token(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    monkeypatch.setattr(settings, "SSE_ALLOW_TOKEN_QUERY", True)
    auth_user, _ = await _seed_user(db_session)
    expired_token = _make_token(auth_user.id, expires_in_minutes=-10)
    response = await async_client.get(
        "/api/v1/sse/stream",
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
    from src.models.rbac import UserRoleAssignment
    from src.models.role import Role

    auth_user = AuthUser(
        username=f"viewer-{uuid.uuid4().hex[:6]}",
        email=f"viewer-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("testpassword"),
        user_id=None,
        is_active=True,
    )
    db_session.add(auth_user)
    await db_session.flush()
    await db_session.refresh(auth_user)

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

    ticket = await _ticket_for(auth_user.id)
    with patch(
        "src.api.v1.endpoints.sse.get_sse_broker", return_value=_make_auto_disconnect_broker()
    ):
        response = await async_client.get(
            "/api/v1/sse/stream",
            params={"ticket": ticket},
        )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")


@pytest.mark.asyncio
async def test_sse_prunes_oldest_connection_when_limit_exceeded(
    async_client: AsyncClient, db_session: AsyncSession
):
    auth_user, _ = await _seed_user(db_session)
    ticket = await _ticket_for(auth_user.id)

    from src.api.v1.endpoints import sse as sse_module

    sse_module._sse_connections[auth_user.username] = [
        ("conn-1", 0.0),
        ("conn-2", 1.0),
        ("conn-3", 2.0),
    ]

    try:
        with patch(
            "src.api.v1.endpoints.sse.get_sse_broker", return_value=_make_auto_disconnect_broker()
        ):
            response = await async_client.get(
                "/api/v1/sse/stream",
                params={"ticket": ticket},
            )
    finally:
        sse_module._sse_connections.pop(auth_user.username, None)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")


@pytest.mark.asyncio
async def test_sse_returns_503_when_broker_fails(
    async_client: AsyncClient, db_session: AsyncSession
):
    auth_user, _ = await _seed_user(db_session)
    ticket = await _ticket_for(auth_user.id)

    with patch("src.api.v1.endpoints.sse.get_sse_broker") as mock_get_broker:
        mock_broker = MagicMock()
        mock_broker.register = AsyncMock(side_effect=ConnectionError("Redis unavailable"))
        mock_get_broker.return_value = mock_broker

        response = await async_client.get(
            "/api/v1/sse/stream",
            params={"ticket": ticket},
        )

    assert response.status_code == 503
    body = response.json()
    assert body["detail"]["error"] == "SSE_UNAVAILABLE"
    assert "Real-time service temporarily unavailable" in body["detail"]["message"]


@pytest.mark.asyncio
async def test_sse_returns_200_and_streams_events(
    async_client: AsyncClient, db_session: AsyncSession
):
    auth_user, _ = await _seed_user(db_session)
    ticket = await _ticket_for(auth_user.id)

    review_event = {
        "review_id": 42,
        "project_key": "PROJ",
        "repository_slug": "my-repo",
        "pull_request_id": "PR-123",
        "created_date": "2025-01-01T00:00:00+00:00",
    }
    event_data = json.dumps(review_event)
    expected_sse = f"event: review_created\ndata: {event_data}\n\n"

    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _feed_then_close():
        await asyncio.sleep(0.05)
        await queue.put(expected_sse)
        await asyncio.sleep(0.05)
        await queue.put(None)

    with patch("src.api.v1.endpoints.sse.get_sse_broker") as mock_get_broker:
        mock_broker = MagicMock()
        mock_broker.register = AsyncMock(return_value=queue)
        mock_broker.unregister = AsyncMock()
        mock_get_broker.return_value = mock_broker

        asyncio.create_task(_feed_then_close())

        response = await async_client.get(
            "/api/v1/sse/stream",
            params={"ticket": ticket},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    raw_body = response.text
    assert expected_sse in raw_body, (
        f"Expected SSE event not found in response.\nExpected: {expected_sse!r}\nGot: {raw_body!r}"
    )


# --- Broker fan-out -----------------------------------------------------------
# The broker is what turns a published review into an SSE frame, so the event
# name and the involvement filter are worth pinning down on their own.


def _review_event(event_name: str = "review_created", **overrides):
    event = {
        "event": event_name,
        "review_id": 7,
        "project_key": "BAR",
        "repository_slug": "pyrag",
        "pull_request_id": "1203",
        "created_date": "2026-11-16T18:00:00+00:00",
        "pull_request_user": "aaronpliu",
        "reviewer": None,
        "assigned_by": None,
    }
    event.update(overrides)
    return event


@pytest.mark.asyncio
async def test_broker_forwards_the_event_name_it_was_given():
    from src.services.sse_broker import SSEBroker, SSEClient

    broker = SSEBroker()
    client = SSEClient(client_id="broker-test", git_username="aaronpliu", is_admin=True)
    broker._clients[client.client_id] = client
    try:
        await broker._fan_out(_review_event("review_updated"))
        frame = client.queue.get_nowait()
    finally:
        broker._clients.pop(client.client_id, None)

    assert frame.startswith("event: review_updated\ndata: ")
    assert '"pull_request_id": "1203"' in frame


@pytest.mark.asyncio
async def test_broker_skips_events_the_connected_user_is_not_part_of():
    from src.services.sse_broker import SSEBroker, SSEClient

    broker = SSEBroker()
    bystander = SSEClient(client_id="bystander", git_username="someone-else", is_admin=False)
    broker._clients[bystander.client_id] = bystander
    try:
        await broker._fan_out(_review_event("review_updated"))
        assert bystander.queue.empty()
    finally:
        broker._clients.pop(bystander.client_id, None)
