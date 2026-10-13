"""Tests for the optional Confluence sync.

Confluence is never contacted: the client is handed an httpx transport that
answers from a script, and the sync is handed the test session instead of opening
one of its own.

What is exercised is the isolation this integration is built around - a release
is recorded whether or not the sync works, and publishing never depends on it -
along with the idempotence that keeps a second sync from leaving a second page.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from src.api.v1.endpoints.release_notes import (
    get_confluence_sync_service,
    get_rbac_service,
    get_release_note_service,
)
from src.core.config import settings
from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.main import app
from src.models.auth_user import AuthUser
from src.models.release_note import ReleaseNote, ReleaseNoteStatus
from src.models.system_setting import SystemSetting
from src.services.confluence.client import ConfluenceClient, has_credentials
from src.services.confluence.service import (
    ConfluenceSyncService,
    SyncOutcome,
    is_auto_sync_enabled,
    page_title,
)
from src.services.confluence.targets import SETTING_KEY as TARGETS_SETTING_KEY
from src.services.project_registry_service import ProjectRegistryService
from src.services.release_note_service import ReleaseNoteService


BASE_URL = "https://confluence.local"
SPACE_KEY = "DOC"


# --------------------------------------------------------------------------- #
# A Confluence that answers from a script
# --------------------------------------------------------------------------- #


class FakeConfluence:
    """Records what it was asked and answers with pages it keeps itself."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []
        self.updates: list[dict[str, Any]] = []
        self.creates: list[dict[str, Any]] = []
        self.bodies: list[str] = []
        self.pages: dict[str, dict[str, Any]] = {}
        self.status = 200
        self.failure: Exception | None = None

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def seed_page(self, title: str, space: str = SPACE_KEY) -> str:
        """A page already on the instance, as an earlier attempt would leave one."""
        page_id = str(100 + len(self.pages))
        self.pages[page_id] = {
            "id": page_id,
            "title": title,
            # A page carries the space it is in, which an update has to keep naming.
            "space": {"key": space},
            "version": {"number": 1},
            "_links": {"webui": f"/spaces/{space}/pages/{page_id}", "base": BASE_URL},
        }
        return page_id

    def calls(self, method: str) -> list[str]:
        return [path for verb, path in self.requests if verb == method]

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append((request.method, request.url.path))

        if self.failure is not None:
            raise self.failure
        if self.status >= 400:
            return httpx.Response(self.status, text="confluence said no")

        if request.method == "GET" and request.url.path.endswith("/rest/api/content"):
            title = request.url.params.get("title")
            found = [page for page in self.pages.values() if page["title"] == title]
            return httpx.Response(200, json={"results": found})

        if request.method == "GET":
            page = self.pages.get(request.url.path.rsplit("/", 1)[-1])
            if page is None:
                return httpx.Response(404, text="no such page")
            return httpx.Response(200, json=page)

        if request.method == "POST":
            payload = json.loads(request.content)
            self.creates.append(payload)
            self.bodies.append(payload["body"]["storage"]["value"])
            page_id = self.seed_page(payload["title"], payload["space"]["key"])
            return httpx.Response(200, json=self.pages[page_id])

        if request.method == "PUT":
            payload = json.loads(request.content)
            self.bodies.append(payload["body"]["storage"]["value"])
            page_id = request.url.path.rsplit("/", 1)[-1]
            page = self.pages.get(page_id)
            if page is None:
                return httpx.Response(404, text="no such page")
            self.updates.append(payload)
            updated = {**page, "title": payload["title"], "version": payload["version"]}
            self.pages[page_id] = updated
            return httpx.Response(200, json=updated)

        return httpx.Response(405, text="unexpected")


class SharedSession:
    """Hands the sync the test session, which it must not close."""

    def __init__(self, session) -> None:
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info) -> bool:
        return False


# --------------------------------------------------------------------------- #
# Fixtures and helpers
# --------------------------------------------------------------------------- #


@pytest.fixture
def confluence_settings(monkeypatch):
    """A configured and switched-on integration, undone with the test."""
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_BASE_URL", BASE_URL)
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SPACE_KEY", SPACE_KEY)
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_TOKEN", "pat_test")
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SYNC_ENABLED", True)
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_PARENT_PAGE_ID", None)


