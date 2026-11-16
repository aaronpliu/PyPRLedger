from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random
import time
from dataclasses import dataclass, field

from redis.asyncio.client import PubSub

from src.utils.metrics import metrics
from src.utils.redis import get_redis_pubsub_client


logger = logging.getLogger(__name__)

REVIEW_CREATED_CHANNEL = "reviews:created"
# Notifications ride the same pubsub connection but on their own channel so the
# review pipeline keeps its semantics: notifications are per-user, reviews are
# per-repository-grant.
NOTIFICATION_CHANNEL = "notifications:events"

SUBSCRIBED_CHANNELS = (REVIEW_CREATED_CHANNEL, NOTIFICATION_CHANNEL)

DISPATCHER_POLL_TIMEOUT = 1.0
HEARTBEAT_INTERVAL = 30
QUEUE_MAX_SIZE = 50

RECONNECT_BASE_DELAY = 1.0
RECONNECT_MAX_DELAY = 30.0


@dataclass
class SSEClient:
    client_id: str
    git_username: str | None
    is_admin: bool
    allowed_pairs: set[tuple[str, str]] | None = None
    # Identifiers the notification publisher may address this user by: the auth
    # username (what the /notifications endpoints key on) and the linked git
    # username (what assignment code passes when it creates notifications).
    notification_user_ids: frozenset[str] = frozenset()
    queue: asyncio.Queue[str | None] = field(
        default_factory=lambda: asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
    )
    connected_at: float = field(default_factory=time.monotonic)


def _reader_may_see_review(
    review: dict,
    allowed_pairs: set[tuple[str, str]] | None = None,
) -> bool:
    """Whether a review belongs in this reader's list.

    Access to the repository is the whole test, not involvement: the list page
    shows every review in the repositories a reader is granted, so a review that
    lands in one of them changes what is on screen even when the reader is
    neither its author nor its assignee - the normal case for a reviewer admin,
    whose grants usually cover more repositories than the rest of the team.
    """
    if allowed_pairs is None:
        return True
    return (review.get("project_key"), review.get("repository_slug")) in allowed_pairs


