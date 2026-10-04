from __future__ import annotations

import hashlib
import re
from typing import Any

from src.core.config import settings
from src.core.exceptions import DependencyGraphNotFoundException
from src.services.dependency_api_client import DependencyApiClient
from src.utils.log import get_logger
from src.utils.metrics import MetricsCollector
from src.utils.metrics import metrics as metrics_collector
from src.utils.redis import RedisCache


logger = get_logger(__name__)

SCHEMA_VERSION = "1.0"
CACHE_KEY_VERSION = "v1"

PROJECT = 0
EXTERNAL = 1
WORKSPACE = 2

# The database answers with the closure it built; a payload larger than this is
# truncated rather than turned into an unreadable canvas and an unreadable body.
MAX_NODES = 500

EXACT_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def _constraint_map(value: Any) -> dict[str, str]:
    """A `{package: constraint}` map, whatever the record calls its values."""
    if not isinstance(value, dict):
        return {}
    return {
        str(name): str(constraint)
        for name, constraint in value.items()
        if name and constraint is not None
    }


def _package_name(entry: dict[str, Any]) -> str:
    return str(entry.get("package_name") or "")


def _release_date(record: dict[str, Any]) -> str | None:
    """When the database recorded the build."""
    created_at = record.get("created_at")
    return created_at if isinstance(created_at, str) and created_at else None


class DependencyGraphService:
    """Consolidates one answer of the dependency database into the drawn graph.

    The record holds what the application declared for its modules (an exact
    version each, which become the pinned edges) and what the packages declared
    for theirs (a range each, which become the bare relationships). Every name a
    map points at that no entry describes is a leaf of the picture.
    """

    def __init__(
        self,
        metrics: MetricsCollector | None = None,
        cache: RedisCache | None = None,
        client: DependencyApiClient | None = None,
    ) -> None:
        self.metrics = metrics or metrics_collector
        self.cache = cache or RedisCache()
        self.client = client or DependencyApiClient()

    async def build(
        self,
        *,
        app_name: str,
        project_key: str,
        repository_slug: str,
        ref: str,
        git_provider: str | None = None,
    ) -> dict[str, Any]:
        """The dependency graph of one ref, served from the cache when it is there."""
        cache_key = self._cache_key(project_key, repository_slug, app_name, ref)
        cached = await self._read_cache(cache_key)
        if cached:
            self.metrics.increment_cache_hit("dependency_graph")
            return cached

        self.metrics.increment_cache_miss("dependency_graph")
        payload = await self._consolidate(
            app_name=app_name,
            project_key=project_key,
            repository_slug=repository_slug,
            ref=ref,
            git_provider=git_provider,
        )
        await self._write_cache(cache_key, payload)
        logger.info(
            "Dependency graph consolidated",
            extra={
                "app_name": app_name,
                "project_key": project_key,
                "repository_slug": repository_slug,
                "ref": ref,
                "packages": len(payload["packages"]),
            },
        )
        return payload

    async def _consolidate(
        self,
        *,
        app_name: str,
        project_key: str,
        repository_slug: str,
        ref: str,
        git_provider: str | None,
    ) -> dict[str, Any]:
        record = await self.client.get_app_release_info(app_name, ref)
        if not record:
            raise DependencyGraphNotFoundException(app_name, ref)

        declared = _constraint_map(record.get("dependencies"))

        packages: list[dict[str, Any]] = [
            {
                "id": app_name,
                "category": PROJECT,
                "version": str(record.get("tagOrBranch") or ref),
                # What the application declared: an exact version for each module.
                "dependencies": dict(declared),
            }
        ]
        seen = {app_name}

        for entry in record.get("packages") or []:
            if not isinstance(entry, dict):
                continue
            name = _package_name(entry)
            if not name or name in seen:
                continue
            seen.add(name)
            packages.append(
                {
                    "id": name,
                    # A module the application declared is what it ships; the
                    # rest the database knows about are pulled in transitively.
                    "category": WORKSPACE if name in declared else EXTERNAL,
                    "version": str(entry.get("version") or ""),
                    "dependencies": _constraint_map(entry.get("dependencies")),
                }
            )

        # Every name a map points at that no entry describes is a leaf: it keeps
        # the version it was asked for when the constraint names one.
        for entry in [*packages]:
            for target, constraint in entry["dependencies"].items():
                if target in seen:
                    continue
                seen.add(target)
                packages.append(
                    {
                        "id": target,
                        "category": EXTERNAL,
                        "version": constraint if EXACT_VERSION.match(constraint) else "",
                        "dependencies": {},
                    }
                )

        if len(packages) > MAX_NODES:
            logger.warning(
                "Dependency graph truncated",
                extra={"app_name": app_name, "ref": ref, "packages": len(packages)},
            )
            packages = packages[:MAX_NODES]

        return {
            "schema_version": SCHEMA_VERSION,
            "project_key": project_key,
            "repository_slug": repository_slug,
            "git_provider": git_provider,
            "ref": {"name": ref, "type": ref_type_of(ref)},
            "generated_at": _release_date(record),
            "packages": packages,
        }

    def _cache_key(self, *parts: str) -> str:
        digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()
        return f"dependency_graph:{CACHE_KEY_VERSION}:{digest[:32]}"

    async def _read_cache(self, cache_key: str) -> dict[str, Any] | None:
        try:
            return await self.cache.get_json(cache_key)
        except Exception as e:
            logger.warning(
                "Dependency graph cache read failed",
                extra={"cache_key": cache_key, "error": str(e)},
            )
            return None

    async def _write_cache(self, cache_key: str, payload: dict[str, Any]) -> None:
        try:
            await self.cache.set_json(
                cache_key, payload, expire=settings.CACHE_TTL_DEPENDENCY_GRAPH
            )
        except Exception as e:
            logger.warning(
                "Dependency graph cache write failed",
                extra={"cache_key": cache_key, "error": str(e)},
            )


def ref_type_of(ref: str) -> str:
    """A ref that reads as a version is a tag; anything else is a branch."""
    return "tag" if re.match(r"^[vV]?\d+\.\d+\.\d+", ref.strip()) else "branch"
