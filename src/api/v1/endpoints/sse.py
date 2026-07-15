import asyncio
import contextlib
import json
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
from src.utils.metrics import metrics
from src.utils.redis import get_redis_pubsub_client


logger = logging.getLogger(__name__)

router = APIRouter()

# Redis pub/sub channel for review creation events
REVIEW_CREATED_CHANNEL = "reviews:created"

# Connection tracking: {username: [(connection_id, start_time), ...]}
# Using list of tuples so we can find and prune the oldest connections
_sse_connections: dict[str, list[tuple[str, float]]] = {}

# Abort signals for pruning stale connections: {connection_id: bool}
# Set to True when a connection should be gracefully shut down
_sse_abort_flags: dict[str, bool] = {}

# Maximum connections per user
# Admin users get higher limit since they may access multiple pages simultaneously
MAX_CONNECTIONS_PER_USER = 3
MAX_CONNECTIONS_PER_ADMIN = 10

# Maximum total SSE connections across all users (safety net against pool exhaustion)
MAX_TOTAL_CONNECTIONS = 200

# Heartbeat interval in seconds — keeps connection alive and detects dead clients
HEARTBEAT_INTERVAL = 30

# Idle timeout — close connection if no events are sent for this duration
# Prevents zombie connections from occupying tracked slots forever
IDLE_TIMEOUT = 300  # 5 minutes

# Redis pub/sub retry configuration
REDIS_PUBSUB_MAX_RETRIES = 3
REDIS_PUBSUB_RETRY_BASE_DELAY = 0.5  # seconds, doubles each attempt

CONNECTION_LIFETIME_WARNING = (
    "Connection limit reached — oldest connection pruned. "
    "This is normal after page refresh but excessive pruning suggests a leak."
)

# Background cleanup task handle
_cleanup_task: asyncio.Task | None = None


async def _periodic_stale_connection_cleanup():
    """Background task to clean up stale SSE connections.

    Runs every 60 seconds and removes connection tracking entries
    that have exceeded the idle timeout. This prevents zombie connections
    from accumulating and exhausting the Redis pub/sub pool.
    """
    while True:
        await asyncio.sleep(60)
        try:
            now = time.monotonic()
            stale_count = 0

            for username, connections in list(_sse_connections.items()):
                fresh_connections = []
                for conn_id, start_time in connections:
                    age = now - start_time
                    if age > IDLE_TIMEOUT and not _sse_abort_flags.get(conn_id):
                        # Mark stale connection for abort
                        _sse_abort_flags[conn_id] = True
                        stale_count += 1
                        logger.info(
                            "Stale SSE connection marked for cleanup",
                            extra={
                                "connection_id": conn_id,
                                "username": username,
                                "age_seconds": int(age),
                            },
                        )
                    else:
                        fresh_connections.append((conn_id, start_time))

                if fresh_connections:
                    _sse_connections[username] = fresh_connections
                elif username in _sse_connections:
                    del _sse_connections[username]

            if stale_count > 0:
                total = sum(len(c) for c in _sse_connections.values())
                logger.info(
                    "SSE stale connection cleanup complete",
                    extra={
                        "stale_pruned": stale_count,
                        "total_remaining": total,
                    },
                )

                # Update active connections gauge
                metrics.sse_connections_active.set(total)

        except Exception:
            logger.warning("Error in SSE stale connection cleanup", exc_info=True)


async def start_sse_cleanup_task():
    """Start the background stale connection cleanup task."""
    global _cleanup_task
    if _cleanup_task is None or _cleanup_task.done():
        _cleanup_task = asyncio.create_task(_periodic_stale_connection_cleanup())
        logger.info("SSE stale connection cleanup task started (interval: 60s)")


async def stop_sse_cleanup_task():
    """Stop the background stale connection cleanup task."""
    global _cleanup_task
    if _cleanup_task is not None and not _cleanup_task.done():
        _cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _cleanup_task
        _cleanup_task = None
        logger.info("SSE stale connection cleanup task stopped")


def _is_user_involved_in_review(
    review: dict,
    git_username: str | None,
    is_admin: bool = False,
) -> bool:
    """
    Determine if a user should receive a review event via SSE.

    Admin users receive ALL review events (matching API visibility rules).
    Regular users only receive events for reviews they're involved in:
    - The PR author (pull_request_user)
    - The assigned reviewer (reviewer)
    - The user who assigned the review (assigned_by)

    Args:
        review: Review event payload from Redis
        git_username: Bitbucket username of the authenticated user (None if not linked)
        is_admin: Whether the user has an admin role (review_admin or system_admin)

    Returns:
        True if user should receive the event, False otherwise
    """
    # Admin users receive ALL events (matches API visibility)
    if is_admin:
        return True

    # Regular users must have git binding to receive any events
    if not git_username:
        return False

    # Check if user is involved in the review
    if review.get("pull_request_user") == git_username:
        return True
    if review.get("reviewer") == git_username:
        return True
    return review.get("assigned_by") == git_username


