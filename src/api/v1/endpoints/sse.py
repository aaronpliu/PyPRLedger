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


def _is_user_involved_in_review(review: dict, username: str) -> bool:
    """
    Determine if a user is involved in a review event.

    A user is considered involved if they are:
    - The PR author (pull_request_user)
    - The assigned reviewer (reviewer)
    - The user who assigned the review (assigned_by)

    Args:
        review: Review event payload from Redis
        username: Bitbucket username of the authenticated user

    Returns:
        True if user is involved, False otherwise
    """
    if review.get("pull_request_user") == username:
        return True
    if review.get("reviewer") == username:
        return True
    return review.get("assigned_by") == username


async def _sse_event_generator(
    redis_client,
    pubsub,
    git_username: str,
    connection_id: str,
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE-formatted review events for a connected user.

    Subscribes to the Redis reviews:created channel, filters events by user
    involvement, and yields SSE-formatted strings. Cleans up the connection
    tracking set when the generator is closed.

    Args:
        redis_client: Redis client for pub/sub
        pubsub: Pre-initialised Redis pub/sub instance (caller handles errors)
        git_username: Bitbucket username of the connected user (for filtering)
        connection_id: Unique ID for this SSE connection (for tracking)

    Yields:
        SSE-formatted event strings
    """
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

            is_involved = _is_user_involved_in_review(review, git_username)

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
        if git_username in _sse_connections:
            _sse_connections[git_username].discard(connection_id)
            if not _sse_connections[git_username]:
                del _sse_connections[git_username]


@router.get("/stream")
async def stream_reviews(
    token: Annotated[str, Query(description="JWT access token for SSE authentication")],
) -> StreamingResponse:
    """
    Server-Sent Events (SSE) endpoint for real-time new review notifications.

    Establishes a persistent connection that streams review creation events
    to the authenticated user. Only events where the user is involved
    (reviewer, assigner, or PR author) are forwarded.

    Authentication:
        JWT token passed as query parameter: ?token=<JWT>

    Connection limits:
        - Maximum 3 concurrent SSE connections per user
        - Maximum 500 total SSE connections across all users

    Args:
        token: JWT access token from query parameter

    Returns:
        StreamingResponse with text/event-stream content type

    Raises:
        HTTPException 401: If token is invalid or expired
        HTTPException 403: If user has no linked Bitbucket account
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

        # Get Bitbucket username for filtering and connection tracking
        stmt = select(User).where(User.id == auth_user.user_id)
        result = await db.execute(stmt)
        git_user = result.scalar_one_or_none()

        if not git_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "NO_BITBUCKET_ACCOUNT",
                    "message": "No linked Bitbucket account found for this user",
                },
            )

        git_username = git_user.username

    # Enforce per-user connection limit
    user_connections = _sse_connections.get(git_username, set())
    if len(user_connections) >= MAX_CONNECTIONS_PER_USER:
        logger.warning(
            "SSE connection limit exceeded",
            extra={
                "username": git_username,
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
    if git_username not in _sse_connections:
        _sse_connections[git_username] = set()
    _sse_connections[git_username].add(connection_id)

    # Update active connections gauge
    total_connections = sum(len(conns) for conns in _sse_connections.values())
    metrics.sse_connections_active.set(total_connections)
    metrics.sse_connections_total.labels(status="connected").inc()

    logger.info(
        "SSE connection established",
        extra={
            "user_id": auth_user.id,
            "username": git_username,
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
            extra={"error": str(exc), "username": git_username},
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
                redis_client, pubsub, git_username, connection_id
            ):
                yield event
        except Exception as e:
            logger.error(
                "SSE stream error",
                extra={
                    "user_id": auth_user.id,
                    "username": git_username,
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
                    "username": git_username,
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