@pytest.fixture
def unconfigured_confluence(monkeypatch):
    """The integration off, whatever the environment the tests run in holds.

    `.env` is read into `settings` when the module is imported, so a machine that
    has Confluence configured would otherwise decide tests that are about an
    instance without it: what they assert is what nothing set looks like, so
    nothing is set here.
    """
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_BASE_URL", None)
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_TOKEN", None)
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_USERNAME", None)
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_PASSWORD", None)
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SYNC_ENABLED", False)


def build_sync(fake: FakeConfluence, db_session) -> ConfluenceSyncService:
    return ConfluenceSyncService(
        client=ConfluenceClient(transport=fake.transport),
        session_factory=lambda: SharedSession(db_session),
    )


async def make_note(
    db_session,
    tag: str = "v1.0.0",
    body: str = "# Notes\n\nFixed a thing.",
    status: str = ReleaseNoteStatus.PUBLISHED,
) -> ReleaseNote:
    note = ReleaseNote(
        project_key="PROJ",
        repository_slug="my-repo",
        tag_name=tag,
        name=tag,
        body=body,
        status=status,
    )
    db_session.add(note)
    await db_session.flush()
    return note


async def set_targets(db_session, projects=None, repositories=None) -> None:
    """Store publishing targets, in the shape the settings endpoint writes."""
    db_session.add(
        SystemSetting(
            setting_key=TARGETS_SETTING_KEY,
            setting_value=json.dumps(
                {"projects": projects or [], "repositories": repositories or []}
            ),
        )
    )
    await db_session.flush()


# --------------------------------------------------------------------------- #
# The switch, and what a title has to do
# --------------------------------------------------------------------------- #


def test_the_switch_gates_the_automatic_sync_only(confluence_settings, monkeypatch) -> None:
    assert has_credentials() is True
    assert is_auto_sync_enabled() is True

    # Switched off: configured, so a manual retry is still possible, but
    # publishing stops writing to Confluence by itself.
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SYNC_ENABLED", False)
    assert has_credentials() is True
    assert is_auto_sync_enabled() is False


def test_an_unset_base_url_leaves_the_integration_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_BASE_URL", None)
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_TOKEN", "pat_test")
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SPACE_KEY", SPACE_KEY)

    assert has_credentials() is False
    assert is_auto_sync_enabled() is False


def test_a_space_is_no_longer_part_of_being_ready(confluence_settings, monkeypatch) -> None:
    """Whether there is a space is asked of each repository, not of the instance."""
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SPACE_KEY", None)

    assert has_credentials() is True
    assert is_auto_sync_enabled() is True


def test_a_title_identifies_the_release_on_its_own() -> None:
    assert page_title("my-app", "my-repo", "v1.0.0") == "my-app — v1.0.0"
    # An unregistered repository resolves to Unknown, and every such release
    # would otherwise land on one page.
    assert page_title("Unknown", "my-repo", "v1.0.0") == "my-repo — v1.0.0"
    assert page_title("", "my-repo", "v1.0.0") == "my-repo — v1.0.0"


# --------------------------------------------------------------------------- #
# The sync itself
# --------------------------------------------------------------------------- #


async def test_an_unconfigured_instance_contacts_nothing(
    db_session, unconfigured_confluence
) -> None:
    fake = FakeConfluence()
    outcome = await build_sync(fake, db_session).sync_note(1)

    assert outcome.attempted is False
    assert outcome.skipped == "Confluence is not configured"
    assert fake.requests == []


async def test_a_release_becomes_a_page_and_is_recorded(db_session, confluence_settings) -> None:
    fake = FakeConfluence()
    note = await make_note(db_session)

    outcome = await build_sync(fake, db_session).sync_note(note.id)

    assert outcome.synced is True
    assert fake.calls("POST") == ["/rest/api/content"]
    assert note.confluence_page_id is not None
    assert note.confluence_url == f"{BASE_URL}/spaces/{SPACE_KEY}/pages/100"
    assert note.confluence_synced_date is not None
    assert note.confluence_sync_error is None


async def test_the_notes_are_written_as_storage_xhtml(db_session, confluence_settings) -> None:
    fake = FakeConfluence()
    note = await make_note(db_session, body="# v1.0.0\n\n```sh\nmake release\n```")

    await build_sync(fake, db_session).sync_note(note.id)

    assert len(fake.bodies) == 1
    written = fake.bodies[0]
    assert "<h1>v1.0.0</h1>" in written
    assert '<ac:structured-macro ac:name="code">' in written
    assert "make release" in written


