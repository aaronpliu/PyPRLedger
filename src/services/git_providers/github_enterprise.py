from __future__ import annotations

import logging
from typing import Any

import httpx

from src.core.config import settings
from src.services.git_providers.base import BaseGitProvider


logger = logging.getLogger(__name__)


class GitHubEnterpriseProvider(BaseGitProvider):
    """GitHub Enterprise provider for fetching project, repository, and user metadata.

    Uses the GitHub Enterprise REST API v3.
    """

    def __init__(self) -> None:
        base_url = getattr(settings, "GITHUB_ENTERPRISE_URL", None)
        if not base_url:
            logger.warning("GITHUB_ENTERPRISE_URL is not configured")
            self.base_url = ""
            self.api_url = ""
        else:
            self.base_url = base_url.rstrip("/")
            self.api_url = f"{self.base_url}/api/v3"

        token = getattr(settings, "GITHUB_ENTERPRISE_TOKEN", None)
        self.headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    @property
    def name(self) -> str:
        return "github_enterprise"

    async def _make_request(self, url: str) -> dict[str, Any] | None:
        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(url, headers=self.headers, timeout=10.0)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"GitHub API request failed: {url} - {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching from GitHub: {e}")
            return None

    async def get_project_info(self, project_key: str) -> dict[str, Any] | None:
        """Fetch GitHub organization or user info, mapped to project concept.

        GitHub doesn't have a 'project' concept like Bitbucket.
        We map the project_key to a GitHub organization or user account.
        """
        url = f"{self.api_url}/orgs/{project_key}"
        logger.info(f"Fetching project info from GitHub: {url}")

        api_response = await self._make_request(url)
        if api_response:
            return {
                "project_id": api_response.get("id", hash(project_key) % 100000),
                "project_name": api_response.get("name") or api_response.get("login", project_key),
                "project_key": project_key,
                "project_url": api_response.get("html_url", f"{self.base_url}/{project_key}"),
                "description": api_response.get("description", ""),
            }

        url = f"{self.api_url}/users/{project_key}"
        logger.info(f"Org not found, trying user: {url}")

        api_response = await self._make_request(url)
        if api_response:
            return {
                "project_id": api_response.get("id", hash(project_key) % 100000),
                "project_name": api_response.get("name") or api_response.get("login", project_key),
                "project_key": project_key,
                "project_url": api_response.get("html_url", f"{self.base_url}/{project_key}"),
                "description": "",
            }

        return None

    async def get_repository_info(self, workspace: str, repo_slug: str) -> dict[str, Any] | None:
        """Fetch repository information from GitHub API.

        Args:
            workspace: GitHub org or user login
            repo_slug: Repository name
        """
        url = f"{self.api_url}/repos/{workspace}/{repo_slug}"
        logger.info(f"Fetching repository info from GitHub: {url}")

        api_response = await self._make_request(url)
        if not api_response:
            return None

        owner = api_response.get("owner", {})
        return {
            "repository_id": api_response.get("id", hash(repo_slug) % 100000),
            "repository_name": api_response.get("name", repo_slug),
            "repository_slug": repo_slug,
            "repository_url": api_response.get("html_url", ""),
            "project_id": owner.get("id"),
            "description": api_response.get("description", ""),
        }

    async def get_user_info(self, username: str) -> dict[str, Any] | None:
        """Fetch user information from GitHub API."""
        url = f"{self.api_url}/users/{username}"
        logger.info(f"Fetching user info from GitHub: {url}")

        api_response = await self._make_request(url)
        if not api_response:
            return None

        return {
            "user_id": api_response.get("id", hash(username) % 100000),
            "username": api_response.get("login", username),
            "display_name": api_response.get("name") or api_response.get("login", username),
            "email_address": api_response.get("email") or f"{username}@github.local",
            "active": True,
        }
