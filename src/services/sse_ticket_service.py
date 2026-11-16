"""Short-lived, single-use tickets for EventSource connections.

``EventSource`` cannot send an Authorization header, so the stream used to take
the JWT in the query string - where it lands in browser history, proxy access
logs and Referer headers. Instead the client asks for a ticket over an
authenticated request and passes that: it lives for a minute, works once and is
worthless if it leaks.
"""

from __future__ import annotations

import secrets

from src.utils.redis import get_redis_client


class SSETicketService:
    """Issue and consume one-shot tickets bound to a user id."""

    TICKET_PREFIX = "auth:sse_ticket"
    TICKET_TTL_SECONDS = 60

    def __init__(self, redis_client=None):
        self.redis_client = redis_client or get_redis_client()

    @classmethod
    def _key(cls, ticket: str) -> str:
        return f"{cls.TICKET_PREFIX}:{ticket}"

    async def issue(self, user_id: int) -> str:
        """Create a ticket for this user, valid for TICKET_TTL_SECONDS."""
        ticket = secrets.token_urlsafe(32)
        await self.redis_client.setex(self._key(ticket), self.TICKET_TTL_SECONDS, str(user_id))
        return ticket

    async def consume(self, ticket: str) -> int | None:
        """Return the user id for a ticket and burn it.

        Returns None when the ticket is unknown, expired or was already used.
        """
        if not ticket:
            return None

        key = self._key(ticket)
        value = await self.redis_client.get(key)
        if value is None:
            return None

        # Delete first: a replayed ticket must not find a live value.
        await self.redis_client.delete(key)

        try:
            return int(value)
        except (TypeError, ValueError):
            return None
