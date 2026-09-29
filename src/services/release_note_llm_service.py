"""Optional LLM pass over the commits of a release scope.

The deterministic grouping of :mod:`src.services.release_note_service` needs no
configuration and stays the default. This is the second pass a caller can ask
for: it writes the paragraph a reader wants first, and re-groups the commits
whose subjects carry no conventional prefix.

The model only ever answers *about* the commits it was given - never with a
commit list of its own - so the notes cannot gain or lose a commit, and every
failure (disabled, unreachable, unparsable) falls back to the deterministic
notes rather than failing the request. The failure is reported rather than
swallowed: a caller that asked for AI prose can tell the reader which of the two
it ended up with.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.schemas.release_note import SUMMARY_NOTICE_FAILED, SUMMARY_NOTICE_NOT_CONFIGURED
from src.services.llm_service import REQUEST_TIMEOUT_SECONDS, LlmService, load_llm_config
from src.services.release_note_service import (
    NOTE_SECTIONS,
    OTHER_SECTION,
    commit_section,
    is_merge_commit,
)
from src.utils.log import get_logger
from src.utils.redis import RedisCache


logger = get_logger(__name__)

# The prompt is a summary task, not a data transfer: a release with thousands of
# commits is summarised from its newest work, and each subject is trimmed so a
# single over-long message cannot crowd the list out.
MAX_PROMPT_COMMITS = 300
MAX_SUBJECT_CHARS = 180

# Bumped when the prompt or the answer schema changes.
CACHE_KEY_VERSION = "v2"

KNOWN_SECTIONS: frozenset[str] = frozenset({title for title, _ in NOTE_SECTIONS} | {OTHER_SECTION})

SECTION_LIST = ", ".join([title for title, _ in NOTE_SECTIONS] + [OTHER_SECTION])

# What the commit list marks the commits the answer is asked about with. Named
# once: instructions that point at a mark the list does not write, or the other
# way round, ask a question the model cannot find.
NEEDS_SECTION_MARK = "[needs a section]"

SYSTEM_PROMPT = (
    "You write release notes for software releases. You are given the commits of "
    "one release and answer with a single JSON object, no other text:\n"
    '{"summary": "<two or three sentences describing what this release does, no '
    'headings, no bullet points>", "categories": {"<commit id>": "<section>"}}\n'
    f"The section must be one of: {SECTION_LIST}.\n"
    f'Answer for every commit the list marks "{NEEDS_SECTION_MARK}", and for no other '
    "commit; when none is marked, answer with the summary alone. Use only the "
    "commit ids you were given; never invent a commit, never invent a feature "
    "that no commit shows. When the subject of a commit is ambiguous, use "
    '"Other Changes".'
)


@dataclass(frozen=True)
class SummaryOutcome:
    """What came of the optional pass: a summary, or the reason there is none.

    ``notice`` is ``None`` when there was nothing to summarize - a scope without
    commits is not a failure - and one of the ``SUMMARY_NOTICE_*`` codes when the
    pass was asked for and could not be made.
    """

    summary: ReleaseNoteSummary | None = None
    notice: str | None = None


@dataclass(frozen=True)
class ReleaseNoteSummary:
    """What the model adds on top of the deterministic notes."""

    summary: str
    sections: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {"summary": self.summary, "sections": self.sections}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ReleaseNoteSummary:
        return cls(
            summary=str(payload.get("summary") or ""),
            sections={
                str(key): str(value) for key, value in (payload.get("sections") or {}).items()
            },
        )


# A commit id is the hex sha the answer was asked about. The summary is written
# before the sections, so both are still readable in an answer that was cut short.
_ANSWER_SUMMARY_RE = re.compile(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"')
_ANSWER_SECTION_RE = re.compile(r'"([0-9a-fA-F]{7,40})"\s*:\s*"([^"]{1,32})"')


def commits_needing_a_section(commits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The commits the deterministic pass could not place, newest first.

    Only these are put to the model: a commit whose subject already says what it
    is needs no second opinion, and the rest of the release stays in the prompt as
    the context of the summary. A merge is left out - it has no section to give.
    """
    return [
        commit
        for commit in commits
        if not is_merge_commit(commit.get("message"))
        and commit_section(commit.get("message")) == OTHER_SECTION
    ]


