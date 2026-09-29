"""Tests for the release note export document.

The builder is a pure function over stored releases, so these tests pin the shape
of the document (headings, metadata, separators, empty bodies) and the filename
without touching a database or a provider.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.models.release_note import ReleaseNote, ReleaseNoteStatus
from src.services.release_note_export import (
    EMPTY_BODY_PLACEHOLDER,
    EMPTY_SELECTION_PLACEHOLDER,
    build_release_notes_document,
    build_release_section,
    release_note_export_filename,
    safe_filename_part,
)


EXPORTED_AT = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def note(
    *,
    tag: str = "v1.0.0",
    name: str = "First release",
    body: str = "- ship the login page",
    status: str = ReleaseNoteStatus.PUBLISHED,
    is_prerelease: bool = False,
) -> ReleaseNote:
    """A stored release row, built in memory."""
    return ReleaseNote(
        project_key="PROJ",
        repository_slug="my-repo",
        tag_name=tag,
        name=name,
        body=body,
        status=status,
        is_prerelease=is_prerelease,
    )


def build(releases: list[ReleaseNote], **overrides: object) -> str:
    payload: dict[str, object] = {
        "project_key": "PROJ",
        "repository_slug": "my-repo",
        "exported_at": EXPORTED_AT,
    }
    payload.update(overrides)
    return build_release_notes_document(releases, **payload)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Document shape
# --------------------------------------------------------------------------- #


def test_one_release_produces_a_complete_document() -> None:
    document = build([note()])

    assert document == (
        "# Release notes - PROJ/my-repo\n"
        "\n"
        "> PROJ/my-repo - 1 release - exported from PyPRLedger on 2026-09-29\n"
        "\n"
        "## First release (v1.0.0)\n"
        "\n"
        "- ship the login page\n"
    )


def test_several_releases_are_separated_by_a_rule() -> None:
    document = build(
        [
            note(tag="v1.1.0", name="Second", body="- second body"),
            note(tag="v1.0.0", name="First", body="- first body"),
        ]
    )

    assert "> PROJ/my-repo - 2 releases - exported from PyPRLedger on 2026-09-29" in document
    assert "## Second (v1.1.0)" in document
    assert "## First (v1.0.0)" in document
    # the order handed in is the order written, and the sections are split
    assert document.index("## Second") < document.index("## First")
    assert "\n\n---\n\n## First (v1.0.0)" in document
    # no front matter: the document starts with the title
    assert document.startswith("# Release notes - PROJ/my-repo\n")


def test_the_heading_does_not_repeat_a_name_that_is_the_tag() -> None:
    """A release drafted from a version is named after it - do not write it twice."""
    document = build([note(tag="v2.0.0", name="v2.0.0")])

    assert "## v2.0.0\n" in document
    assert "## v2.0.0 (v2.0.0)" not in document


def test_an_empty_name_falls_back_to_the_tag() -> None:
    assert build_release_section(note(tag="v3.0.0", name="  ")).startswith("## v3.0.0\n")


def test_a_draft_and_a_prerelease_are_marked_in_the_heading() -> None:
    document = build(
        [
            note(
                tag="v2.0.0-rc.1",
                name="Release candidate",
                status=ReleaseNoteStatus.DRAFT,
                is_prerelease=True,
            )
        ]
    )

    assert "## Release candidate (v2.0.0-rc.1) - draft, pre-release" in document
    # no metadata block: the section is the heading and the notes
    assert "- Status:" not in document
    assert "- Pre-release:" not in document


def test_a_draft_alone_is_marked() -> None:
    assert "## First release (v1.0.0) - draft" in build([note(status=ReleaseNoteStatus.DRAFT)])


def test_a_released_version_carries_no_marker() -> None:
    assert build_release_section(note()).startswith("## First release (v1.0.0)\n")


def test_an_empty_body_says_so() -> None:
    document = build([note(body="   ")])

    assert EMPTY_BODY_PLACEHOLDER in document


def test_an_empty_selection_still_produces_a_document() -> None:
    document = build([])

    assert EMPTY_SELECTION_PLACEHOLDER in document
    assert "0 releases" in document


# --------------------------------------------------------------------------- #
# Verbatim bodies
# --------------------------------------------------------------------------- #


def test_the_body_is_copied_verbatim() -> None:
    """Markers inside a body must survive untouched, and stay inside their section."""
    body = "### Fixed\n- ship the login fix PRL-123 (@jane)\n\n---\n\n## Not a release heading\n"

    document = build([note(tag="v1.0.0", name="Fixes", body=body)])

    assert body in document
    # the body's own rule and heading are present but belong to the one section
    assert document.count("## Fixes (v1.0.0)") == 1


def test_a_stored_body_is_not_rewritten() -> None:
    """JIRA keys stay plain: linking them is a display concern."""
    document = build([note(body="- ship the login fix PRL-123")])

    assert "- ship the login fix PRL-123" in document
    assert "browse/PRL-123" not in document


# --------------------------------------------------------------------------- #
# Filename
# --------------------------------------------------------------------------- #


def test_the_filename_of_one_release_names_its_tag() -> None:
    filename = release_note_export_filename(
        [note(tag="v1.2.0")],
        project_key="PROJ",
        repository_slug="my-repo",
        exported_at=EXPORTED_AT,
    )

    assert filename == "releasenotes-PROJ-my-repo-v1.2.0.md"


def test_the_filename_of_several_releases_is_counted_and_dated() -> None:
    filename = release_note_export_filename(
        [note(), note(tag="v1.1.0")],
        project_key="PROJ",
        repository_slug="my-repo",
        exported_at=EXPORTED_AT,
    )

    assert filename == "releasenotes-PROJ-my-repo-2-releases-20260929.md"


def test_a_tag_with_path_separators_produces_a_safe_filename() -> None:
    filename = release_note_export_filename(
        [note(tag="release/1.0.0")],
        project_key="PROJ",
        repository_slug="my-repo",
        exported_at=EXPORTED_AT,
    )

    assert filename == "releasenotes-PROJ-my-repo-release-1.0.0.md"
    assert "/" not in filename


def test_a_tag_with_spaces_and_colons_produces_a_safe_filename() -> None:
    filename = release_note_export_filename(
        [note(tag="v1.0.0: hot fix")],
        project_key="PROJ",
        repository_slug="my-repo",
        exported_at=EXPORTED_AT,
    )

    assert filename == "releasenotes-PROJ-my-repo-v1.0.0-hot-fix.md"


def test_filename_parts_that_carry_nothing_fall_back() -> None:
    assert safe_filename_part("...") == "release"
    assert safe_filename_part("  ") == "release"
    assert safe_filename_part(None) == "release"
    # repeated separators are collapsed instead of left as noise
    assert safe_filename_part("v1.0.0//rc") == "v1.0.0-rc"