async def _sse_event_generator(
    redis_client,
    pubsub,
    git_username: str | None,
    is_admin: bool,
    connection_id: str,
    tracking_username: str | None,
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE-formatted review events for a connected user.

    Subscribes to the Redis reviews:created channel, filters events by user
    involvement (or admin status), and yields SSE-formatted strings. Sends
    periodic heartbeats to detect dead connections and checks the abort
    flag for stale connection pruning. Cleans up the connection tracking
    set when the generator is closed.

    Args:
        redis_client: Redis client for pub/sub
        pubsub: Pre-initialised Redis pub/sub instance (caller handles errors)
        git_username: Bitbucket username of the connected user (None if not linked)
        is_admin: Whether the user has an admin role (receives all events)
        connection_id: Unique ID for this SSE connection (for tracking)
        tracking_username: Key used for per-user connection tracking

    Yields:
        SSE-formatted event strings
    """
    last_event_time = time.monotonic()
    last_heartbeat_time = time.monotonic()

    try:
        while True:
            # Check if this connection should be pruned (stale connection replacement)
            if _sse_abort_flags.get(connection_id):
                logger.info(
                    "SSE connection pruned by newer connection",
                    extra={"connection_id": connection_id},
                )
                break

            # Check idle timeout — close if no events sent for too long
            now = time.monotonic()
            if now - last_event_time > IDLE_TIMEOUT:
                logger.info(
                    "SSE connection idle timeout",
                    extra={
                        "connection_id": connection_id,
                        "idle_seconds": IDLE_TIMEOUT,
                    },
                )
                break

            # Poll for Redis message with 1s timeout
            # Using poll instead of blocking listen() so we can periodically
            # check abort flags, send heartbeats, and enforce idle timeout
            message = await pubsub.get_message(timeout=1.0)

            if message and message["type"] == "message":
                try:
                    review = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Failed to parse SSE event from Redis: {e}")
                    metrics.sse_events_filtered_total.labels(filtered="parse_error").inc()
                    continue

                is_involved = _is_user_involved_in_review(review, git_username, is_admin)

                # Log filtering decision for debugging
                logger.debug(
                    "SSE event filtering",
                    extra={
                        "review_id": review.get("review_id"),
                        "pull_request_user": review.get("pull_request_user"),
                        "git_username": git_username,
                        "is_admin": is_admin,
                        "is_involved": is_involved,
                    },
                )

                if is_involved:
                    minimal_payload = {
                        "review_id": review["review_id"],
                        "project_key": review["project_key"],
                        "repository_slug": review["repository_slug"],
                        "pull_request_id": review["pull_request_id"],
                        "created_date": review["created_date"],
                    }
                    event_data = json.dumps(minimal_payload)
                    logger.info(
                        "SSE event sent to user",
                        extra={
                            "review_id": review["review_id"],
                            "tracking_username": tracking_username,
                            "is_admin": is_admin,
                        },
                    )
                    yield f"event: review_created\ndata: {event_data}\n\n"
                    metrics.sse_events_filtered_total.labels(filtered="false").inc()
                    last_event_time = time.monotonic()
                else:
                    metrics.sse_events_filtered_total.labels(filtered="true").inc()

            # Send heartbeat every HEARTBEAT_INTERVAL seconds
            now = time.monotonic()
            if now - last_heartbeat_time >= HEARTBEAT_INTERVAL:
                yield ": heartbeat\n\n"
                last_heartbeat_time = now
    except asyncio.CancelledError:
        # Client disconnected (browser refresh/close) — let cleanup proceed
        logger.debug(
            "SSE connection cancelled (client disconnected)",
            extra={"connection_id": connection_id},
        )
    finally:
        await pubsub.unsubscribe(REVIEW_CREATED_CHANNEL)
        await pubsub.close()

        # Clean up abort flag
        _sse_abort_flags.pop(connection_id, None)

        # Clean up connection tracking
        if tracking_username and tracking_username in _sse_connections:
            _sse_connections[tracking_username] = [
                (cid, t) for (cid, t) in _sse_connections[tracking_username] if cid != connection_id
            ]
            if not _sse_connections[tracking_username]:
                del _sse_connections[tracking_username]


@router.get("/stream")
async def stream_reviews(
    token: Annotated[str, Query(description="JWT access token for SSE authentication")],
) -> StreamingResponse:
    """
    Server-Sent Events (SSE) endpoint for real-time new review notifications.

    Establishes a persistent connection that streams review creation events
    to the authenticated user. Only events where the user is involved
    (reviewer, assigner, or PR author) are forwarded, unless the user has
    an admin role (review_admin or system_admin), who receive all events.

    Authentication:
        JWT token passed as query parameter: ?token=<JWT>

    Authorization:
        - Any authenticated user can connect (no Bitbucket linkage required)
        - Non-admin users without linked Bitbucket account receive no events
        - Admin users (review_admin, system_admin) receive all review events,
          even without a linked Bitbucket account

    Connection limits:
        - Maximum 3 concurrent SSE connections per regular user
        - Maximum 10 concurrent SSE connections per admin user (review_admin, system_admin)
        - When limit is exceeded, the oldest connection is automatically pruned
          to make room for the new one (graceful degradation on page refresh)
        - Connections idle for 5+ minutes are automatically closed
        - Server sends a heartbeat every 30 seconds to detect dead clients

    Args:
        token: JWT access token from query parameter

    Returns:
        StreamingResponse with text/event-stream content type

    Raises:
        HTTPException 401: If token is invalid or expired
        HTTPException 403: If user account is inactive
        HTTPException 429: If connection limit exceeded
    """
    redis_client = get_redis_pubsub_client()
    connection_id = str(uuid.uuid4())

    # Validate JWT token and get auth user (requires DB session)
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

        # Check if user account is active
        stmt = select(AuthUser).where(AuthUser.id == auth_user.id)
        result = await db.execute(stmt)
        auth_user_record = result.scalar_one_or_none()
        if not auth_user_record or not auth_user_record.is_active:
            raise UserInactiveException(username=auth_user.username)

        # Check user roles to determine admin status
        rbac_service = RBACService(db)
        user_roles = await rbac_service.get_user_roles(auth_user.id)
        role_names = {role["role_name"] for role in user_roles}
        is_admin = "review_admin" in role_names or "system_admin" in role_names

        # Get Bitbucket username for filtering and connection tracking
        stmt = select(User).where(User.id == auth_user.user_id)
        result = await db.execute(stmt)
        git_user = result.scalar_one_or_none()

        git_username = None
        if git_user:
            git_username = git_user.username
        # Non-admin without git binding: allow connection but will receive no events

        # Use git_username for tracking if available, otherwise use a fallback for admin without git binding
        tracking_username = git_username or (
            f"admin:{auth_user.id}" if is_admin else auth_user.username
        )

    # Enforce global connection limit (safety net against Redis pool exhaustion)
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

    # Enforce per-user connection limit — prune oldest connection to make room
    # This handles the common case where a user refreshes the page and the old
    # connection hasn't been cleaned up yet (e.g., beforeunload didn't fire).
    user_connections = _sse_connections.get(tracking_username, [])
    max_connections = MAX_CONNECTIONS_PER_ADMIN if is_admin else MAX_CONNECTIONS_PER_USER
    if len(user_connections) >= max_connections:
        # Sort by start_time (oldest first) and prune the oldest
        user_connections.sort(key=lambda x: x[1])
        pruned_count = len(user_connections) - max_connections + 1
        for i in range(pruned_count):
            old_id, _ = user_connections[i]
            _sse_abort_flags[old_id] = True
            logger.info(
                "SSE connection abort signalled for pruning",
                extra={
                    "connection_id": old_id,
                    "username": tracking_username,
                },
            )

        # Keep only the (max_connections - 1) newest entries
        _sse_connections[tracking_username] = user_connections[pruned_count:]

        logger.warning(
            CONNECTION_LIFETIME_WARNING,
            extra={
                "username": tracking_username,
                "pruned_count": pruned_count,
                "remaining": len(_sse_connections[tracking_username]),
            },
        )

    # Track this connection
    now = time.monotonic()
    if tracking_username not in _sse_connections:
        _sse_connections[tracking_username] = []
    _sse_connections[tracking_username].append((connection_id, now))

    # Update active connections gauge
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

    # Ensure the stale connection cleanup task is running
    await start_sse_cleanup_task()

    # Initialise Redis pub/sub with retry logic for transient failures.
    # Each SSE connection holds a dedicated pub/sub subscription, so we
    # retry with backoff to handle momentary pool exhaustion or network blips.
    pubsub = None
    last_exc = None
    for attempt in range(1, REDIS_PUBSUB_MAX_RETRIES + 1):
        try:
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(REVIEW_CREATED_CHANNEL)
            break
        except Exception as exc:
            last_exc = exc
            # Clean up the failed pubsub object to release the connection
            with contextlib.suppress(Exception):
                await pubsub.close()
            pubsub = None

            if attempt < REDIS_PUBSUB_MAX_RETRIES:
                delay = REDIS_PUBSUB_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Redis pub/sub init failed, retrying",
                    extra={
                        "attempt": attempt,
                        "max_retries": REDIS_PUBSUB_MAX_RETRIES,
                        "delay_seconds": delay,
                        "username": tracking_username,
                        "error": str(exc),
                    },
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "Failed to initialise Redis pub/sub for SSE after all retries",
                    extra={
                        "error": str(exc),
                        "username": tracking_username,
                        "attempts": REDIS_PUBSUB_MAX_RETRIES,
                    },
                )

    if pubsub is None:
        # All retries exhausted — clean up connection tracking
        if tracking_username and tracking_username in _sse_connections:
            _sse_connections[tracking_username] = [
                (cid, t) for (cid, t) in _sse_connections[tracking_username] if cid != connection_id
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
        ) from last_exc

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for event in _sse_event_generator(
                redis_client, pubsub, git_username, is_admin, connection_id, tracking_username
            ):
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
            # Update active connections gauge on disconnect
            total_connections = sum(len(conns) for conns in _sse_connections.values())
            metrics.sse_connections_active.set(total_connections)
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
