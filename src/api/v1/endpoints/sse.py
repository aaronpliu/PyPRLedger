from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from src.core.database import get_db_context
from src.core.exceptions import (
    InvalidTokenException,
    TokenExpiredException,
    UserInactiveException,
)
from src.models.auth_user import AuthUser
from src.models.user import User
from src.services.auth_service import AuthService
from src.services.rbac_service import RBACService
from src.services.sse_broker import get_sse_broker
from src.utils.metrics import metrics


logger = logging.getLogger(__name__)

router = APIRouter()

# Connection tracking: {username: [(connection_id, start_time), ...]}
_sse_connections: dict[str, list[tuple[str, float]]] = {}

# Maximum connections per user
MAX_CONNECTIONS_PER_USER = 3
MAX_CONNECTIONS_PER_ADMIN = 10

# Maximum total SSE connections across all users
MAX_TOTAL_CONNECTIONS = 2000

# Idle timeout — close connection if no events are sent for this duration
IDLE_TIMEOUT = 300  # 5 minutes

CONNECTION_LIFETIME_WARNING = (
    "Connection limit reached — oldest connection pruned. "
    "This is normal after page refresh but excessive pruning suggests a leak."
)


def _prune_oldest_user_connection(tracking_username: str) -> None:
    """Prune the oldest connection for a user to make room for a new one."""
    user_connections = _sse_connections.get(tracking_username, [])
    if not user_connections:
        return
    user_connections.sort(key=lambda x: x[1])
    old_id, _ = user_connections[0]
    _sse_connections[tracking_username] = user_connections[1:]
    if not _sse_connections[tracking_username]:
        del _sse_connections[tracking_username]
    logger.info(
        "SSE connection abort signalled for pruning",
        extra={"connection_id": old_id, "username": tracking_username},
    )


