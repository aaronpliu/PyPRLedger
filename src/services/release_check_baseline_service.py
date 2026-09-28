"""Read / write access to the release check baseline of a repository.

The baseline belongs to a repository (provider + project + slug), not to a user:
the per-build merge check is a routine, and everyone running it should narrow the
check the same way.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.release_check_baseline import ReleaseCheckBaseline
from src.utils.log import get_logger


logger = get_logger(__name__)


class ReleaseCheckBaselineService:
    """Baseline ref of a repository, used by the release missing check."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _normalize(project_key: str) -> str:
        """Normalize the business key so casing cannot create a second baseline."""
        return project_key.strip().upper()

    async def get(
        self,
        *,
        git_provider: str,
        project_key: str,
        repository_slug: str,
    ) -> ReleaseCheckBaseline | None:
        """Return the stored baseline of a repository, or None."""
        statement = select(ReleaseCheckBaseline).where(
            ReleaseCheckBaseline.git_provider == git_provider,
            ReleaseCheckBaseline.project_key == self._normalize(project_key),
            ReleaseCheckBaseline.repository_slug == repository_slug.strip(),
        )
        return (await self.db.execute(statement)).scalar_one_or_none()

    async def get_ref(
        self,
        *,
        git_provider: str,
        project_key: str,
        repository_slug: str,
    ) -> str | None:
        """Return just the baseline ref, which is all the check needs."""
        baseline = await self.get(
            git_provider=git_provider,
            project_key=project_key,
            repository_slug=repository_slug,
        )
        return baseline.baseline_ref if baseline else None

    async def save(
        self,
        *,
        git_provider: str,
        project_key: str,
        repository_slug: str,
        baseline_ref: str,
        note: str | None = None,
        updated_by: str | None = None,
    ) -> ReleaseCheckBaseline:
        """Store (or replace) the baseline of a repository."""
        normalized_key = self._normalize(project_key)
        slug = repository_slug.strip()
        baseline = await self.get(
            git_provider=git_provider,
            project_key=normalized_key,
            repository_slug=slug,
        )

        if baseline is None:
            baseline = ReleaseCheckBaseline(
                git_provider=git_provider,
                project_key=normalized_key,
                repository_slug=slug,
                baseline_ref=baseline_ref.strip(),
                note=note,
                updated_by=updated_by,
            )
            self.db.add(baseline)
        else:
            baseline.baseline_ref = baseline_ref.strip()
            baseline.note = note
            baseline.updated_by = updated_by

        await self.db.commit()
        await self.db.refresh(baseline)
        logger.info(
            "Release check baseline saved",
            extra={
                "git_provider": git_provider,
                "project_key": normalized_key,
                "repository_slug": slug,
                "baseline_ref": baseline.baseline_ref,
            },
        )
        return baseline

    async def clear(
        self,
        *,
        git_provider: str,
        project_key: str,
        repository_slug: str,
    ) -> bool:
        """Remove the baseline of a repository; True when one was removed."""
        result = await self.db.execute(
            delete(ReleaseCheckBaseline).where(
                ReleaseCheckBaseline.git_provider == git_provider,
                ReleaseCheckBaseline.project_key == self._normalize(project_key),
                ReleaseCheckBaseline.repository_slug == repository_slug.strip(),
            )
        )
        await self.db.commit()
        return bool(result.rowcount)
