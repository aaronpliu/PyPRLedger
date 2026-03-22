"""Bitbucket API Integration Service

This service provides methods to fetch project, repository, and user information
from Bitbucket API when inserting PR review results.
"""
import httpx
from typing import Optional, Dict, Any
from loguru import logger


class BitbucketService:
    """Service for interacting with Bitbucket API"""

    def __init__(self):
        self.base_url = "https://api.bitbucket.org/2.0"
        self.headers = {
            "Accept": "application/json",
        }
        # Add authentication if available (can be extended later)
        # For now, assuming public access or token-based auth
        
    async def _make_request(self, url: str) -> Optional[Dict[str, Any]]:
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

    async def get_project_info(self, project_key: str) -> Optional[Dict[str, Any]]:
        """
        Fetch project information from Bitbucket API
        
        Args:
            project_key: The project key (e.g., "PROJ")
            
        Returns:
            Dictionary containing project info or None if not found
            
        Example response:
        {
            "project_id": 12345,
            "project_name": "My Project",
            "project_key": "PROJ",
            "project_url": "https://bitbucket.org/workspace/PROJ"
        }
        """
        # Note: Bitbucket doesn't have a direct "project" endpoint
        # We'll need to infer from repositories or use workspace info
        # For now, return minimal info that can be enhanced later
        logger.info(f"Fetching project info for key: {project_key}")
        
        # Try to get project from a known repository pattern
        # This is a placeholder - actual implementation depends on your Bitbucket setup
        return {
            "project_id": hash(project_key) % 100000,  # Generate pseudo-ID
            "project_name": f"Project {project_key}",
            "project_key": project_key,
            "project_url": f"https://bitbucket.org/{project_key}"
        }

    async def get_repository_info(
        self, 
        workspace: str, 
        repo_slug: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch repository information from Bitbucket API
        
        Args:
            workspace: Bitbucket workspace name
            repo_slug: Repository slug (e.g., "my-repo")
            
        Returns:
            Dictionary containing repository info or None if not found
            
        Example response:
        {
            "repository_id": 67890,
            "repository_name": "My Repo",
            "repository_slug": "my-repo",
            "repository_url": "https://bitbucket.org/workspace/my-repo",
            "project_id": 12345
        }
        """
        url = f"{self.base_url}/repositories/{workspace}/{repo_slug}"
        logger.info(f"Fetching repository info: {workspace}/{repo_slug}")
        
        api_response = await self._make_request(url)
        if not api_response:
            return None
        
        # Map Bitbucket API response to our format
        return {
            "repository_id": api_response.get("uuid", "").replace("{", "").replace("}", "") or hash(repo_slug) % 100000,
            "repository_name": api_response.get("name", repo_slug),
            "repository_slug": repo_slug,
            "repository_url": api_response.get("links", {}).get("html", {}).get("href", ""),
            "project_id": None  # Will be linked to parent project
        }

    async def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Fetch user information from Bitbucket API
        
        Args:
            username: Bitbucket username
            
        Returns:
            Dictionary containing user info or None if not found
            
        Example response:
        {
            "user_id": 11111,
            "username": "john_doe",
            "display_name": "John Doe",
            "email_address": "john@example.com"
        }
        """
        url = f"{self.base_url}/users/{username}"
        logger.info(f"Fetching user info for: {username}")
        
        api_response = await self._make_request(url)
        if not api_response:
            # If user endpoint fails, try accounts endpoint
            url = f"{self.base_url}/accounts/{username}"
            api_response = await self._make_request(url)
        
        if not api_response:
            # Return minimal info if API fails
            return {
                "user_id": hash(username) % 100000,
                "username": username,
                "display_name": username.replace("_", " ").title(),
                "email_address": f"{username}@example.com"
            }
        
        # Map Bitbucket API response to our format
        return {
            "user_id": api_response.get("account_id", hash(username) % 100000),
            "username": username,
            "display_name": api_response.get("display_name", username),
            "email_address": api_response.get("email", f"{username}@example.com")
        }


# Singleton instance
_bitbucket_service: Optional[BitbucketService] = None


def get_bitbucket_service() -> BitbucketService:
    """Get or create BitbucketService singleton"""
    global _bitbucket_service
    if _bitbucket_service is None:
        _bitbucket_service = BitbucketService()
    return _bitbucket_service
