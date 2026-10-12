"""Writing a release to Confluence, when that is set up.

The integration is an addition to publishing rather than part of it, and the
shape of this module follows from that:

* It never raises at its caller. A release is published whether or not Confluence
  answers, so a failure is recorded on the release - where the release page can
  offer a retry - and returned as a small result rather than thrown.
* It uses a session of its own. The automatic path runs after the response has
  been sent, and the manual retry runs while the request still holds its own
  transaction; neither should write through the other.
* It does nothing at all unless the integration is configured, so an instance
  that does not use Confluence behaves exactly as it did before.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.config import settings
from src.core.database import get_session_maker
from src.models.release_note import ReleaseNote, ReleaseNoteStatus
from src.services.confluence.client import (
    MAX_ERROR_LENGTH,
    ConfluenceClient,
    ConfluenceError,
    ConfluencePage,
    has_credentials,
)
from src.services.confluence.markdown import markdown_to_storage
from src.services.confluence.targets import Resolution, label, load_targets, resolve
from src.services.project_registry_service import ProjectRegistryService
from src.utils.log import get_logger
from src.utils.timezone import get_current_time


logger = get_logger(__name__)

# What a repository that is not registered resolves to.
UNKNOWN_APP_NAME = "Unknown"


@dataclass(frozen=True)
class SyncOutcome:
    """What one sync attempt did, or why it did nothing."""

    attempted: bool
    synced: bool = False
    page_url: str | None = None
    error: str | None = None
    skipped: str | None = None

    @property
    def message(self) -> str:
        """One line the release page can show as it stands."""
        if self.synced:
            return "Synced to Confluence"
        if self.skipped:
            return f"Not synced: {self.skipped}"
        return self.error or "Not synced"


def is_auto_sync_enabled() -> bool:
    """Whether anything on this instance syncs by itself.

    Two gates, so the automatic path can be switched off without clearing the
    credentials: the integration has to be configured, and the switch has to be on.
    The switch is a ceiling as well as this instance default - a repository can be
    kept out of the automatic path on its own (``auto_sync`` in its target), but none
    can be let in while the switch is off.

    Manual syncing is not gated by this: whether a release may be written by hand is
    ``enabled`` of its repository, so publishing still happens deliberately on an
    instance that syncs nothing by itself.
    """
    return settings.CONFLUENCE_SERVER_SYNC_ENABLED and has_credentials()


def page_title(app_name: str, repository_slug: str, tag_name: str) -> str:
    """The page a release lives on.

    The title has to identify the release by itself, because finding an existing
    page is what makes a repeat sync an update rather than a second page.
    An unregistered repository resolves to ``Unknown``, so the slug stands in
    there - otherwise every unregistered release would share one page.
    """
    scope = app_name if app_name and app_name != UNKNOWN_APP_NAME else repository_slug

    return f"{scope} — {tag_name}"


class ConfluenceSyncService:
    """Syncs one release note to Confluence."""

    def __init__(self, client: ConfluenceClient | None = None, session_factory=None) -> None:
        # Both are injectable so a test can exercise the calls without an instance
        # or a database behind them; production takes the defaults.
        self.client = client or ConfluenceClient()
        self._session_factory = session_factory

    async def sync_note(self, note_id: int, automatic: bool = False) -> SyncOutcome:
        """Sync one release by id, on a session of its own.

        ``automatic`` says which path asked. The two are not the same question: a
        repository that is kept out of the automatic sync is still written when
        someone asks for it, so only the automatic path consults ``auto_sync``.
        """
        if not has_credentials():
            return SyncOutcome(attempted=False, skipped="Confluence is not configured")

        # Resolved here rather than in the constructor: this service is built as a
        # request dependency, before anything has been synced, and it has no
        # business requiring a database to exist in order to be constructible.
        factory = self._session_factory or get_session_maker()
        async with factory() as session:
            note = await session.get(ReleaseNote, note_id)
            if note is None:
                return SyncOutcome(attempted=False, skipped=f"Release {note_id} not found")

            # Only a published release goes out. The automatic path checks this
            # before scheduling one at all; saying it here as well is what keeps a
            # draft from reaching Confluence through any other caller.
            if note.status != ReleaseNoteStatus.PUBLISHED:
                return SyncOutcome(
                    attempted=False,
                    skipped=f"Release {note_id} is {note.status}, not published",
                )

            return await self._sync(note, session, automatic)

    async def _sync(self, note: ReleaseNote, session, automatic: bool = False) -> SyncOutcome:
        name = label(note.project_key, note.repository_slug)

        try:
            # Which repository this is decides where it goes, so the target is
            # read first: the space and the parent page are its own, falling back
            # to its project and then to the instance.
            target = resolve(await load_targets(session), note.project_key, note.repository_slug)

            # Switched off for this repository: nothing is attempted and nothing is
            # recorded, because a repository that does not publish is a decision
            # rather than a failure of the release.
            if not target.enabled:
                return SyncOutcome(attempted=False, skipped=f"sync is switched off for {name}")

            # Left out of the automatic path on purpose. Skipped rather than failed,
            # and only when the automatic path is what asked: the manual sync is how
            # such a repository is written.
            if automatic and not target.auto_sync:
                return SyncOutcome(attempted=False, skipped=f"automatic sync is off for {name}")

            # Nowhere to write it. Recorded on the release rather than skipped, so
            # the release page says so and offers the retry once a space is set.
            if not target.has_space:
                raise ConfluenceError(f"No Confluence space is configured for {name}")

            app_name = await ProjectRegistryService().get_app_name(
                note.project_key, note.repository_slug, session
            )
            title = page_title(app_name, note.repository_slug, note.tag_name)
            body = markdown_to_storage(note.body or "")

            page = await self._upsert_page(note, title, body, target)
        except ConfluenceError as e:
            return await self._record_failure(note, session, e)
        except Exception as e:  # noqa: BLE001 - an addition must not take a release down
            # Anything unexpected is still the sync's problem, not the release's.
            logger.exception(
                "Unexpected failure while syncing a release to Confluence",
                extra={"note_id": note.id, "tag_name": note.tag_name},
            )
            return await self._record_failure(note, session, e)

        note.confluence_page_id = page.id
        note.confluence_url = page.url
        note.confluence_synced_date = get_current_time()
        note.confluence_sync_error = None
        await session.commit()

        logger.info(
            "Release synced to Confluence",
            extra={
                "note_id": note.id,
                "tag_name": note.tag_name,
                "page_id": page.id,
                "page_url": page.url,
            },
        )

        return SyncOutcome(attempted=True, synced=True, page_url=page.url)

    async def _upsert_page(
        self, note: ReleaseNote, title: str, body: str, target: Resolution
    ) -> ConfluencePage:
        """The page for this release: updated when it exists, created when it does not."""
        existing: ConfluencePage | None = None

        if note.confluence_page_id:
            try:
                existing = await self.client.get_page(note.confluence_page_id)
            except ConfluenceError as e:
                # The page may have been deleted since it was recorded. The title
                # is looked up before creating one, so this cannot leave two.
                logger.warning(
                    "Recorded Confluence page could not be read, falling back to its title",
                    extra={
                        "note_id": note.id,
                        "page_id": note.confluence_page_id,
                        "error": str(e),
                    },
                )

        if existing is None:
            existing = await self.client.find_page(title, target.space_key)

        if existing is not None:
            return await self.client.update_page(existing, title, body, target.space_key)

        return await self.client.create_page(
            title, body, target.space_key, target.parent_page_id or None
        )

    async def _record_failure(self, note: ReleaseNote, session, error: Exception) -> SyncOutcome:
        """Store why the attempt failed, so the release page can say so and retry."""
        message = str(error)[:MAX_ERROR_LENGTH]
        note.confluence_sync_error = message
        await session.commit()

        logger.warning(
            "Confluence sync failed",
            extra={"note_id": note.id, "tag_name": note.tag_name, "error": message},
        )

        return SyncOutcome(attempted=True, synced=False, error=message)


async def sync_release_note_to_confluence(note_id: int) -> None:
    """Background entry point: sync one release and forget about it.

    Scheduled after the response, so publishing is neither blocked by Confluence
    nor affected by whether it answers.
    """
    if not is_auto_sync_enabled():
        return

    try:
        await ConfluenceSyncService().sync_note(note_id, automatic=True)
    except Exception:  # noqa: BLE001 - a background task has nobody to raise at
        logger.exception("Confluence sync task failed", extra={"note_id": note_id})