async def test_the_app_name_is_used_once_the_repository_is_registered(
    db_session, confluence_settings, monkeypatch
) -> None:
    fake = FakeConfluence()
    note = await make_note(db_session)

    async def _app_name(self, project_key, repository_slug, db):
        return "My App"

    monkeypatch.setattr(ProjectRegistryService, "get_app_name", _app_name)

    await build_sync(fake, db_session).sync_note(note.id)

    assert note.confluence_page_id is not None
    assert fake.pages[note.confluence_page_id]["title"] == "My App — v1.0.0"


async def test_a_second_sync_updates_rather_than_creating_another_page(
    db_session, confluence_settings
) -> None:
    fake = FakeConfluence()
    note = await make_note(db_session)
    sync = build_sync(fake, db_session)

    await sync.sync_note(note.id)
    note.body = "# Notes\n\nAnd a second thought."
    await db_session.flush()
    await sync.sync_note(note.id)

    assert fake.calls("POST") == ["/rest/api/content"]
    assert len(fake.calls("GET")) == 2  # read by title, then by id
    assert len(fake.updates) == 1
    # Confluence refuses an update that does not move the version on.
    assert fake.updates[0]["version"]["number"] == 2
    assert len(fake.pages) == 1


async def test_a_page_an_earlier_attempt_created_is_found_by_its_title(
    db_session, confluence_settings
) -> None:
    fake = FakeConfluence()
    note = await make_note(db_session)
    # No page id recorded on the release, but the page is already there.
    existing = fake.seed_page("my-repo — v1.0.0")

    outcome = await build_sync(fake, db_session).sync_note(note.id)

    assert outcome.synced is True
    assert fake.calls("POST") == []
    assert note.confluence_page_id == existing
    assert len(fake.pages) == 1


async def test_a_recorded_page_that_is_gone_falls_back_to_the_title(
    db_session, confluence_settings
) -> None:
    fake = FakeConfluence()
    note = await make_note(db_session)
    note.confluence_page_id = "999"  # recorded, but deleted in Confluence since

    outcome = await build_sync(fake, db_session).sync_note(note.id)

    assert outcome.synced is True
    assert fake.calls("POST") == ["/rest/api/content"]
    assert note.confluence_page_id != "999"


async def test_a_refused_call_is_recorded_rather_than_raised(
    db_session, confluence_settings
) -> None:
    fake = FakeConfluence()
    fake.status = 500
    note = await make_note(db_session)

    outcome = await build_sync(fake, db_session).sync_note(note.id)

    assert outcome.synced is False
    assert outcome.error is not None
    assert "500" in outcome.error
    assert note.confluence_sync_error is not None
    assert note.confluence_page_id is None
    # The release itself is untouched: it is published either way.
    assert note.status == ReleaseNoteStatus.PUBLISHED


async def test_an_unreachable_confluence_is_recorded_rather_than_raised(
    db_session, confluence_settings
) -> None:
    fake = FakeConfluence()
    fake.failure = httpx.ConnectError("no route to host")
    note = await make_note(db_session)

    outcome = await build_sync(fake, db_session).sync_note(note.id)

    assert outcome.synced is False
    assert outcome.error is not None
    assert "could not be reached" in outcome.error
    assert note.confluence_sync_error is not None


async def test_a_failure_does_not_lose_an_already_recorded_page(
    db_session, confluence_settings
) -> None:
    fake = FakeConfluence()
    note = await make_note(db_session)
    sync = build_sync(fake, db_session)
    await sync.sync_note(note.id)
    page_id = note.confluence_page_id

    fake.status = 503
    outcome = await sync.sync_note(note.id)

    assert outcome.synced is False
    # The page is still the release's page; only the last attempt failed.
    assert note.confluence_page_id == page_id


async def test_a_release_that_is_not_there_is_skipped(db_session, confluence_settings) -> None:
    fake = FakeConfluence()
    outcome = await build_sync(fake, db_session).sync_note(987654)

    assert outcome.attempted is False
    assert "not found" in (outcome.skipped or "")
    assert fake.requests == []


