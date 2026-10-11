"""Tests for the markdown -> Confluence storage conversion.

The converter is where release notes meet a foreign renderer, so the cases that
matter are the ordinary ones plus the two that could do damage: markup a note
might contain by accident, and markup it might contain on purpose.
"""

from __future__ import annotations

from src.services.confluence.markdown import markdown_to_storage


def test_headings_become_heading_elements() -> None:
    assert markdown_to_storage("# Title") == "<h1>Title</h1>"
    assert markdown_to_storage("### Deep") == "<h3>Deep</h3>"


def test_a_wrapped_paragraph_is_one_element() -> None:
    assert markdown_to_storage("one line\nand its wrap") == "<p>one line and its wrap</p>"


def test_a_blank_line_separates_paragraphs() -> None:
    assert markdown_to_storage("first\n\nsecond") == "<p>first</p><p>second</p>"


def test_bullets_and_numbered_items_become_lists() -> None:
    assert markdown_to_storage("- one\n- two") == "<ul><li>one</li><li>two</li></ul>"
    assert markdown_to_storage("1. one\n2. two") == "<ol><li>one</li><li>two</li></ol>"


def test_an_indented_item_is_kept_as_an_item() -> None:
    # Nesting is not built; a sub-item stays a line of the same list, which reads
    # as written rather than disappearing into the item above it.
    assert markdown_to_storage("- one\n  - a detail") == ("<ul><li>one</li><li>a detail</li></ul>")


def test_a_wrapped_bullet_line_joins_the_item_above_it() -> None:
    assert markdown_to_storage("- one\n  continued") == "<ul><li>one continued</li></ul>"


def test_bold_code_and_links() -> None:
    assert markdown_to_storage("a **bold** word") == "<p>a <strong>bold</strong> word</p>"
    assert markdown_to_storage("run `make test`") == "<p>run <code>make test</code></p>"
    assert (
        markdown_to_storage("see [the PR](https://git.local/1)")
        == '<p>see <a href="https://git.local/1">the PR</a></p>'
    )


def test_emphasis_inside_a_code_span_is_left_alone() -> None:
    assert markdown_to_storage("`a **b** c`") == "<p><code>a **b** c</code></p>"


def test_a_fenced_block_becomes_the_code_macro() -> None:
    assert markdown_to_storage("```python\nprint(1)\n```") == (
        '<ac:structured-macro ac:name="code">'
        '<ac:parameter ac:name="language">python</ac:parameter>'
        "<ac:plain-text-body><![CDATA[print(1)]]></ac:plain-text-body>"
        "</ac:structured-macro>"
    )


def test_a_fence_without_a_language_carries_no_parameter() -> None:
    converted = markdown_to_storage("```\nplain\n```")

    assert "<ac:parameter" not in converted
    assert "<![CDATA[plain]]>" in converted


def test_a_closing_sequence_inside_code_survives_as_text() -> None:
    converted = markdown_to_storage("```\n]]>\n```")

    # CDATA has no escape, so the sequence is split across two sections and the
    # code still reads as it was written.
    assert "<![CDATA[]]]]><![CDATA[>]]>" in converted


def test_a_fence_that_is_never_closed_still_becomes_a_code_block() -> None:
    converted = markdown_to_storage("```\nprint(1)")

    assert "<ac:plain-text-body><![CDATA[print(1)]]>" in converted


def test_a_rule_becomes_a_horizontal_rule() -> None:
    assert markdown_to_storage("---") == "<hr/>"


def test_what_is_not_recognised_is_text() -> None:
    assert markdown_to_storage("> quoted") == "<p>&gt; quoted</p>"
    assert markdown_to_storage("- [ ] a task") == "<ul><li>[ ] a task</li></ul>"


def test_a_note_cannot_inject_markup() -> None:
    assert markdown_to_storage("a & b") == "<p>a &amp; b</p>"
    assert markdown_to_storage("# <script>alert(1)</script>") == (
        "<h1>&lt;script&gt;alert(1)&lt;/script&gt;</h1>"
    )


def test_something_that_only_looks_like_a_link_stays_text() -> None:
    # The URL pattern stops at whitespace, so this never becomes an anchor and its
    # quotes never reach an attribute.
    converted = markdown_to_storage('[click](https://x/" onmouseover="alert(1))')

    assert "<a " not in converted
    assert 'href="' not in converted
    assert "onmouseover" in converted


def test_an_empty_note_is_an_empty_page() -> None:
    assert markdown_to_storage("") == ""
    assert markdown_to_storage("\n\n") == ""


def test_carriage_returns_are_normalised() -> None:
    assert markdown_to_storage("first\r\n\r\nsecond") == "<p>first</p><p>second</p>"
