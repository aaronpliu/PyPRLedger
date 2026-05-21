import json
import logging
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
from src.utils.redis import get_redis_client


logger = logging.getLogger(__name__)

router = APIRouter()

# Redis pub/sub channel for review creation events
REVIEW_CREATED_CHANNEL = "reviews:created"

# Global tracking of active SSE connections: {username: set of connection_id}
_sse_connections: dict[str, set[str]] = {}

# Maximum connections per user
MAX_CONNECTIONS_PER_USER = 3


def _is_user_involved_in_review(
    review: dict,
    git_username: str | None,
    is_admin: bool = False,
) -> bool:
    """
    Determine if a user is involved in a review event.

    A user is considered involved if they are:
    - The PR author (pull_request_user)
    - The assigned reviewer (reviewer)
    - The user who assigned the review (assigned_by)

    For admin users without a linked Bitbucket account (git_username=None),
    all reviews are considered relevant.

    Args:
        review: Review event payload from Redis
        git_username: Bitbucket username of the authenticated user (None if not linked)
        is_admin: Whether the user has an admin role (review_admin or system_admin)

    Returns:
        True if user is involved (or admin), False otherwise
    """
    # Admin users without git binding receive all events
    if is_admin and git_username is None:
        return True

    if not git_username:
        return False

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
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE-formatted review events for a connected user.

    Subscribes to the Redis reviews:created channel, filters events by user
    involvement (or admin status), and yields SSE-formatted strings. Cleans up
    the connection tracking set when the generator is closed.

    Args:
        redis_client: Redis client for pub/sub
        pubsub: Pre-initialised Redis pub/sub instance (caller handles errors)
        git_username: Bitbucket username of the connected user (None if not linked)
        is_admin: Whether the user has an admin role (receives all events)
        connection_id: Unique ID for this SSE connection (for tracking)

    Yields:
        SSE-formatted event strings
    """
    # Derive tracking username for connection management
    # Admin without git binding uses a special admin key
    tracking_username = git_username or (f"admin:{connection_id}" if is_admin else None)

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            try:
                review = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse SSE event from Redis: {e}")
                metrics.sse_events_filtered_total.labels(filtered="parse_error").inc()
                continue

            is_involved = _is_user_involved_in_review(review, git_username, is_admin)

            if is_involved:
                minimal_payload = {
                    "review_id": review["review_id"],
                    "project_key": review["project_key"],
                    "repository_slug": review["repository_slug"],
                    "pull_request_id": review["pull_request_id"],
                    "created_date": review["created_date"],
                }
                event_data = json.dumps(minimal_payload)
                yield f"event: review_created\ndata: {event_data}\n\n"
                metrics.sse_events_filtered_total.labels(filtered="false").inc()
            else:
                metrics.sse_events_filtered_total.labels(filtered="true").inc()
    finally:
        await pubsub.unsubscribe(REVIEW_CREATED_CHANNEL)
        await pubsub.close()

        # Clean up connection tracking
        if tracking_username and tracking_username in _sse_connections:
            _sse_connections[tracking_username].discard(connection_id)
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
        - Maximum 3 concurrent SSE connections per user
        - Maximum 500 total SSE connections across all users

    Args:
        token: JWT access token from query parameter

    Returns:
        StreamingResponse with text/event-stream content type

    Raises:
        HTTPException 401: If token is invalid or expired
        HTTPException 403: If user account is inactive
        HTTPException 429: If connection limit exceeded
    """
    redis_client = get_redis_client()
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

    # Enforce per-user connection limit
    user_connections = _sse_connections.get(tracking_username, set())
    if len(user_connections) >= MAX_CONNECTIONS_PER_USER:
        logger.warning(
            "SSE connection limit exceeded",
            extra={
                "username": tracking_username,
                "connection_count": len(user_connections),
                "limit": MAX_CONNECTIONS_PER_USER,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "CONNECTION_LIMIT_EXCEEDED",
                "message": f"Maximum {MAX_CONNECTIONS_PER_USER} concurrent SSE connections per user",
            },
        )

    # Track this connection
    if tracking_username not in _sse_connections:
        _sse_connections[tracking_username] = set()
    _sse_connections[tracking_username].add(connection_id)

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
        },
    )

    # Initialise Redis pub/sub before creating StreamingResponse
    # so that any Redis failure is returned as 503, not a silently broken stream.
    try:
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(REVIEW_CREATED_CHANNEL)
    except Exception as exc:
        logger.error(
            "Failed to initialise Redis pub/sub for SSE",
            extra={"error": str(exc), "username": tracking_username},
        )
        metrics.sse_connections_total.labels(status="redis_failed").inc()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "SSE_UNAVAILABLE",
                "message": "Real-time service temporarily unavailable",
            },
        ) from exc

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for event in _sse_event_generator(
                redis_client, pubsub, git_username, is_admin, connection_id
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