async def test_a_later_success_clears_the_recorded_failure(db_session, confluence_settings) -> None:
    fake = FakeConfluence()
    note = await make_note(db_session)
    sync = build_sync(fake, db_session)

    fake.status = 500
    await sync.sync_note(note.id)
    assert note.confluence_sync_error is not None

    fake.status = 200
    await sync.sync_note(note.id)

    assert note.confluence_sync_error is None
    assert note.confluence_url is not None


# --------------------------------------------------------------------------- #
# Where a release is published
# --------------------------------------------------------------------------- #


async def test_a_space_set_on_the_project_is_used_by_its_repositories(
    db_session, confluence_settings
) -> None:
    fake = FakeConfluence()
    note = await make_note(db_session)
    await set_targets(db_session, projects=[{"project_key": "PROJ", "space_key": "PROJSPACE"}])

    await build_sync(fake, db_session).sync_note(note.id)

    assert fake.creates[0]["space"]["key"] == "PROJSPACE"


async def test_a_repository_target_overrides_its_project(db_session, confluence_settings) -> None:
    fake = FakeConfluence()
    note = await make_note(db_session)
    await set_targets(
        db_session,
        projects=[{"project_key": "PROJ", "space_key": "PROJSPACE", "parent_page_id": "1"}],
        repositories=[
            {
                "project_key": "PROJ",
                "repository_slug": "my-repo",
                "space_key": "OWNSPACE",
                "parent_page_id": "2",
            }
        ],
    )

    await build_sync(fake, db_session).sync_note(note.id)

    assert fake.creates[0]["space"]["key"] == "OWNSPACE"
    assert fake.creates[0]["ancestors"] == [{"id": "2"}]


async def test_a_parent_page_is_used_only_where_one_is_decided(
    db_session, confluence_settings
) -> None:
    """With none anywhere, the page is created at the root of the space."""
    fake = FakeConfluence()
    note = await make_note(db_session)
    await set_targets(db_session, projects=[{"project_key": "PROJ", "space_key": "PROJSPACE"}])

    await build_sync(fake, db_session).sync_note(note.id)

    assert "ancestors" not in fake.creates[0]


async def test_a_repository_with_no_space_anywhere_is_recorded_as_a_failure(
    db_session, confluence_settings, monkeypatch
) -> None:
    """Nothing is attempted, and the release says why rather than looking untouched."""
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SPACE_KEY", None)
    fake = FakeConfluence()
    note = await make_note(db_session)

    outcome = await build_sync(fake, db_session).sync_note(note.id)

    assert outcome.synced is False
    assert outcome.error == "No Confluence space is configured for PROJ/my-repo"
    assert note.confluence_sync_error == outcome.error
    assert fake.requests == []


async def test_a_repository_switched_off_is_skipped_without_a_trace(
    db_session, confluence_settings
) -> None:
    fake = FakeConfluence()
    note = await make_note(db_session)
    await set_targets(
        db_session,
        repositories=[{"project_key": "PROJ", "repository_slug": "my-repo", "enabled": False}],
    )

    outcome = await build_sync(fake, db_session).sync_note(note.id)

    assert outcome.attempted is False
    assert "switched off" in (outcome.skipped or "")
    # A repository that does not publish is a decision, not a failure.
    assert note.confluence_sync_error is None
    assert fake.requests == []


async def test_another_repository_being_off_does_not_touch_this_one(
    db_session, confluence_settings
) -> None:
    fake = FakeConfluence()
    note = await make_note(db_session)
    await set_targets(
        db_session,
        repositories=[{"project_key": "PROJ", "repository_slug": "internal-lib", "enabled": False}],
    )

    outcome = await build_sync(fake, db_session).sync_note(note.id)

    assert outcome.synced is True
    assert fake.calls("POST") == ["/rest/api/content"]


async def test_an_update_keeps_the_space_the_page_is_already_in(
    db_session, confluence_settings
) -> None:
    """A target can be changed; a page already written stays where it is."""
    fake = FakeConfluence()
    note = await make_note(db_session)
    note.confluence_page_id = fake.seed_page("my-repo — v1.0.0", space="OLD")
    await set_targets(
        db_session,
        repositories=[{"project_key": "PROJ", "repository_slug": "my-repo", "space_key": "NEW"}],
    )

    outcome = await build_sync(fake, db_session).sync_note(note.id)

    assert outcome.synced is True
    assert fake.updates[0]["space"]["key"] == "OLD"
    assert fake.calls("POST") == []