def _prompt_lines(commits: list[dict[str, Any]], needs_section: set[str]) -> list[str]:
    """One line per commit, the ones the answer is asked about marked.

    The rest of the list is what the summary is written from.
    """
    lines: list[str] = []
    for commit in commits:
        subject = str(commit.get("message") or "").split("\n", 1)[0].strip()
        mark = f"  {NEEDS_SECTION_MARK}" if str(commit.get("id")) in needs_section else ""
        lines.append(f"- {commit.get('id')}: {subject[:MAX_SUBJECT_CHARS]}{mark}")
    return lines


def read_cut_off_answer(raw: str) -> dict[str, Any] | None:
    """Read what arrived of an answer the provider stopped mid-object.

    A provider that stops writing - its own limit, a dropped connection - would
    otherwise lose the whole answer, the summary included, to a syntax error. The
    pairs
    are read back into the shape the model was asked for, so the same validation
    decides what is kept.
    """
    summary = _ANSWER_SUMMARY_RE.search(raw)
    sections = _ANSWER_SECTION_RE.findall(raw)
    if summary is None and not sections:
        return None
    if summary is not None:
        logger.info("Release note summary answer was cut off - reading what arrived")
    return {
        "summary": _json_string(summary.group(1)) if summary else "",
        "categories": dict(sections),
    }


def _json_string(value: str) -> str:
    """The body of a JSON string as the text it stands for."""
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value


def parse_summary_answer(text: str | None, commit_ids: set[str]) -> ReleaseNoteSummary | None:
    """Read the model's answer, keeping only what can be trusted.

    A commit id that was never sent, or a section that is not one of ours, is
    dropped rather than rendered: the answer is a suggestion, not the notes.
    """
    raw = (text or "").strip()
    if not raw:
        return None

    # a fenced block is what a model answers when the schema is not enforced
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, re.DOTALL)
    if fenced:
        raw = fenced.group(1).strip()

    start = raw.find("{")
    if start < 0:
        return None
    body = raw[start:]

    payload: dict[str, Any] | None = None
    end = body.rfind("}")
    if end > 0:
        try:
            payload = json.loads(body[: end + 1])
        except json.JSONDecodeError:
            payload = None
        if not isinstance(payload, dict):
            payload = None

    if payload is None:
        # A model that ran out of tokens - or a provider that stopped the answer -
        # is read pair by pair rather than thrown away for a syntax error.
        payload = read_cut_off_answer(body)
        if payload is None:
            logger.warning("Release note summary answer is not JSON")
            return None

    sections: dict[str, str] = {}
    categories = payload.get("categories")
    if isinstance(categories, dict):
        for key, value in categories.items():
            commit_id = str(key).strip()
            section = str(value).strip()
            if commit_id in commit_ids and section in KNOWN_SECTIONS:
                sections[commit_id] = section

    summary = str(payload.get("summary") or "").strip()
    if not summary and not sections:
        return None
    return ReleaseNoteSummary(summary=summary, sections=sections)


