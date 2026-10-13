"""Confluence Server/Data Center REST client.

The sync needs four calls - find a page by title, read one, create one, update
one - and this module is those calls and nothing else. It treats the page body as
an opaque string, so the markup decisions stay in ``markdown`` and the ordering
stays in ``service``.

Server/Data Center is the target rather than Cloud: it keeps the v1 content API
this uses, and its Personal Access Tokens are sent as a Bearer token, the same
way the Bitbucket Server token in this project already is.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx

from src.core.config import settings
from src.utils.log import get_logger


logger = get_logger(__name__)

CONTENT_PATH = "/rest/api/content"

# Longest failure message worth carrying: the column it is stored in is 512 wide.
MAX_ERROR_LENGTH = 480


class ConfluenceNotConfiguredError(Exception):
    """The integration is not set up, so nothing was attempted."""


class ConfluenceError(Exception):
    """Confluence refused a call, or could not be reached."""


@dataclass(frozen=True)
class ConfluencePage:
    """A page, as much of it as the sync needs."""

    id: str
    title: str
    url: str | None = None
    version: int | None = None
    # The space the page is actually in, which an update has to keep naming: a
    # configured target can be changed long after a page was written.
    space_key: str | None = None


def has_credentials() -> bool:
    """Whether an instance is set up enough for a call to be made at all.

    The space is deliberately not part of this. Which space a release goes to is
    answered per repository (see ``targets``), so it is checked where a target is
    resolved rather than here - a repository with no space anywhere is a failure
    of that repository, not an instance that cannot talk to Confluence.

    Nothing here is required by the application: with these unset, no code path
    reaches Confluence and releasing behaves exactly as it did.
    """
    if not settings.CONFLUENCE_SERVER_BASE_URL:
        return False

    return bool(
        settings.CONFLUENCE_SERVER_TOKEN
        or (settings.CONFLUENCE_SERVER_USERNAME and settings.CONFLUENCE_SERVER_PASSWORD)
    )


def auth_header() -> dict[str, str]:
    """The credential, as a Bearer token when there is one and Basic otherwise."""
    if settings.CONFLUENCE_SERVER_TOKEN:
        return {"Authorization": f"Bearer {settings.CONFLUENCE_SERVER_TOKEN}"}

    user = settings.CONFLUENCE_SERVER_USERNAME or ""
    password = settings.CONFLUENCE_SERVER_PASSWORD or ""
    encoded = base64.b64encode(f"{user}:{password}".encode()).decode()

    return {"Authorization": f"Basic {encoded}"}


class ConfluenceClient:
    """The Confluence calls the release sync makes."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        # A transport is only ever passed by a test, which keeps the calls
        # exercised without an instance behind them.
        # The space is not held here: it is resolved per repository and passed to
        # each call, so one client serves every project of the instance.
        self._transport = transport
        self._base_url = (settings.CONFLUENCE_SERVER_BASE_URL or "").rstrip("/")

    async def find_page(self, title: str, space_key: str) -> ConfluencePage | None:
        """The page with this title in the space, or None when there is none.

        Titles are unique within a space, so this is the lookup that makes a sync
        repeatable: a page created by an earlier attempt is found again rather
        than duplicated.
        """
        payload = await self._request(
            "GET",
            CONTENT_PATH,
            params={"spaceKey": space_key, "title": title, "expand": "version,space"},
        )
        results = (payload or {}).get("results") or []

        return self._page(results[0]) if results else None

    async def get_page(self, page_id: str) -> ConfluencePage:
        """The page with this id, which is how the version to update is read."""
        payload = await self._request(
            "GET", f"{CONTENT_PATH}/{page_id}", params={"expand": "version,space"}
        )
        if not payload:
            raise ConfluenceError(f"Confluence returned no page for id {page_id}")

        return self._page(payload)

    async def create_page(
        self, title: str, body: str, space_key: str, parent_id: str | None = None
    ) -> ConfluencePage:
        """A new page holding the notes.

        The parent page is only ever used here: it decides where the page sits at
        the moment it comes into being. Moving a page afterwards is a call this
        client does not make.
        """
        payload: dict[str, Any] = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {"storage": {"value": body, "representation": "storage"}},
        }
        if parent_id:
            payload["ancestors"] = [{"id": parent_id}]

        created = await self._request("POST", CONTENT_PATH, json=payload)
        if not created:
            raise ConfluenceError("Confluence returned no page after creating one")

        return self._page(created)

    async def update_page(
        self, page: ConfluencePage, title: str, body: str, space_key: str
    ) -> ConfluencePage:
        """The existing page, with the notes as they now read.

        The space named is the page's own rather than the one the target now
        resolves to. A page already written stays where it is - Confluence refuses
        an update that says it lives somewhere else - so changing a configured
        space moves what is written from then on, not what is there.
        """
        payload = {
            "id": page.id,
            "type": "page",
            "title": title,
            "space": {"key": page.space_key or space_key},
            "body": {"storage": {"value": body, "representation": "storage"}},
            # Confluence refuses an update that does not move the version on.
            "version": {"number": (page.version or 0) + 1},
        }

        updated = await self._request("PUT", f"{CONTENT_PATH}/{page.id}", json=payload)
        if not updated:
            raise ConfluenceError(f"Confluence returned no page after updating {page.id}")

        return self._page(updated)

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any] | None:
        url = f"{self._base_url}{path}"
        headers = {**auth_header(), "Accept": "application/json"}

        try:
            async with httpx.AsyncClient(
                verify=settings.CONFLUENCE_SERVER_VERIFY_SSL,
                timeout=settings.CONFLUENCE_SERVER_TIMEOUT_SECONDS,
                transport=self._transport,
            ) as client:
                response = await client.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as e:
            raise ConfluenceError(f"Confluence could not be reached: {e}") from e

        if response.status_code >= 400:
            detail = (response.text or response.reason_phrase or "").strip()
            raise ConfluenceError(f"Confluence returned {response.status_code}: {detail[:200]}")

        if not response.content:
            return None

        try:
            return response.json()
        except ValueError as e:
            raise ConfluenceError(f"Confluence returned a body that is not JSON: {e}") from e

    def _page(self, payload: dict[str, Any]) -> ConfluencePage:
        links = payload.get("_links") or {}
        webui = links.get("webui")
        url = None
        if webui:
            # `webui` is relative to the instance, and `base` carries the context
            # path the instance may sit under, so it is preferred over the
            # configured URL - which would double that path where there is one.
            base = links.get("base") or self._base_url
            url = webui if webui.startswith("http") else urljoin(f"{base}/", webui.lstrip("/"))

        return ConfluencePage(
            id=str(payload.get("id") or ""),
            title=payload.get("title") or "",
            url=url,
            version=(payload.get("version") or {}).get("number"),
            space_key=(payload.get("space") or {}).get("key") or None,
        )