async def test_a_draft_is_not_written_anywhere(db_session, confluence_settings) -> None:
    """Confluence is read by other people; publishing is what puts a release there."""
    fake = FakeConfluence()
    note = await make_note(db_session, status=ReleaseNoteStatus.DRAFT)

    outcome = await build_sync(fake, db_session).sync_note(note.id)

    assert outcome.attempted is False
    assert "not published" in (outcome.skipped or "")
    assert note.confluence_page_id is None
    assert fake.requests == []


async def test_the_switch_being_off_leaves_the_manual_sync_working(
    db_session, confluence_settings, monkeypatch
) -> None:
    """The switch is about the automatic path, so asking for the write still works.

    This is what the two switches are for: an instance that writes nothing by itself
    is still one where a release can be published to Confluence deliberately.
    """
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SYNC_ENABLED", False)
    fake = FakeConfluence()
    note = await make_note(db_session)

    outcome = await build_sync(fake, db_session).sync_note(note.id)

    assert outcome.synced is True
    assert fake.calls("POST") == ["/rest/api/content"]


async def test_the_automatic_path_leaves_out_a_repository_that_opted_out(
    db_session, confluence_settings
) -> None:
    fake = FakeConfluence()
    note = await make_note(db_session)
    await set_targets(
        db_session,
        repositories=[{"project_key": "PROJ", "repository_slug": "my-repo", "auto_sync": False}],
    )

    automatic = await build_sync(fake, db_session).sync_note(note.id, automatic=True)

    assert automatic.attempted is False
    assert automatic.skipped == "automatic sync is off for PROJ/my-repo"
    # Being left out is a decision, not a failure, so nothing is recorded on it.
    assert note.confluence_sync_error is None
    assert fake.requests == []

    # And the same release written on request: what was switched off is the
    # automatic path, not this repository.
    manual = await build_sync(fake, db_session).sync_note(note.id)

    assert manual.synced is True
    assert fake.calls("POST") == ["/rest/api/content"]


async def test_the_automatic_path_is_stopped_by_the_environment_even_where_a_repository_asks(
    db_session, confluence_settings, monkeypatch
) -> None:
    """The switch is a ceiling, not a default a repository can override."""
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SYNC_ENABLED", False)
    fake = FakeConfluence()
    note = await make_note(db_session)
    await set_targets(
        db_session,
        repositories=[{"project_key": "PROJ", "repository_slug": "my-repo", "auto_sync": True}],
    )

    outcome = await build_sync(fake, db_session).sync_note(note.id, automatic=True)

    assert outcome.attempted is False
    assert outcome.skipped == "automatic sync is off for PROJ/my-repo"
    assert fake.requests == []


async def test_a_repository_left_out_of_the_automatic_sync_still_needs_a_space(
    db_session, confluence_settings, monkeypatch
) -> None:
    """Being left out of the automatic path is not a way of publishing nowhere.

    The manual sync still reaches this repository, so it needs a target like any
    other - and says so on the release when it has none.
    """
    monkeypatch.setattr(settings, "CONFLUENCE_SERVER_SPACE_KEY", None)
    fake = FakeConfluence()
    note = await make_note(db_session)
    await set_targets(
        db_session,
        repositories=[
            {
                "project_key": "PROJ",
                "repository_slug": "my-repo",
                "auto_sync": False,
                "parent_page_id": "9",
            }
        ],
    )

    outcome = await build_sync(fake, db_session).sync_note(note.id)

    assert outcome.synced is False
    assert outcome.error == "No Confluence space is configured for PROJ/my-repo"
    assert fake.requests == []


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


class StubRBAC:
    def __init__(self) -> None:
        self.allowed = True
        self.calls: list[tuple[str, str]] = []

    async def check_permission(self, auth_user_id: int, action: str, resource_type: str) -> bool:
        self.calls.append((action, resource_type))
        return self.allowed


@pytest.fixture
def authenticated_client(db_session):
    """Test client with auth and release note dependencies overridden."""

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    async def _db_session():
        yield db_session

    rbac = StubRBAC()
    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_db_session] = _db_session
    app.dependency_overrides[get_release_note_service] = lambda: ReleaseNoteService(db_session)
    app.dependency_overrides[get_rbac_service] = lambda: rbac
    yield rbac
    for dependency in (
        get_current_user_with_token,
        get_db_session,
        get_release_note_service,
        get_rbac_service,
        get_confluence_sync_service,
    ):
        app.dependency_overrides.pop(dependency, None)


