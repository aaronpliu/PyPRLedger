"""Bitbucket Server / Data Center Git Provider

Implements BaseGitProvider for Bitbucket Server (and Data Center) REST API.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from src.core.config import settings
from src.core.git_provider import GitProvider
from src.services.git_providers.base import BaseGitProvider


logger = logging.getLogger(__name__)


class BitbucketServerProvider(BaseGitProvider):
    """Provider for Bitbucket Server / Data Center REST API."""

    def __init__(self) -> None:
        base_url = getattr(settings, "BITBUCKET_SERVER_URL", "http://localhost:7990")
        self._base_url = f"{base_url}/rest/api/latest"
        self._headers: dict[str, str] = {"Accept": "application/json"}

        # Prefer a Personal Access Token (Bitbucket Server/Data Center) as Bearer auth.
        # Fall back to Basic auth (username + password/app password) when no token is set.
        token = getattr(settings, "BITBUCKET_TOKEN", None)
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        else:
            user = getattr(settings, "BITBUCKET_USER", None)
            password = getattr(settings, "BITBUCKET_PASSWORD", None)
            if user and password:
                credentials = f"{user}:{password}"
                encoded = base64.b64encode(credentials.encode()).decode()
                self._headers["Authorization"] = f"Basic {encoded}"

    @property
    def name(self) -> str:
        return GitProvider.BITBUCKET_SERVER.value

    async def _make_request(self, url: str) -> dict[str, Any] | None:
        """Make HTTP request to Bitbucket Server API."""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(url, headers=self._headers, timeout=10.0)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Bitbucket API request failed: {url} - {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching from Bitbucket: {e}")
            return None

    async def get_project_info(self, project_key: str) -> dict[str, Any] | None:
        """Fetch project information from Bitbucket Server API.

        Expected API response:
        {
            "id": 1, "key": "PROJ", "name": "My Project",
            "description": "...", "public": false,
            "links": {"self": [{"href": "http://host:port/projects/PROJ"}]}
        }
        """
        url = f"{self._base_url}/projects/{project_key}"
        logger.info(f"Fetching project info from Bitbucket Server: {url}")

        api_response = await self._make_request(url)
        if not api_response:
            return None

        links = api_response.get("links", {})
        self_links = links.get("self", [])
        project_url = (
            self_links[0]["href"] if self_links else f"{self._base_url}/projects/{project_key}"
        )

        return {
            "project_id": api_response.get("id", hash(project_key) % 100000),
            "project_name": api_response.get("name", project_key),
            "project_key": api_response.get("key", project_key),
            "project_url": project_url,
            "description": api_response.get("description", ""),
        }

    async def get_repository_info(self, workspace: str, repo_slug: str) -> dict[str, Any] | None:
        """Fetch repository information from Bitbucket Server API.

        Expected API response:
        {
            "id": 1, "slug": "my-repo", "name": "My Repo", "description": "...",
            "project": {"key": "PROJ", "name": "My Project", "id": 1},
            "links": {
                "self": [{"href": "..."}],
                "clone": [{"href": "...", "name": "http"}, ...]
            }
        }
        """
        url = f"{self._base_url}/projects/{workspace}/repos/{repo_slug}"
        logger.info(f"Fetching repository info from Bitbucket Server: {url}")

        api_response = await self._make_request(url)
        if not api_response:
            return None

        links = api_response.get("links", {})
        self_links = links.get("self", [])
        clone_links = links.get("clone", [])

        https_url = next(
            (link["href"] for link in clone_links if link.get("name") == "https"), None
        )
        http_url = next((link["href"] for link in clone_links if link.get("name") == "http"), None)
        repository_url = https_url or http_url or (self_links[0]["href"] if self_links else "")

        project = api_response.get("project", {})
        project_id = project.get("id", hash(workspace) % 100000) if project else None

        return {
            "repository_id": api_response.get("id", hash(repo_slug) % 100000),
            "repository_name": api_response.get("name", repo_slug),
            "repository_slug": repo_slug,
            "repository_url": repository_url,
            "project_id": project_id,
            "description": api_response.get("description", ""),
        }

    async def get_user_info(self, username: str) -> dict[str, Any] | None:
        """Fetch user information from Bitbucket Server API.

        Expected API response:
        {
            "id": 1, "name": "jdoe", "displayName": "John Doe",
            "emailAddress": "jdoe@example.com", "active": true
        }
        """
        url = f"{self._base_url}/users/{username}"
        logger.info(f"Fetching user info from Bitbucket Server: {url}")

        api_response = await self._make_request(url)
        if not api_response:
            return None

        return {
            "user_id": api_response.get("id", hash(username) % 100000),
            "username": api_response.get("name", username),
            "display_name": api_response.get("displayName", username),
            "email_address": api_response.get("emailAddress", f"{username}@example.com"),
            "active": api_response.get("active", True),
        }