class ReleaseNoteLlmService:
    """Summarize a release scope with the configured LLM, best effort."""

    def __init__(
        self,
        db: AsyncSession,
        cache: RedisCache | None = None,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self._db = db
        self._cache = cache or RedisCache()
        self._timeout = timeout

    async def summarize(
        self,
        *,
        project_key: str,
        repository_slug: str,
        version: str,
        previous_version: str | None,
        commits: list[dict[str, Any]],
        language: str | None = None,
    ) -> SummaryOutcome:
        """Summary and section hints for one release scope.

        The outcome says which it is: the model's answer, or why there is none -
        not configured, a call that failed, an answer that could not be read. The
        caller renders the deterministic notes either way.
        """
        # A merge is not a change to summarize - the commits it brought in carry
        # that - so it is left out of the prompt as well as out of the notes.
        entries: list[dict[str, Any]] = []
        for commit in commits:
            if is_merge_commit(commit.get("message")):
                continue
            if len(entries) == MAX_PROMPT_COMMITS:
                break
            entries.append(commit)
        if not entries:
            return SummaryOutcome()

        config = await load_llm_config(self._db)
        client = LlmService(config, timeout=self._timeout)
        cache_key = self._cache_key(
            model=config.model,
            language=language,
            project_key=project_key,
            repository_slug=repository_slug,
            version=version,
            previous_version=previous_version,
            commits=entries,
        )

        cached = await self._read_cache(cache_key)
        if cached is not None:
            return SummaryOutcome(summary=cached)

        if not config.usable:
            return SummaryOutcome(notice=SUMMARY_NOTICE_NOT_CONFIGURED)

        needs_section = commits_needing_a_section(entries)
        needs_ids = {str(commit.get("id")) for commit in needs_section}

        answer = await client.complete(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": self._prompt(
                        entries,
                        needs_ids,
                        project_key=project_key,
                        repository_slug=repository_slug,
                        version=version,
                        previous_version=previous_version,
                        language=language,
                    ),
                },
            ]
        )
        summary = parse_summary_answer(answer, needs_ids)
        if summary is None:
            return SummaryOutcome(notice=SUMMARY_NOTICE_FAILED)

        await self._write_cache(cache_key, summary)
        logger.info(
            "Release note summary generated",
            extra={
                "project_key": project_key,
                "repository_slug": repository_slug,
                "version": version,
                "commits": len(entries),
                "grouped": len(summary.sections),
            },
        )
        return SummaryOutcome(summary=summary)

    # ------------------------------------------------------------------ #
    # Prompt and cache
    # ------------------------------------------------------------------ #

    @staticmethod
    def _prompt(
        commits: list[dict[str, Any]],
        needs_section: set[str],
        *,
        project_key: str,
        repository_slug: str,
        version: str,
        previous_version: str | None,
        language: str | None,
    ) -> str:
        scope = f"{previous_version}...{version}" if previous_version else version
        lines = [
            f"Repository: {project_key}/{repository_slug}",
            f"Release: {version} (scope: {scope})",
            f'Commits ("{NEEDS_SECTION_MARK}" marks the ones to answer about):',
        ]
        lines.extend(_prompt_lines(commits, needs_section))
        if language:
            lines.append(f"Write the summary in this language: {language}")
        return "\n".join(lines)

    @staticmethod
    def _cache_key(**parts: Any) -> str:
        commits = parts.pop("commits")
        digest = "|".join(
            [str(parts[key]) for key in sorted(parts)]
            + [str(commit.get("id") or "") for commit in commits]
        )
        return f"release_note_summary:{CACHE_KEY_VERSION}:{hashlib.sha256(digest.encode()).hexdigest()[:32]}"

    async def _read_cache(self, cache_key: str) -> ReleaseNoteSummary | None:
        try:
            cached = await self._cache.get_json(cache_key)
        except Exception as e:  # noqa: BLE001 - a cache failure must not raise
            logger.warning("Release note summary cache read failed", extra={"error": str(e)})
            return None
        if not isinstance(cached, dict):
            return None
        try:
            return ReleaseNoteSummary.from_dict(cached)
        except (TypeError, ValueError):
            return None

    async def _write_cache(self, cache_key: str, summary: ReleaseNoteSummary) -> None:
        # The scope is a fixed pair of revisions, so the answer holds until the
        # notes themselves are regenerated - and a second click costs nothing.
        try:
            await self._cache.set_json(
                cache_key, summary.as_dict(), expire=settings.CACHE_TTL_RELEASE_REFS
            )
        except Exception as e:  # noqa: BLE001 - a cache failure must not raise
            logger.warning("Release note summary cache write failed", extra={"error": str(e)})