async def test_the_page_is_told_whether_a_sync_is_possible(
    async_client, authenticated_client, confluence_settings
) -> None:
    response = await async_client.get("/api/v1/release/notes/confluence")

    assert response.status_code == 200
    assert response.json() == {"configured": True, "auto_sync": True}


async def test_the_page_is_told_when_the_integration_is_absent(
    async_client, authenticated_client, unconfigured_confluence
) -> None:
    response = await async_client.get("/api/v1/release/notes/confluence")

    assert response.status_code == 200
    assert response.json() == {"configured": False, "auto_sync": False}


async def test_the_manual_sync_reports_what_happened(
    async_client, authenticated_client, db_session
) -> None:
    note = await make_note(db_session)

    class StubSync:
        async def sync_note(self, note_id: int, automatic: bool = False) -> SyncOutcome:
            assert note_id == note.id
            # The endpoint is the manual path, which is what decides whether the
            # automatic switch of a repository is consulted at all.
            assert automatic is False
            return SyncOutcome(
                attempted=True,
                synced=True,
                page_url=f"{BASE_URL}/spaces/{SPACE_KEY}/pages/100",
            )

    app.dependency_overrides[get_confluence_sync_service] = lambda: StubSync()

    response = await async_client.post(f"/api/v1/release/notes/{note.id}/confluence-sync")

    assert response.status_code == 200
    body = response.json()
    assert body["synced"] is True
    assert body["page_url"] == f"{BASE_URL}/spaces/{SPACE_KEY}/pages/100"
    assert body["message"] == "Synced to Confluence"


async def test_the_manual_sync_says_so_when_it_did_nothing(
    async_client, authenticated_client, db_session
) -> None:
    note = await make_note(db_session)

    class StubSync:
        async def sync_note(self, note_id: int, automatic: bool = False) -> SyncOutcome:
            return SyncOutcome(attempted=False, skipped="Confluence is not configured")

    app.dependency_overrides[get_confluence_sync_service] = lambda: StubSync()

    response = await async_client.post(f"/api/v1/release/notes/{note.id}/confluence-sync")

    assert response.status_code == 200
    assert response.json()["synced"] is False
    assert response.json()["message"] == "Not synced: Confluence is not configured"


async def test_the_manual_sync_refuses_a_draft(
    async_client, authenticated_client, db_session
) -> None:
    """Asking for a draft to be published to Confluence is answered, not obeyed."""
    note = await make_note(db_session, status=ReleaseNoteStatus.DRAFT)

    response = await async_client.post(f"/api/v1/release/notes/{note.id}/confluence-sync")

    assert response.status_code == 409
    assert "only a published release" in response.json()["detail"]["message"]


async def test_the_manual_sync_needs_manage_permission(
    async_client, authenticated_client, db_session
) -> None:
    note = await make_note(db_session)
    authenticated_client.allowed = False

    response = await async_client.post(f"/api/v1/release/notes/{note.id}/confluence-sync")

    assert response.status_code == 403


async def test_the_manual_sync_reports_a_release_that_is_not_there(
    async_client, authenticated_client
) -> None:
    response = await async_client.post("/api/v1/release/notes/987654/confluence-sync")

    assert response.status_code == 404


async def test_publishing_does_not_touch_confluence_when_it_is_off(
    async_client, authenticated_client, unconfigured_confluence, monkeypatch
) -> None:
    """The integration is absent: nothing is scheduled, and calls are unchanged."""
    scheduled: list[int] = []

    async def _record(note_id: int) -> None:
        scheduled.append(note_id)

    monkeypatch.setattr(
        "src.api.v1.endpoints.release_notes.sync_release_note_to_confluence", _record
    )

    response = await async_client.post(
        "/api/v1/release/notes",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "tag_name": "v1.0.0",
            "status": "published",
        },
    )

    assert response.status_code == 201
    assert scheduled == []


