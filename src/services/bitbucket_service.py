"""Bitbucket API Integration Service

This service provides methods to fetch project, repository, and user information
from Bitbucket API when inserting PR review results.

Supports both Bitbucket Cloud and Bitbucket Server (Data Center).
"""

import logging
from typing import Any

import httpx

from src.core.config import settings


logger = logging.getLogger(__name__)


class BitbucketService:
    """Service for interacting with Bitbucket API"""

    def __init__(self):
        # Support both Cloud and Server versions
        self.is_cloud = getattr(settings, "BITBUCKET_CLOUD", False)

        if self.is_cloud:
            self.base_url = "https://api.bitbucket.org/2.0"
            self.headers = {
                "Accept": "application/json",
            }
        else:
            # Bitbucket Server/Data Center
            base_url = getattr(settings, "BITBUCKET_SERVER_URL", "http://localhost:7990")
            self.base_url = f"{base_url}/rest/api/latest"
            self.headers = {
                "Accept": "application/json",
            }
            # Add authentication for Server if provided
            bitbucket_user = getattr(settings, "BITBUCKET_USER", None)
            bitbucket_password = getattr(settings, "BITBUCKET_PASSWORD", None)
            if bitbucket_user and bitbucket_password:
                import base64

                credentials = f"{bitbucket_user}:{bitbucket_password}"
                encoded = base64.b64encode(credentials.encode()).decode()
                self.headers["Authorization"] = f"Basic {encoded}"

    async def _make_request(self, url: str) -> dict[str, Any] | None:
        """Make HTTP request to Bitbucket API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, timeout=10.0)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Bitbucket API request failed: {url} - {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching from Bitbucket: {str(e)}")
            return None

    async def get_project_info(self, project_key: str) -> dict[str, Any] | None:
        """
        Fetch project information from Bitbucket API

        Args:
            project_key: The project key (e.g., "PROJ")

        Returns:
            Dictionary containing project info or None if not found

        Bitbucket Server API Response:
        {
            "key": "PROJ",
            "name": "My Project",
            "description": "Project description",
            "public": false,
            "links": {
                "self": [{"href": "http://host:port/projects/PROJ"}]
            }
        }
        """
        if self.is_cloud:
            # Cloud version - use workspace-based URL
            logger.info(f"Fetching project info from Cloud: {project_key}")
            # Note: Bitbucket Cloud doesn't have a direct project endpoint
            # Return minimal info as fallback
            return {
                "project_id": hash(project_key) % 100000,
                "project_name": f"Project {project_key}",
                "project_key": project_key,
                "project_url": f"https://bitbucket.org/{project_key}",
            }
        else:
            # Server version - use REST API
            url = f"{self.base_url}/projects/{project_key}"
            logger.info(f"Fetching project info from Server: {url}")

            api_response = await self._make_request(url)
            if not api_response:
                # Fallback to minimal info if API fails
                return {
                    "project_id": hash(project_key) % 100000,
                    "project_name": f"Project {project_key}",
                    "project_key": project_key,
                    "project_url": f"{self.base_url}/projects/{project_key}",
                }

            # Map Bitbucket Server API response to our format
            links = api_response.get("links", {})
            self_links = links.get("self", [])
            project_url = (
                self_links[0]["href"] if self_links else f"{self.base_url}/projects/{project_key}"
            )

            return {
                "project_id": api_response.get("id", hash(project_key) % 100000),
                "project_name": api_response.get("name", project_key),
                "project_key": api_response.get("key", project_key),
                "project_url": project_url,
                "description": api_response.get("description", ""),
            }

    async def get_repository_info(self, workspace: str, repo_slug: str) -> dict[str, Any] | None:
        """
        Fetch repository information from Bitbucket API

        Args:
            workspace: Bitbucket workspace name (Cloud) or project key (Server)
            repo_slug: Repository slug (e.g., "my-repo")

        Returns:
            Dictionary containing repository info or None if not found

        Bitbucket Server API Response:
        {
            "slug": "my-repo",
            "name": "My Repo",
            "description": "Repository description",
            "public": false,
            "project": {
                "key": "PROJ",
                "name": "My Project"
            },
            "links": {
                "self": [{"href": "..."}],
                "clone": [{"href": "...", "name": "http"}, ...]
            }
        }
        """
        if self.is_cloud:
            # Cloud version
            url = f"{self.base_url}/repositories/{workspace}/{repo_slug}"
            logger.info(f"Fetching repository info from Cloud: {workspace}/{repo_slug}")

            api_response = await self._make_request(url)
            if not api_response:
                return None

            # Map Cloud API response
            links = api_response.get("links", {})
            html_link = links.get("html", {}).get("href", "")

            return {
                "repository_id": api_response.get("uuid", "").replace("{", "").replace("}", "")
                or hash(repo_slug) % 100000,
                "repository_name": api_response.get("name", repo_slug),
                "repository_slug": repo_slug,
                "repository_url": html_link,
                "project_id": None,
            }
        else:
            # Server version - use project key + repo slug
            url = f"{self.base_url}/projects/{workspace}/repos/{repo_slug}"
            logger.info(f"Fetching repository info from Server: {url}")

            api_response = await self._make_request(url)
            if not api_response:
                # Fallback to minimal info
                return {
                    "repository_id": hash(repo_slug) % 100000,
                    "repository_name": repo_slug,
                    "repository_slug": repo_slug,
                    "repository_url": f"{self.base_url}/projects/{workspace}/repos/{repo_slug}",
                    "project_id": None,
                }

            # Map Server API response
            links = api_response.get("links", {})
            self_links = links.get("self", [])
            clone_links = links.get("clone", [])

            # Prefer HTTPS clone URL
            https_url = next(
                (link["href"] for link in clone_links if link.get("name") == "https"), None
            )
            http_url = next(
                (link["href"] for link in clone_links if link.get("name") == "http"), None
            )
            repository_url = https_url or http_url or (self_links[0]["href"] if self_links else "")

            # Get project info if available
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
        """
        Fetch user information from Bitbucket API

        Args:
            username: Bitbucket username

        Returns:
            Dictionary containing user info or None if not found
        """
        if self.is_cloud:
            # Cloud version
            url = f"{self.base_url}/users/{username}"
            logger.info(f"Fetching user info from Cloud: {username}")

            api_response = await self._make_request(url)
            if not api_response:
                # Try accounts endpoint as fallback
                url = f"{self.base_url}/accounts/{username}"
                api_response = await self._make_request(url)

            if not api_response:
                # Return minimal info if API fails
                return {
                    "user_id": hash(username) % 100000,
                    "username": username,
                    "display_name": username.replace("_", " ").title(),
                    "email_address": f"{username}@example.com",
                }

            # Map Cloud API response
            return {
                "user_id": api_response.get("account_id", hash(username) % 100000),
                "username": username,
                "display_name": api_response.get("display_name", username),
                "email_address": api_response.get("email", f"{username}@example.com"),
            }
        else:
            # Server version
            url = f"{self.base_url}/users/{username}"
            logger.info(f"Fetching user info from Server: {url}")

            api_response = await self._make_request(url)
            if not api_response:
                # Return minimal info if API fails
                return {
                    "user_id": hash(username) % 100000,
                    "username": username,
                    "display_name": username.replace("_", " ").title(),
                    "email_address": f"{username}@example.com",
                }

            # Map Server API response
            return {
                "user_id": api_response.get("id", hash(username) % 100000),
                "username": api_response.get("name", username),
                "display_name": api_response.get("displayName", username),
                "email_address": api_response.get("emailAddress", f"{username}@example.com"),
                "active": api_response.get("active", True),
            }


# Singleton instance
_bitbucket_service: BitbucketService | None = None


def get_bitbucket_service() -> BitbucketService:
    """Get or create BitbucketService singleton"""
    global _bitbucket_service
    if _bitbucket_service is None:
        _bitbucket_service = BitbucketService()
    return _bitbucket_service
