"""Bitbucket Cloud (bitbucket.org) Git Provider.

Implements BaseGitProvider against the Bitbucket Cloud REST API 2.0:

* base URL: https://api.bitbucket.org/2.0
* workspace == project key, repo slug == repository slug
* commits are listed with ``include`` / ``exclude`` instead of the Server
  ``compare/commits`` endpoint
* pagination uses ``pagelen`` / ``page`` and the ``next`` link
* refs live under ``/refs/tags`` and ``/refs/branches``
"""

from __future__ import annotations

import base64
import hashlib
import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from src.core.config import settings
from src.core.exceptions import GitServiceException, NotFoundException
from src.core.git_provider import GitProvider
from src.services.git_providers.base import BaseGitProvider


logger = logging.getLogger(__name__)

CLOUD_API_URL = "https://api.bitbucket.org/2.0"
MAX_PAGE_LEN = 100


def strip_credentials(url: str | None) -> str | None:
    """Drop the ``user@`` userinfo that Cloud clone links embed.

    Cloud returns clone hrefs such as ``https://alice@bitbucket.org/ws/repo.git``.
    The username adds no value for a stored repository URL and leaks the
    authenticated account, so it is removed.
    """
    if not url:
        return url
    parsed = urlsplit(url)
    if not parsed.username:
        return url
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))


def stable_id(value: str) -> int:
    """Derive a stable numeric id from a Cloud uuid / slug.

    Cloud identifies entities with uuids while the local schema uses integer
    ids, so a deterministic digest keeps ids identical across restarts.
    """
    digest = hashlib.sha256(value.encode()).hexdigest()
    return int(digest[:8], 16) % 100_000_000


