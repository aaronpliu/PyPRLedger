from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any


logger = logging.getLogger(__name__)


class BaseGitProvider(ABC):
    """Abstract base class for Git provider integrations.

    Each provider implements methods to fetch project, repository, and user
    metadata from the respective Git platform's REST API.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (see GitProvider enum)."""

    @abstractmethod
    async def get_project_info(self, project_key: str) -> dict[str, Any] | None:
        """Fetch project/organization information.

        Args:
            project_key: Project key (Bitbucket) or org name (GitHub)

        Returns:
            Dict with keys: project_id, project_name, project_key, project_url
            None if not found.
        """

    @abstractmethod
    async def get_repository_info(self, workspace: str, repo_slug: str) -> dict[str, Any] | None:
        """Fetch repository information.

        Args:
            workspace: Project key (Bitbucket) or org/owner (GitHub)
            repo_slug: Repository slug/name

        Returns:
            Dict with keys: repository_id, repository_name, repository_slug,
            repository_url, project_id
            None if not found.
        """

    @abstractmethod
    async def get_user_info(self, username: str) -> dict[str, Any] | None:
        """Fetch user information.

        Args:
            username: User login/username

        Returns:
            Dict with keys: user_id, username, display_name, email_address
            None if not found.
        """

    async def compare_commits(
        self,
        project_key: str,
        repository_slug: str,
        from_ref: str,
        to_ref: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return raw commits reachable from ``to_ref`` but not from ``from_ref``.

        Args:
            project_key: Project key (Bitbucket) or org/owner (GitHub)
            repository_slug: Repository slug/name
            from_ref: Base ref (exclusive)
            to_ref: Target ref (inclusive)
            limit: Maximum number of commits to return

        Returns:
            List of provider-specific raw commit dicts.

        Raises:
            NotImplementedError: When the provider does not expose a compare API.
        """
        raise NotImplementedError(f"Provider '{self.name}' does not implement compare_commits()")

    async def compare_commits_complete(
        self,
        project_key: str,
        repository_slug: str,
        from_ref: str,
        to_ref: str,
        limit: int = 1000,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Return a commit difference together with a completeness flag.

        The difference is the commits reachable from ``to_ref`` but not from
        ``from_ref`` - the same set :meth:`compare_commits` returns. Providers
        that can prove completeness from their own paging signal override this;
        the default is deliberately conservative: a full page may have been cut
        short, so the enumeration is reported as incomplete.

        Args:
            project_key: Project key (Bitbucket) or org/owner (GitHub)
            repository_slug: Repository slug/name
            from_ref: Base ref (exclusive)
            to_ref: Target ref (inclusive)
            limit: Maximum number of commits to enumerate

        Returns:
            Tuple of (commits, complete). ``complete`` is True only when the whole
            difference was enumerated, so a caller may conclude that nothing is
            missing instead of admitting that it cannot tell.
        """
        commits = await self.compare_commits(
            project_key=project_key,
            repository_slug=repository_slug,
            from_ref=from_ref,
            to_ref=to_ref,
            limit=limit,
        )
        return commits, len(commits) < limit

    async def contains_commit(
        self,
        project_key: str,
        repository_slug: str,
        ref: str,
        commit: str,
    ) -> bool:
        """Whether ``commit`` is reachable from ``ref`` (one provider call).

        The answer comes from the provider's difference computation rather than
        from an enumeration of the release, so it stays exact no matter how many
        commits the release holds. The test is "does the commit introduce anything
        the ref lacks", i.e. ``commits(commit) \\ commits(ref)`` is empty:

        * Bitbucket Server - ``compare/commits?from={ref}&to={commit}`` is empty
        * Bitbucket Cloud - ``commits?include={commit}&exclude={ref}`` is empty
        * GitHub Enterprise - overridden: ``compare/{ref}...{commit}`` reports
          ``ahead_by == 0``

        Short SHAs are resolved by the provider. A blank or unknown commit
        answers False; a commit equal to the ref itself answers True.

        Args:
            project_key: Project key (Bitbucket) or org/owner (GitHub)
            repository_slug: Repository slug/name
            ref: Ref the commit should be reachable from
            commit: Commit SHA (full or short)

        Returns:
            True when the ref contains the commit.
        """
        target = (ref or "").strip()
        candidate = (commit or "").strip()
        if not target or not candidate:
            return False
        if target.lower() == candidate.lower():
            return True

        difference = await self.compare_commits(
            project_key=project_key,
            repository_slug=repository_slug,
            from_ref=target,
            to_ref=candidate,
            limit=1,
        )
        return not difference

    async def list_commits_until(
        self,
        project_key: str,
        repository_slug: str,
        until_ref: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return raw commits reachable from ``until_ref`` (newest first).

        Args:
            project_key: Project key (Bitbucket) or org/owner (GitHub)
            repository_slug: Repository slug/name
            until_ref: Ref to walk from (inclusive)
            limit: Maximum number of commits to return

        Returns:
            List of provider-specific raw commit dicts.

        Raises:
            NotImplementedError: When the provider does not expose a commit listing API.
        """
        raise NotImplementedError(f"Provider '{self.name}' does not implement list_commits_until()")

    @property
    def supports_releases(self) -> bool:
        """Whether the provider exposes a release API (GitHub Enterprise does)."""
        return False

    async def list_releases(
        self,
        project_key: str,
        repository_slug: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return the provider releases of a repository.

        Args:
            project_key: Project key (Bitbucket) or org/owner (GitHub)
            repository_slug: Repository slug/name
            limit: Maximum number of releases returned

        Returns:
            List of dicts with ``id``, ``tag_name``, ``name``, ``body``, ``draft``,
            ``prerelease``, ``html_url``, ``published_at`` and ``author``.

        Raises:
            NotImplementedError: When the provider has no release API.
        """
        raise NotImplementedError(f"Provider '{self.name}' does not implement list_releases()")

    async def create_release(
        self,
        project_key: str,
        repository_slug: str,
        *,
        tag_name: str,
        name: str,
        body: str = "",
        target_commitish: str | None = None,
        draft: bool = False,
        prerelease: bool = False,
    ) -> dict[str, Any]:
        """Publish a release on the provider.

        Raises:
            NotImplementedError: When the provider has no release API.
        """
        raise NotImplementedError(f"Provider '{self.name}' does not implement create_release()")

    async def update_release(
        self,
        project_key: str,
        repository_slug: str,
        release_id: str,
        *,
        name: str | None = None,
        body: str | None = None,
        prerelease: bool | None = None,
    ) -> dict[str, Any]:
        """Update an existing provider release.

        Raises:
            NotImplementedError: When the provider has no release API.
        """
        raise NotImplementedError(f"Provider '{self.name}' does not implement update_release()")

    @staticmethod
    def compare_refs_ready(*refs: str | None) -> bool:
        """Whether a comparison can be addressed remotely (all parts non blank)."""
        return all(bool(ref and ref.strip()) for ref in refs)

    def web_compare_url(
        self,
        project_key: str,
        repository_slug: str,
        from_ref: str,
        to_ref: str,
    ) -> str | None:
        """Browsable URL comparing two revisions, when the platform has one.

        ``from_ref`` is the base (exclusive) and ``to_ref`` the target (inclusive),
        matching :meth:`compare_commits`, so the page shows what ``to_ref`` adds on
        top of ``from_ref``.

        Args:
            project_key: Project key (Bitbucket) or org/owner (GitHub)
            repository_slug: Repository slug/name
            from_ref: Base revision (tag, branch or commit)
            to_ref: Target revision

        Returns:
            The comparison URL, or ``None`` when the provider exposes no web UI or
            the host needed to build the URL is not configured.
        """
        return None

    def web_user_url(self, username: str) -> str | None:
        """Browsable profile page of a user, when the platform has one.

        Args:
            username: Provider login / account slug of the user

        Returns:
            The profile URL, or ``None`` when the provider exposes no web UI or the
            host needed to build the URL is not configured.
        """
        return None

    async def list_workspaces(self) -> list[dict[str, Any]]:
        """Return the workspaces (Bitbucket Cloud) reachable with the credentials.

        Only Bitbucket Cloud has a workspace concept, so every other provider
        reports no workspaces instead of raising.

        Returns:
            List of dicts with ``slug`` and ``name`` keys.
        """
        return []

    async def list_refs(
        self,
        project_key: str,
        repository_slug: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Return the tags and branches of a repository.

        The listing is a picker's candidate set, so it is ordered most recently
        modified first where the provider allows it, and read whole rather than as a
        small page: a ref the picker never received is a release the reader cannot
        choose.

        Args:
            project_key: Project key (Bitbucket) or org/owner (GitHub)
            repository_slug: Repository slug/name
            limit: Maximum number of names returned per ref type

        Returns:
            Dict with ``tags`` and ``branches`` keys, each holding ref names, plus
            ``tags_total`` / ``branches_total`` when the provider reports how many
            the repository holds - the caller needs them to tell a complete listing
            from one ``limit`` cut short. A provider that cannot report them leaves
            the keys out.

        Raises:
            NotImplementedError: When the provider does not expose ref listing.
        """
        raise NotImplementedError(f"Provider '{self.name}' does not implement list_refs()")

    async def list_tags_with_commits(
        self,
        project_key: str,
        repository_slug: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return the tags of a repository with the commit each one points at.

        Entry shape (see :meth:`normalize_tag_entries`)::

            {"name": str, "sha": str, "date": int | None, "is_annotated": bool | None}

        ``date`` is epoch milliseconds (the unit the commit normalizer uses), and
        ``is_annotated`` is ``None`` when the provider does not report the tag
        type. An **annotated** tag MUST be reported with the commit it references,
        never with the tag object's own id: storing the tag object's id produces a
        revision that no comparison can resolve, and the mistake is invisible
        until a diff silently targets the wrong thing. Dereferencing is the
        provider's job because only the provider knows its own tag object model.

        The provider's ordering is **not** release order (it may be alphabetical or
        by modification time) and callers must not rely on it - ordering decisions
        belong to the caller.

        A provider that cannot resolve tags to revisions should raise instead of
        returning names with empty revisions, so the caller can degrade honestly.

        ``add-app-release-diff`` reuses this primitive for its release manifests, so
        it stays the only tag -> revision call in the codebase.

        Args:
            project_key: Project key (Bitbucket) or org/owner (GitHub)
            repository_slug: Repository slug/name
            limit: Maximum number of tags collected (the result may be capped)

        Returns:
            Tag entries, de-duplicated by name, blank entries dropped.

        Raises:
            NotImplementedError: When the provider does not expose tag revisions.
        """
        raise NotImplementedError(
            f"Provider '{self.name}' does not implement list_tags_with_commits()"
        )

    @staticmethod
    def normalize_tag_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Trim the fields of tag entries, drop blank names and de-duplicate.

        Repeated names would otherwise offer the same tag twice to the scope
        resolver, and a blank name would be unusable as a ref.
        """
        tags: list[dict[str, Any]] = []
        seen: set[str] = set()

        for entry in entries:
            name = str(entry.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            tags.append(
                {
                    "name": name,
                    "sha": str(entry.get("sha") or "").strip(),
                    "date": entry.get("date"),
                    "is_annotated": entry.get("is_annotated"),
                }
            )

        return tags
