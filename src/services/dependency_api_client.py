from __future__ import annotations

from typing import Any

import httpx

from src.core.config import settings
from src.core.exceptions import DependencyApiException
from src.services.dependency_mock_data import release_info_for
from src.utils.log import get_logger


logger = get_logger(__name__)

REQUEST_TIMEOUT = 15.0

# The dependency database names the ref it was asked about, not `ref`.
TAG_OR_BRANCH_PARAM = "tagOrBranch"


class DependencyApiClient:
    """Reads what an application shipped at one ref.

    One question, one endpoint: the merged answer holds what the application
    declared for its modules and what every package the database knows declared
    for its own dependencies, so nothing here walks a graph. Serving that answer
    is the dependency database's business - this client only asks for it.
    """

    async def get_app_release_info(
        self, app_name: str, tag_or_branch: str
    ) -> dict[str, Any] | None:
        """One application ref, or nothing when the database holds no record.

        The application name is what the record is keyed by, so a repository
        that is not registered (and resolves to ``Unknown``) has no answer.
        """
        if settings.DEPENDENCY_API_MOCK:
            return release_info_for(app_name, tag_or_branch)

        return await self._get(
            settings.DEPENDENCY_API_RELEASE_PATH,
            {"app_name": app_name, TAG_OR_BRANCH_PARAM: tag_or_branch},
        )

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any] | None:
        base = (settings.DEPENDENCY_API_BASE_URL or "").rstrip("/")
        if not base:
            raise DependencyApiException("The dependency database is not configured", path=path)

        url = f"{base}{path}"
        headers: dict[str, str] = {}
        if settings.DEPENDENCY_API_TOKEN:
            headers["Authorization"] = f"Bearer {settings.DEPENDENCY_API_TOKEN}"

        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    url, params=params, headers=headers, timeout=REQUEST_TIMEOUT
                )
        except httpx.HTTPError as e:
            logger.error(
                "Dependency database request failed",
                extra={"url": url, "error": str(e)},
            )
            raise DependencyApiException(str(e), url=url) from e

        if response.status_code == 404:
            return None
        if response.is_error:
            logger.error(
                "Dependency database answered with an error",
                extra={"url": url, "status_code": response.status_code},
            )
            raise DependencyApiException(
                f"Dependency database answered {response.status_code}", url=url
            )
        return response.json()
