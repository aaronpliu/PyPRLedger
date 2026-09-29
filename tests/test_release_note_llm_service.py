"""Tests for the optional LLM pass over release notes.

No LLM is contacted: the provider is reached through ``httpx.MockTransport`` and
the note service is wired to a stub summarizer.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.release_diff import CommitInfo
from src.schemas.release_note import (
    SUMMARY_DETERMINISTIC,
    SUMMARY_LLM,
    ReleaseNotePreviewRequest,
)
from src.services import llm_service as llm_module
from src.services import release_note_llm_service as llm_notes_module
from src.services.llm_service import LlmConfig
from src.services.release_note_llm_service import (
    ReleaseNoteLlmService,
    ReleaseNoteSummary,
    parse_summary_answer,
)
from src.services.release_note_service import ReleaseNoteService


C1 = "1111111111111111111111111111111111111111"
C2 = "2222222222222222222222222222222222222222"


def commit(sha: str, message: str) -> CommitInfo:
    return CommitInfo(
        id=sha,
        display_id=sha[:7],
        author_name="Jane Doe",
        message=message,
        url=f"https://git.local/commits/{sha[:7]}",
    )


class StubDiffService:
    """Stands in for ReleaseDiffService (no provider traffic)."""

    def __init__(self, commits: list[CommitInfo]) -> None:
        self._commits = commits

    async def compare_releases(self, request: Any) -> Any:
        return type(
            "Comparison",
            (),
            {
                "added_commits": self._commits,
                "added_count": len(self._commits),
                "added_complete": True,
            },
        )()

    async def list_release_commits(self, **kwargs: Any) -> tuple[list[CommitInfo], bool]:
        return self._commits, False


class StubLlmService:
    """Stands in for ReleaseNoteLlmService (fixed answer, no provider traffic)."""

    def __init__(self, summary: ReleaseNoteSummary | None) -> None:
        self._summary = summary
        self.calls = 0

    async def summarize(self, **kwargs: Any) -> ReleaseNoteSummary | None:
        self.calls += 1
        return self._summary


def install_llm(
    monkeypatch: pytest.MonkeyPatch, *, enabled: bool = True, payload: Any = None
) -> None:
    """Point the summarizer at a mock provider answering ``payload``."""
    config = LlmConfig(
        enabled=enabled,
        model="test-model",
        base_url="https://llm.local/v1",
        api_key="test-key",
    )

    async def fake_load(_db: AsyncSession) -> LlmConfig:
        return config

    monkeypatch.setattr(llm_notes_module, "load_llm_config", fake_load)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        content = "" if payload is None else json.dumps(payload)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    real_client = httpx.AsyncClient

    def client_factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("verify", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(llm_module.httpx, "AsyncClient", client_factory)


def preview_request(**overrides: Any) -> ReleaseNotePreviewRequest:
    return ReleaseNotePreviewRequest(
        project_key="PROJ",
        repository_slug="my-repo",
        version="v1.1.0",
        previous_version="v1.0.0",
        **overrides,
    )


# --------------------------------------------------------------------------- #
# The model's answer
# --------------------------------------------------------------------------- #


def test_parse_summary_answer_reads_the_answer() -> None:
    answer = json.dumps({"summary": "Adds SSO login.", "categories": {C1: "Added", C2: "Fixed"}})

    summary = parse_summary_answer(answer, {C1, C2})

    assert summary is not None
    assert summary.summary == "Adds SSO login."
    assert summary.sections == {C1: "Added", C2: "Fixed"}


def test_parse_summary_answer_reads_a_fenced_block() -> None:
    """A model answers with a fenced block when the schema is not enforced."""
    answer = f"```json\n{json.dumps({'summary': 's', 'categories': {C1: 'Added'}})}\n```"

    summary = parse_summary_answer(answer, {C1})

    assert summary is not None
    assert summary.sections == {C1: "Added"}


def test_parse_summary_answer_drops_what_it_cannot_trust() -> None:
    """A commit that was never sent, or a section that is not ours, is dropped."""
    answer = json.dumps(
        {
            "summary": "s",
            "categories": {C1: "Added", "not-a-commit": "Added", C2: "Features"},
        }
    )

    summary = parse_summary_answer(answer, {C1, C2})

    assert summary is not None
    assert summary.sections == {C1: "Added"}


@pytest.mark.parametrize("answer", ["", "not json at all", "{}"])
def test_parse_summary_answer_gives_up_without_failing(answer: str) -> None:
    assert parse_summary_answer(answer, {C1}) is None


# --------------------------------------------------------------------------- #
# The summarizer
# --------------------------------------------------------------------------- #


async def test_summarize_returns_the_summary_and_the_sections(
    monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession
) -> None:
    install_llm(
        monkeypatch,
        payload={"summary": "Adds SSO login.", "categories": {C1: "Added", C2: "Fixed"}},
    )
    service = ReleaseNoteLlmService(db=db_session)

    summary = await service.summarize(
        project_key="PROJ",
        repository_slug="my-repo",
        version="v1.1.0",
        previous_version="v1.0.0",
        commits=[{"id": C1, "message": "wip"}, {"id": C2, "message": "wip"}],
    )

    assert summary is not None
    assert summary.summary == "Adds SSO login."
    assert summary.sections == {C1: "Added", C2: "Fixed"}


async def test_summarize_is_a_no_op_without_a_configured_llm(
    monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession
) -> None:
    """A deployment without an LLM keeps the deterministic notes."""
    install_llm(monkeypatch, enabled=False, payload={"summary": "s"})
    service = ReleaseNoteLlmService(db=db_session)

    summary = await service.summarize(
        project_key="PROJ",
        repository_slug="my-repo",
        version="v1.1.0",
        previous_version=None,
        commits=[{"id": C1, "message": "wip"}],
    )

    assert summary is None


async def test_summarize_survives_a_provider_failure(
    monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession
) -> None:
    install_llm(monkeypatch, payload=None)
    service = ReleaseNoteLlmService(db=db_session)

    summary = await service.summarize(
        project_key="PROJ",
        repository_slug="my-repo",
        version="v1.1.0",
        previous_version=None,
        commits=[{"id": C1, "message": "wip"}],
    )

    assert summary is None


# --------------------------------------------------------------------------- #
# Wired into the notes
# --------------------------------------------------------------------------- #


async def test_preview_renders_the_summary_the_llm_wrote(db_session: AsyncSession) -> None:
    """The summary sits above the sections, and its grouping is honoured."""
    llm = StubLlmService(ReleaseNoteSummary(summary="Adds SSO login.", sections={C1: "Added"}))
    service = ReleaseNoteService(
        db_session, diff_service=StubDiffService([commit(C1, "wip")]), llm_service=llm
    )

    preview = await service.generate_preview(preview_request(summarize=True))

    assert llm.calls == 1
    assert preview.summary_source == SUMMARY_LLM
    assert preview.summary == "Adds SSO login."
    assert "Adds SSO login." in preview.body
    assert preview.body.index("Adds SSO login.") < preview.body.index("### ✨ Added")


async def test_preview_falls_back_when_the_llm_cannot_answer(db_session: AsyncSession) -> None:
    """A failed AI pass withholds the prose, never the notes."""
    llm = StubLlmService(None)
    service = ReleaseNoteService(
        db_session, diff_service=StubDiffService([commit(C1, "wip")]), llm_service=llm
    )

    preview = await service.generate_preview(preview_request(summarize=True))

    assert preview.summary_source == SUMMARY_DETERMINISTIC
    assert preview.summary is None
    assert "wip" in preview.body
    assert "### 📝 Other Changes" in preview.body


async def test_preview_does_not_ask_unless_asked(db_session: AsyncSession) -> None:
    llm = StubLlmService(ReleaseNoteSummary(summary="s", sections={}))
    service = ReleaseNoteService(
        db_session, diff_service=StubDiffService([commit(C1, "wip")]), llm_service=llm
    )

    preview = await service.generate_preview(preview_request())

    assert llm.calls == 0
    assert preview.summary_source == SUMMARY_DETERMINISTIC


async def test_preview_survives_a_summarizer_that_raises(db_session: AsyncSession) -> None:
    class Exploding:
        async def summarize(self, **kwargs: Any) -> ReleaseNoteSummary:
            raise RuntimeError("provider exploded")

    service = ReleaseNoteService(
        db_session, diff_service=StubDiffService([commit(C1, "wip")]), llm_service=Exploding()
    )

    preview = await service.generate_preview(preview_request(summarize=True))

    assert preview.summary_source == SUMMARY_DETERMINISTIC
    assert "wip" in preview.body


async def test_preview_writes_the_notes_in_the_language_of_the_caller(
    db_session: AsyncSession,
) -> None:
    service = ReleaseNoteService(
        db_session,
        diff_service=StubDiffService([commit(C1, "feat: add login page")]),
        llm_service=StubLlmService(None),
    )

    preview = await service.generate_preview(preview_request(language="zh-CN"))

    assert preview.body.startswith("## 变更内容")
    assert "### ✨ 新增" in preview.body
