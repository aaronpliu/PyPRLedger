"""Confluence release sync - an optional integration, kept to itself.

Nothing outside this package needs to know Confluence exists. The release flow
schedules a sync and moves on; whether it succeeds is recorded on the release,
where the release page can offer a retry.
"""

from src.services.confluence.service import (
    ConfluenceSyncService,
    SyncOutcome,
    is_auto_sync_enabled,
    sync_release_note_to_confluence,
)


__all__ = [
    "ConfluenceSyncService",
    "SyncOutcome",
    "is_auto_sync_enabled",
    "sync_release_note_to_confluence",
]