async def test_publishing_schedules_a_sync_when_it_is_on(
    async_client, authenticated_client, confluence_settings, monkeypatch
) -> None:
    scheduled: list[int] = []

    async def _record(note_id: int) -> None:
        scheduled.append(note_id)

    monkeypatch.setattr(
        "src.api.v1.endpoints.release_notes.sync_release_note_to_confluence", _record
    )

    response = await async_client.post(
        "/api/v1/release/notes",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "tag_name": "v2.0.0",
            "status": "published",
        },
    )

    assert response.status_code == 201
    assert scheduled == [response.json()["id"]]


async def test_a_draft_is_not_synced(
    async_client, authenticated_client, confluence_settings, monkeypatch
) -> None:
    scheduled: list[int] = []

    async def _record(note_id: int) -> None:
        scheduled.append(note_id)

    monkeypatch.setattr(
        "src.api.v1.endpoints.release_notes.sync_release_note_to_confluence", _record
    )

    response = await async_client.post(
        "/api/v1/release/notes",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "tag_name": "v3.0.0",
            "status": "draft",
        },
    )

    assert response.status_code == 201
    assert scheduled == []


async def test_the_request_can_decline_the_sync(
    async_client, authenticated_client, confluence_settings, monkeypatch
) -> None:
    scheduled: list[int] = []

    async def _record(note_id: int) -> None:
        scheduled.append(note_id)

    monkeypatch.setattr(
        "src.api.v1.endpoints.release_notes.sync_release_note_to_confluence", _record
    )

    response = await async_client.post(
        "/api/v1/release/notes",
        json={
            "project_key": "PROJ",
            "repository_slug": "my-repo",
            "tag_name": "v4.0.0",
            "status": "published",
            "sync_to_confluence": False,
        },
    )

    assert response.status_code == 201
    assert scheduled == []


# --------------------------------------------------------------------------- #
# What an update is worth writing
# --------------------------------------------------------------------------- #


def record_scheduled(monkeypatch) -> list[int]:
    """Collect the release ids the endpoint hands to the background task."""
    scheduled: list[int] = []

    async def _record(note_id: int) -> None:
        scheduled.append(note_id)

    monkeypatch.setattr(
        "src.api.v1.endpoints.release_notes.sync_release_note_to_confluence", _record
    )

    return scheduled


async def test_editing_the_notes_writes_the_page_again(
    async_client, authenticated_client, db_session, confluence_settings, monkeypatch
) -> None:
    scheduled = record_scheduled(monkeypatch)
    note = await make_note(db_session)

    response = await async_client.put(
        f"/api/v1/release/notes/{note.id}",
        json={"body": "# Notes\n\nFixed another thing."},
    )

    assert response.status_code == 200
    assert scheduled == [note.id]


async def test_saving_a_published_release_unchanged_writes_nothing(
    async_client, authenticated_client, db_session, confluence_settings, monkeypatch
) -> None:
    """The form is saved whole, so most saves carry the notes as they already are.

    Writing those again would only add a version to a page that says what it
    already says - and the version the release compares to, or whether it is a
    pre-release, are not on the page at all.
    """
    scheduled = record_scheduled(monkeypatch)
    note = await make_note(db_session)

    response = await async_client.put(
        f"/api/v1/release/notes/{note.id}",
        json={
            "name": note.name,
            "body": note.body,
            "previous_tag": "v0.9.0",
            "is_prerelease": True,
            "status": "published",
        },
    )

    assert response.status_code == 200
    assert scheduled == []


async def test_renaming_a_release_writes_nothing(
    async_client, authenticated_client, db_session, confluence_settings, monkeypatch
) -> None:
    """The release's name is this application's title; the page is titled by its tag."""
    scheduled = record_scheduled(monkeypatch)
    note = await make_note(db_session)

    response = await async_client.put(
        f"/api/v1/release/notes/{note.id}", json={"name": "A better title"}
    )

    assert response.status_code == 200
    assert scheduled == []


async def test_publishing_a_draft_writes_its_first_page(
    async_client, authenticated_client, db_session, confluence_settings, monkeypatch
) -> None:
    """A release with no page is a change in itself, notes or no notes."""
    scheduled = record_scheduled(monkeypatch)
    note = await make_note(db_session, status=ReleaseNoteStatus.DRAFT)

    response = await async_client.put(
        f"/api/v1/release/notes/{note.id}", json={"status": "published"}
    )

    assert response.status_code == 200
    assert scheduled == [note.id]