class SSEBroker:
    """
    Singleton that multiplexes a single Redis pubsub subscription
    across all SSE clients.

    Instead of each SSE connection holding its own Redis pubsub subscription
    (which exhausts the connection pool at scale), the broker:
    1. Maintains exactly 1 Redis pubsub subscription
    2. Dispatches incoming events to per-client asyncio.Queues
    3. Filters events per client based on involvement rules

    This supports unlimited concurrent SSE clients using only 1 Redis connection.
    """

    _instance: SSEBroker | None = None

    def __new__(cls) -> SSEBroker:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._clients: dict[str, SSEClient] = {}
        self._pubsub: PubSub | None = None
        self._dispatch_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._running = False

    async def start(self) -> None:
        async with self._lock:
            if self._running:
                return
            self._running = True

            await self._connect_pubsub()

            self._dispatch_task = asyncio.create_task(self._dispatch_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            logger.info("SSEBroker started — single pubsub subscription shared across all clients")

    async def _connect_pubsub(self) -> None:
        """Create a fresh pubsub subscription to Redis."""
        redis_client = get_redis_pubsub_client()
        self._pubsub = redis_client.pubsub()
        await self._pubsub.subscribe(*SUBSCRIBED_CHANNELS)
        logger.info("SSEBroker pubsub subscription established")

    async def stop(self) -> None:
        async with self._lock:
            if not self._running:
                return
            self._running = False

            if self._dispatch_task and not self._dispatch_task.done():
                self._dispatch_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._dispatch_task
                self._dispatch_task = None

            if self._heartbeat_task and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._heartbeat_task
                self._heartbeat_task = None

            if self._pubsub:
                with contextlib.suppress(Exception):
                    await self._pubsub.unsubscribe(*SUBSCRIBED_CHANNELS)
                    await self._pubsub.close()
                self._pubsub = None

            # Signal all remaining clients to disconnect
            for client in self._clients.values():
                with contextlib.suppress(asyncio.QueueFull):
                    client.queue.put_nowait(None)
            self._clients.clear()

            logger.info("SSEBroker stopped")

    async def register(
        self,
        client_id: str,
        git_username: str | None,
        is_admin: bool,
        allowed_pairs: set[tuple[str, str]] | None = None,
        notification_user_ids: frozenset[str] | None = None,
    ) -> asyncio.Queue[str | None]:
        await self.start()

        client = SSEClient(
            client_id=client_id,
            git_username=git_username,
            is_admin=is_admin,
            allowed_pairs=allowed_pairs,
            notification_user_ids=notification_user_ids or frozenset(),
        )
        self._clients[client_id] = client

        total = len(self._clients)
        metrics.sse_connections_active.set(total)
        logger.info(
            "SSEBroker client registered",
            extra={
                "client_id": client_id,
                "git_username": git_username,
                "is_admin": is_admin,
                "total_clients": total,
            },
        )

        return client.queue

    async def unregister(self, client_id: str) -> None:
        self._clients.pop(client_id, None)

        total = len(self._clients)
        metrics.sse_connections_active.set(total)
        logger.debug(
            "SSEBroker client unregistered",
            extra={"client_id": client_id, "total_clients": total},
        )

        if total == 0 and self._running:
            logger.info("No SSE clients remaining — stopping broker to free Redis connection")
            await self.stop()

    def disconnect_client(self, client_id: str) -> bool:
        """Signal one client's stream to end.

        The stream generator treats ``None`` as disconnect and unregisters the
        client in its ``finally`` block, so no cleanup happens here.
        """
        client = self._clients.get(client_id)
        if client is None:
            return False
        with contextlib.suppress(asyncio.QueueFull):
            if client.queue.full():
                client.queue.get_nowait()
            client.queue.put_nowait(None)
        logger.info(
            "SSEBroker client disconnect signalled",
            extra={"client_id": client_id},
        )
        return True

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def is_healthy(self) -> bool:
        """Check if the broker is running and dispatch loop is alive."""
        return self._running and self._dispatch_task is not None and not self._dispatch_task.done()

    async def _dispatch_loop(self) -> None:
        consecutive_errors = 0
        try:
            while self._running:
                if not self._pubsub:
                    await self._attempt_reconnect(consecutive_errors)
                    consecutive_errors = 0
                    continue

                try:
                    message = await self._pubsub.get_message(timeout=DISPATCHER_POLL_TIMEOUT)
                    consecutive_errors = 0
                except Exception as exc:
                    consecutive_errors += 1
                    logger.warning(
                        f"SSEBroker pubsub read error (attempt {consecutive_errors}): {exc}"
                    )
                    await self._cleanup_pubsub()
                    await self._attempt_reconnect(consecutive_errors)
                    continue

                if not message or message["type"] != "message":
                    continue

                if message["channel"] == NOTIFICATION_CHANNEL:
                    await self._dispatch_notification(message["data"])
                    continue

                try:
                    review = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError) as exc:
                    logger.warning(f"SSEBroker failed to parse event: {exc}")
                    metrics.sse_events_filtered_total.labels(filtered="parse_error").inc()
                    continue

                await self._fan_out(review)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.error("SSEBroker dispatch loop crashed", exc_info=True)

    async def _attempt_reconnect(self, attempt: int) -> None:
        """Reconnect to Redis pubsub with exponential backoff."""
        delay = min(RECONNECT_BASE_DELAY * (2 ** min(attempt, 7)), RECONNECT_MAX_DELAY)
        jitter = delay * 0.2 * (2 * random.random() - 1)
        delay = max(0.1, delay + jitter)

        logger.info(f"SSEBroker reconnecting to Redis in {delay:.1f}s (attempt {attempt + 1})")
        await asyncio.sleep(delay)

        if not self._running:
            return

        try:
            await self._connect_pubsub()
            logger.info("SSEBroker reconnected to Redis successfully")
        except Exception as exc:
            logger.warning(f"SSEBroker reconnection failed: {exc}")

    async def _cleanup_pubsub(self) -> None:
        """Safely close the current pubsub connection."""
        if self._pubsub:
            with contextlib.suppress(Exception):
                await self._pubsub.unsubscribe(*SUBSCRIBED_CHANNELS)
                await self._pubsub.close()
            self._pubsub = None

    async def _fan_out(self, review: dict) -> None:
        minimal_payload = {
            "review_id": review["review_id"],
            "project_key": review["project_key"],
            "repository_slug": review["repository_slug"],
            "pull_request_id": review["pull_request_id"],
            "created_date": review["created_date"],
        }
        # The publisher names the event (review_created / review_updated); the
        # frame has to carry that name, else the browser fires the wrong one.
        event_name = review.get("event") or "review_created"
        event_str = f"event: {event_name}\ndata: {json.dumps(minimal_payload)}\n\n"

        for client in list(self._clients.values()):
            if _reader_may_see_review(review, client.allowed_pairs):
                try:
                    client.queue.put_nowait(event_str)
                    metrics.sse_events_filtered_total.labels(filtered="false").inc()
                    logger.debug(
                        "SSEBroker dispatched event to client",
                        extra={
                            "client_id": client.client_id,
                            "review_id": review.get("review_id"),
                        },
                    )
                except asyncio.QueueFull:
                    self._drop_slow_consumer(client)
            else:
                metrics.sse_events_filtered_total.labels(filtered="true").inc()

    def _drop_slow_consumer(self, client: SSEClient) -> None:
        """End the stream of a consumer that cannot keep up.

        Silently dropping frames would leave the client connected but stale
        forever — worse than a short blip. Signalling the stream to end makes
        the browser reconnect, refetch and resync; one pending frame is
        sacrificed to make room for the disconnect signal.
        """
        with contextlib.suppress(asyncio.QueueFull):
            if client.queue.full():
                client.queue.get_nowait()
            client.queue.put_nowait(None)
        metrics.sse_events_filtered_total.labels(filtered="slow_consumer").inc()
        logger.warning(
            "SSEBroker client queue full — closing stream to force a resync",
            extra={"client_id": client.client_id},
        )

    async def _dispatch_notification(self, raw_data: str | bytes) -> None:
        """Parse a notification pubsub payload and deliver it to its user."""
        try:
            payload = json.loads(raw_data)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning(f"SSEBroker failed to parse notification event: {exc}")
            metrics.sse_events_filtered_total.labels(filtered="notification_parse_error").inc()
            return

        if not isinstance(payload, dict) or not isinstance(payload.get("user_id"), str):
            logger.warning("SSEBroker dropping notification event without a user_id")
            metrics.sse_events_filtered_total.labels(filtered="notification_parse_error").inc()
            return

        event_str = f"event: notification\ndata: {json.dumps(payload)}\n\n"
        delivered = False
        for client in list(self._clients.values()):
            if payload["user_id"] in client.notification_user_ids:
                try:
                    client.queue.put_nowait(event_str)
                    delivered = True
                except asyncio.QueueFull:
                    self._drop_slow_consumer(client)
        metrics.sse_events_filtered_total.labels(
            filtered="notification_delivered" if delivered else "notification_no_recipient"
        ).inc()

    async def _heartbeat_loop(self) -> None:
        try:
            while self._running:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                heartbeat = ": heartbeat\n\n"
                for client in list(self._clients.values()):
                    with contextlib.suppress(asyncio.QueueFull):
                        client.queue.put_nowait(heartbeat)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.error("SSEBroker heartbeat loop crashed", exc_info=True)


def get_sse_broker() -> SSEBroker:
    return SSEBroker()