def to_epoch_ms(value: str | None) -> int | None:
    """Convert an ISO-8601 timestamp to epoch milliseconds."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp() * 1000)


def author_name(raw_author: str, user: dict[str, Any]) -> str:
    """Best effort display name for a Cloud commit author."""
    name = user.get("display_name") or user.get("nickname")
    if name:
        return name
    return raw_author.split("<")[0].strip() or raw_author


def author_email(raw_author: str, user: dict[str, Any], fallback: str) -> str:
    """Extract the email from a ``Name <email>`` author string."""
    if "<" in raw_author and ">" in raw_author:
        return raw_author.split("<", 1)[1].split(">", 1)[0].strip()
    nickname = user.get("nickname")
    return f"{nickname}@users.noreply.bitbucket.org" if nickname else fallback


class BitbucketCloudProvider(BaseGitProvider):
    """Provider for Bitbucket Cloud (bitbucket.org) REST API 2.0."""

    def __init__(self) -> None:
        base_url = getattr(settings, "BITBUCKET_CLOUD_API_URL", None) or CLOUD_API_URL
        self._base_url = base_url.rstrip("/")
        self._headers: dict[str, str] = {"Accept": "application/json"}

        # Cloud accepts OAuth2 / workspace access tokens as Bearer credentials.
        # Without a token we fall back to Basic auth with an app password.
        token = getattr(settings, "BITBUCKET_CLOUD_TOKEN", None)
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        else:
            # Cloud credentials are separate from Server, so both providers can be
            # used side by side - they fall back to the shared Server credentials.
            user = getattr(settings, "BITBUCKET_CLOUD_USER", None) or getattr(
                settings, "BITBUCKET_USER", None
            )
            password = getattr(settings, "BITBUCKET_CLOUD_APP_PASSWORD", None) or getattr(
                settings, "BITBUCKET_PASSWORD", None
            )
            if user and password:
                credentials = f"{user}:{password}"
                encoded = base64.b64encode(credentials.encode()).decode()
                self._headers["Authorization"] = f"Basic {encoded}"

        if "Authorization" not in self._headers:
            logger.warning(
                "Bitbucket Cloud credentials are not configured - set BITBUCKET_CLOUD_TOKEN "
                "or BITBUCKET_CLOUD_USER + BITBUCKET_CLOUD_APP_PASSWORD, otherwise API calls "
                "fail with 401"
            )
        else:
            mode = "bearer_token" if token else f"basic(user={user})"
            logger.info(f"Bitbucket Cloud provider initialized: auth={mode}, api={self._base_url}")

    @property
    def name(self) -> str:
        return GitProvider.BITBUCKET_CLOUD.value

    async def _request(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """Make a GET request, raising typed exceptions on failure."""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(url, headers=self._headers, params=params, timeout=30.0)
        except httpx.HTTPError as e:
            logger.error(f"Bitbucket Cloud API request failed: {url} - {e}")
            raise GitServiceException(f"Bitbucket Cloud request failed: {e}") from e

        if response.status_code == 404:
            raise NotFoundException(f"Bitbucket Cloud resource not found: {url}")
        if response.status_code in (401, 403):
            raise GitServiceException(
                f"Bitbucket Cloud authentication failed ({response.status_code}) for {url}. "
                "Check BITBUCKET_CLOUD_TOKEN (Bearer) or BITBUCKET_CLOUD_USER + "
                "BITBUCKET_CLOUD_APP_PASSWORD (Atlassian username, not email), the app "
                "password scopes and the workspace membership - Cloud returns 401 both for "
                "invalid credentials and for a workspace the account cannot see."
            )
        if response.status_code >= 400:
            raise GitServiceException(f"Bitbucket Cloud returned {response.status_code} for {url}")

        return response.json()

    async def _request_optional(self, url: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """Fetch a resource, returning None when it is missing or unreachable."""
        try:
            return await self._request(url, params)
        except NotFoundException as e:
            logger.warning(
                f"Bitbucket Cloud resource not found - wrong workspace/slug or the account "
                f"has no access: {url} - {e}"
            )
            return None
        except GitServiceException as e:
            logger.error(f"Bitbucket Cloud lookup failed: {url} - {e}")
            return None

    async def _fetch_paged_values(
        self, url: str, params: dict[str, Any], limit: int
    ) -> list[dict[str, Any]]:
        """Page through a Cloud list endpoint until ``limit`` values are collected."""
        values: list[dict[str, Any]] = []
        page = 1

        while len(values) < limit:
            page_len = min(MAX_PAGE_LEN, limit - len(values))
            payload = await self._request(url, {**params, "pagelen": page_len, "page": page})
            page_values = payload.get("values") or []

            values.extend(page_values)
            if not page_values or not payload.get("next"):
                break
            page += 1

        return values[:limit]

    async def get_project_info(self, project_key: str) -> dict[str, Any] | None:
        """Fetch workspace information (Cloud has no Bitbucket project concept).

        Maps to GET /2.0/workspaces/{workspace}
        """
        url = f"{self._base_url}/workspaces/{project_key}"
        logger.info(f"Fetching workspace info from Bitbucket Cloud: {url}")

        api_response = await self._request_optional(url, {})
        if not api_response:
            return None

        links = api_response.get("links") or {}
        html = links.get("html") or {}
        return {
            "project_id": stable_id(str(api_response.get("uuid") or project_key)),
            "project_name": api_response.get("name") or project_key,
            "project_key": api_response.get("slug") or project_key,
            "project_url": html.get("href") or f"https://bitbucket.org/{project_key}",
            "description": api_response.get("description") or "",
        }

    async def get_repository_info(self, workspace: str, repo_slug: str) -> dict[str, Any] | None:
        """Fetch repository information.

        Maps to GET /2.0/repositories/{workspace}/{repo_slug}
        """
        url = f"{self._base_url}/repositories/{workspace}/{repo_slug}"
        logger.info(f"Fetching repository info from Bitbucket Cloud: {url}")

        api_response = await self._request_optional(url, {})
        if not api_response:
            return None

        links = api_response.get("links") or {}
        html = links.get("html") or {}
        clone = links.get("clone") or []
        https_url = next((link["href"] for link in clone if link.get("name") == "https"), None)
        project = api_response.get("project") or {}

        return {
            "repository_id": stable_id(str(api_response.get("uuid") or repo_slug)),
            "repository_name": api_response.get("name") or repo_slug,
            "repository_slug": api_response.get("slug") or repo_slug,
            "repository_url": strip_credentials(https_url) or html.get("href") or "",
            "project_id": stable_id(str(project.get("uuid") or workspace)) if project else None,
            "description": api_response.get("description") or "",
        }

    async def get_user_info(self, username: str) -> dict[str, Any] | None:
        """Fetch user information.

        Maps to GET /2.0/users/{username} (accepts username, uuid or account_id)
        """
        url = f"{self._base_url}/users/{username}"
        logger.info(f"Fetching user info from Bitbucket Cloud: {url}")

        api_response = await self._request_optional(url, {})
        if not api_response:
            return None

        nickname = api_response.get("nickname") or username

        return {
            "user_id": stable_id(str(api_response.get("uuid") or username)),
            "username": nickname,
            "display_name": api_response.get("display_name") or nickname,
            "email_address": f"{nickname}@users.noreply.bitbucket.org",
            "active": True,
        }

    async def compare_commits(
        self,
        project_key: str,
        repository_slug: str,
        from_ref: str,
        to_ref: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Fetch commits reachable from ``to_ref`` but not from ``from_ref``.

        Cloud has no compare/commits endpoint - ``include`` / ``exclude`` on the
        commits endpoint gives the same result.
        """
        url = f"{self._base_url}/repositories/{project_key}/{repository_slug}/commits"
        logger.info(
            f"Comparing commits on Bitbucket Cloud: {project_key}/{repository_slug} "
            f"({from_ref} -> {to_ref})"
        )
        commits = await self._fetch_paged_values(
            url, {"include": to_ref, "exclude": from_ref}, limit
        )
        return self._as_server_commits(commits)

    async def list_commits_until(
        self,
        project_key: str,
        repository_slug: str,
        until_ref: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Fetch commits reachable from ``until_ref`` (newest first).

        Maps to GET /2.0/repositories/{workspace}/{repo}/commits?include={ref}
        """
        url = f"{self._base_url}/repositories/{project_key}/{repository_slug}/commits"
        logger.info(f"Listing commits on Bitbucket Cloud: {project_key}/{repository_slug}")

        commits = await self._fetch_paged_values(url, {"include": until_ref}, limit)
        return self._as_server_commits(commits)

    async def list_refs(
        self,
        project_key: str,
        repository_slug: str,
        limit: int = 100,
    ) -> dict[str, list[str]]:
        """Fetch tags and branches of a repository.

        Maps to GET /2.0/repositories/{workspace}/{repo}/refs/tags and /refs/branches
        """
        base = f"{self._base_url}/repositories/{project_key}/{repository_slug}/refs"
        logger.info(f"Listing refs on Bitbucket Cloud: {project_key}/{repository_slug}")

        tags = await self._fetch_paged_values(f"{base}/tags", {}, limit)
        branches = await self._fetch_paged_values(f"{base}/branches", {}, limit)

        return {
            "tags": self._ref_names(tags),
            "branches": self._ref_names(branches),
        }

    @staticmethod
    def _ref_names(values: list[dict[str, Any]]) -> list[str]:
        """Extract ref names from Cloud tag / branch payloads."""
        names: list[str] = []
        for value in values:
            name = str(value.get("name") or value.get("displayId") or "").strip()
            if name:
                names.append(name)
        return names

    @staticmethod
    def _as_server_commits(raw_commits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Map Cloud commit payloads to the Bitbucket Server shape.

        The rest of the codebase (and the release diff normalizer) expects the
        Server fields, so the translation happens once here.
        """
        commits: list[dict[str, Any]] = []
        for raw in raw_commits:
            author = raw.get("author") or {}
            user = author.get("user") or {}
            raw_author = author.get("raw") or ""
            links = raw.get("links") or {}
            html = links.get("html") or {}
            commit_hash = raw.get("hash", "")

            commits.append(
                {
                    "id": commit_hash,
                    "author": {
                        "name": author_name(raw_author, user),
                        "emailAddress": author_email(
                            raw_author, user, f"{user.get('nickname') or 'unknown'}@bitbucket.org"
                        ),
                    },
                    "authorTimestamp": to_epoch_ms(raw.get("date")),
                    "message": raw.get("message"),
                    "url": html.get("href"),
                    "parents": raw.get("parents") or [],
                }
            )
        return commits