async def _sse_event_generator(
    queue: asyncio.Queue[str | None],
    connection_id: str,
    tracking_username: str | None,
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE events from the broker queue.

    Reads from a personal asyncio.Queue fed by the shared SSEBroker.
    Sends None from the queue as a signal to disconnect.
    """
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=IDLE_TIMEOUT)
            except TimeoutError:
                logger.info(
                    "SSE connection idle timeout",
                    extra={"connection_id": connection_id, "idle_seconds": IDLE_TIMEOUT},
                )
                break

            if event is None:
                logger.info(
                    "SSE connection disconnected by broker",
                    extra={"connection_id": connection_id},
                )
                break

            yield event

    except asyncio.CancelledError:
        logger.debug(
            "SSE connection cancelled (client disconnected)",
            extra={"connection_id": connection_id},
        )


@router.get("/stream")
async def stream_reviews(
    token: Annotated[str, Query(description="JWT access token for SSE authentication")],
) -> StreamingResponse:
    """
    Server-Sent Events (SSE) endpoint for real-time new review notifications.

    Uses a shared SSEBroker with a single Redis pubsub subscription that
    multiplexes events to all connected clients via asyncio.Queues.
    This supports thousands of concurrent connections using only 1 Redis connection.

    Authentication:
        JWT token passed as query parameter: ?token=<JWT>

    Authorization:
        - Any authenticated user can connect (no Bitbucket linkage required)
        - Non-admin users without linked Bitbucket account receive no events
        - Admin users (review_admin, system_admin) receive all review events

    Connection limits:
        - Maximum 3 concurrent SSE connections per regular user
        - Maximum 10 concurrent SSE connections per admin user
        - When limit is exceeded, the oldest connection is automatically pruned
        - Connections idle for 5 minutes are automatically closed
    """
    connection_id = str(uuid.uuid4())

    async with get_db_context() as db:
        auth_service = AuthService(db)
        try:
            auth_user = await auth_service.get_current_user(token)
        except TokenExpiredException:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "TOKEN_EXPIRED", "message": "Token expired"},
            )
        except InvalidTokenException:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "INVALID_TOKEN", "message": "Invalid token"},
            )

        stmt = select(AuthUser).where(AuthUser.id == auth_user.id)
        result = await db.execute(stmt)
        auth_user_record = result.scalar_one_or_none()
        if not auth_user_record or not auth_user_record.is_active:
            raise UserInactiveException(username=auth_user.username)

        rbac_service = RBACService(db)
        user_roles = await rbac_service.get_user_roles(auth_user.id)
        role_names = {role["role_name"] for role in user_roles}
        is_admin = "review_admin" in role_names or "system_admin" in role_names

        stmt = select(User).where(User.id == auth_user.user_id)
        result = await db.execute(stmt)
        git_user = result.scalar_one_or_none()

        git_username = None
        if git_user:
            git_username = git_user.username

        tracking_username = git_username or (
            f"admin:{auth_user.id}" if is_admin else auth_user.username
        )

    # Enforce global connection limit
    total_connections = sum(len(conns) for conns in _sse_connections.values())
    if total_connections >= MAX_TOTAL_CONNECTIONS:
        logger.warning(
            "Global SSE connection limit reached — rejecting new connection",
            extra={
                "total_connections": total_connections,
                "max_total": MAX_TOTAL_CONNECTIONS,
                "username": tracking_username,
            },
        )
        metrics.sse_connections_total.labels(status="rejected_global_limit").inc()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "SSE_UNAVAILABLE",
                "message": "Too many real-time connections. Please try again in a moment.",
            },
        )

    # Enforce per-user connection limit — prune oldest to make room
    user_connections = _sse_connections.get(tracking_username, [])
    max_connections = MAX_CONNECTIONS_PER_ADMIN if is_admin else MAX_CONNECTIONS_PER_USER
    if len(user_connections) >= max_connections:
        _prune_oldest_user_connection(tracking_username)
        logger.warning(
            CONNECTION_LIFETIME_WARNING,
            extra={
                "username": tracking_username,
                "remaining": len(_sse_connections.get(tracking_username, [])),
            },
        )

    # Track this connection
    now = time.monotonic()
    if tracking_username not in _sse_connections:
        _sse_connections[tracking_username] = []
    _sse_connections[tracking_username].append((connection_id, now))

    total_connections = sum(len(conns) for conns in _sse_connections.values())
    metrics.sse_connections_active.set(total_connections)
    metrics.sse_connections_total.labels(status="connected").inc()

    logger.info(
        "SSE connection established",
        extra={
            "user_id": auth_user.id,
            "username": tracking_username,
            "is_admin": is_admin,
            "connection_id": connection_id,
            "total_user_connections": len(_sse_connections[tracking_username]),
            "total_global_connections": total_connections,
        },
    )

    # Register with the shared broker — gets a personal asyncio.Queue
    broker = get_sse_broker()
    try:
        queue = await broker.register(connection_id, git_username, is_admin)
    except Exception as exc:
        logger.error(
            f"Failed to register with SSEBroker: {exc}",
            extra={"connection_id": connection_id, "username": tracking_username},
        )
        # Clean up connection tracking
        if tracking_username in _sse_connections:
            _sse_connections[tracking_username] = [
                (cid, t) for cid, t in _sse_connections[tracking_username] if cid != connection_id
            ]
            if not _sse_connections[tracking_username]:
                del _sse_connections[tracking_username]
        metrics.sse_connections_total.labels(status="redis_failed").inc()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "SSE_UNAVAILABLE",
                "message": "Real-time service temporarily unavailable. Please try again.",
            },
        ) from exc

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for event in _sse_event_generator(queue, connection_id, tracking_username):
                yield event
        except Exception as e:
            logger.error(
                "SSE stream error",
                extra={
                    "user_id": auth_user.id,
                    "username": tracking_username,
                    "is_admin": is_admin,
                    "connection_id": connection_id,
                    "error": str(e),
                },
            )
        finally:
            # Unregister from broker
            await broker.unregister(connection_id)

            # Clean up connection tracking
            if tracking_username in _sse_connections:
                _sse_connections[tracking_username] = [
                    (cid, t)
                    for cid, t in _sse_connections[tracking_username]
                    if cid != connection_id
                ]
                if not _sse_connections[tracking_username]:
                    del _sse_connections[tracking_username]

            total = sum(len(conns) for conns in _sse_connections.values())
            metrics.sse_connections_active.set(total)
            metrics.sse_connections_total.labels(status="disconnected").inc()

            logger.info(
                "SSE connection closed",
                extra={
                    "user_id": auth_user.id,
                    "username": tracking_username,
                    "is_admin": is_admin,
                    "connection_id": connection_id,
                },
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
