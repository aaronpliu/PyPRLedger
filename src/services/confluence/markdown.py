"""Markdown to Confluence storage format.

Release notes are stored as markdown and Confluence takes its own storage format,
which is XHTML. This module is the bridge between the two.

It covers what release notes actually contain - headings, paragraphs, lists,
fenced code, rules, and inline bold, code and links - and treats everything else
as text.

Two things it deliberately does not do. It does not turn issue keys into links:
that is a rendering decision belonging to the instance the page is written to,
and the release note export leaves bodies verbatim for the same reason. And it
never passes input through: text is escaped before any markup is added, so a note
cannot break the page it is written to, let alone inject into it.
"""

from __future__ import annotations

import html
import re


HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")
BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
ORDERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")
RULE = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
FENCE = re.compile(r"^\s*```\s*([A-Za-z0-9_+-]*)\s*$")

INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")

# The placeholder that carries a code span past the other inline patterns.
_HELD_SPAN = re.compile(r"\x00(\d+)\x00")

# What the code macro is called in the storage format.
CODE_MACRO = "code"


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _escape_attribute(value: str) -> str:
    return html.escape(value, quote=True)


def _inline(text: str) -> str:
    """Inline markup, applied to text that has already been escaped."""
    escaped = _escape(text)

    # Code spans are lifted out first: their contents are not markup, and the
    # patterns below would otherwise read the asterisks inside them.
    spans: list[str] = []

    def hold(match: re.Match[str]) -> str:
        spans.append(match.group(1))
        return f"\x00{len(spans) - 1}\x00"

    working = INLINE_CODE.sub(hold, escaped)
    working = BOLD.sub(lambda match: f"<strong>{match.group(1)}</strong>", working)
    working = LINK.sub(
        lambda match: f'<a href="{_escape_attribute(match.group(2))}">{match.group(1)}</a>',
        working,
    )

    def release(match: re.Match[str]) -> str:
        return f"<code>{spans[int(match.group(1))]}</code>"

    return _HELD_SPAN.sub(release, working)


def _code_block(body: str, language: str) -> str:
    """A fenced block, as the code macro Confluence renders it with."""
    parameter = (
        f'<ac:parameter ac:name="language">{_escape_attribute(language)}</ac:parameter>'
        if language
        else ""
    )
    # CDATA has no escape, so a closing sequence inside the code is split across
    # two sections - the standard way to carry one literally.
    safe = body.replace("]]>", "]]]]><![CDATA[>")
    return (
        f'<ac:structured-macro ac:name="{CODE_MACRO}">'
        f"{parameter}"
        f"<ac:plain-text-body><![CDATA[{safe}]]></ac:plain-text-body>"
        "</ac:structured-macro>"
    )


def _starts_block(line: str) -> bool:
    """Whether a line opens a block of its own rather than continuing a paragraph."""
    return bool(
        HEADING.match(line)
        or FENCE.match(line)
        or RULE.match(line)
        or BULLET.match(line)
        or ORDERED.match(line)
    )


def _list(lines: list[str], start: int, pattern: re.Pattern[str], tag: str) -> tuple[str, int]:
    """One list, from its first item to the line that ends it."""
    items: list[str] = []
    index = start

    while index < len(lines):
        match = pattern.match(lines[index])
        if match:
            items.append(_inline(match.group(1).strip()))
            index += 1
            continue

        # An indented line that is not itself an item continues the one above it,
        # which is how markdown wraps a long bullet. Nesting is not built: an
        # indented item stays a line of the same list, which reads as written.
        if lines[index].strip() and lines[index][:1].isspace() and items:
            items[-1] = f"{items[-1]} {_inline(lines[index].strip())}"
            index += 1
            continue

        break

    body = "".join(f"<li>{item}</li>" for item in items)
    return f"<{tag}>{body}</{tag}>", index


def markdown_to_storage(markdown: str) -> str:
    """The notes, as Confluence storage XHTML."""
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[str] = []
    index = 0

    while index < len(lines):
        stripped = lines[index].strip()

        if not stripped:
            index += 1
            continue

        fence = FENCE.match(lines[index])
        if fence:
            body: list[str] = []
            index += 1
            while index < len(lines) and not FENCE.match(lines[index]):
                body.append(lines[index])
                index += 1
            index += 1  # the closing fence, or the end of the notes
            blocks.append(_code_block("\n".join(body), fence.group(1)))
            continue

        heading = HEADING.match(lines[index])
        if heading:
            level = len(heading.group(1))
            blocks.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            index += 1
            continue

        if RULE.match(lines[index]):
            blocks.append("<hr/>")
            index += 1
            continue

        if BULLET.match(lines[index]):
            block, index = _list(lines, index, BULLET, "ul")
            blocks.append(block)
            continue

        if ORDERED.match(lines[index]):
            block, index = _list(lines, index, ORDERED, "ol")
            blocks.append(block)
            continue

        # A paragraph runs until a blank line or something that opens a block.
        # A single newline reads as a space, the way markdown wraps text.
        paragraph = [stripped]
        index += 1
        while index < len(lines) and lines[index].strip() and not _starts_block(lines[index]):
            paragraph.append(lines[index].strip())
            index += 1
        blocks.append(f"<p>{_inline(' '.join(paragraph))}</p>")

    return "".join(blocks)
