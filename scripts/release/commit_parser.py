#!/usr/bin/env python3
"""Parse conventional-commit subjects into changelog categories.

Shared by ``analyze_changes.py`` and ``update_changelog.py`` so both scripts
understand the scoped style used across this repository, e.g.
``feat(release): support bitbucket cloud platform``.
"""

import re


# conventional type -> (changelog category, analysis category)
TYPE_CATEGORIES = {
    "feat": ("Added", "Features"),
    "feature": ("Added", "Features"),
    "fix": ("Fixed", "Bug Fixes"),
    "perf": ("Improved", "Improvements"),
    "improve": ("Improved", "Improvements"),
    "impr": ("Improved", "Improvements"),
    "refactor": ("Changed", "Improvements"),
    "style": ("Changed", "Improvements"),
    "styles": ("Changed", "Improvements"),
    "docs": ("Documentation", "Documentation"),
    "doc": ("Documentation", "Documentation"),
    "chore": ("Dependencies", "Dependencies"),
    "build": ("Dependencies", "Dependencies"),
    "ci": ("Dependencies", "Dependencies"),
    "deps": ("Dependencies", "Dependencies"),
    "test": ("Tests", "Tests"),
    "tests": ("Tests", "Tests"),
    "revert": ("Reverted", "Reverted"),
    "breaking": ("Breaking Changes", "Breaking Changes"),
}

# Changelog sections in display order
CHANGELOG_ORDER = [
    "Added",
    "Fixed",
    "Improved",
    "Changed",
    "Tests",
    "Documentation",
    "Dependencies",
    "Reverted",
    "Breaking Changes",
    "Other Changes",
]

# Analysis sections in display order
ANALYSIS_ORDER = [
    "Features",
    "Bug Fixes",
    "Improvements",
    "Tests",
    "Documentation",
    "Dependencies",
    "Reverted",
    "Breaking Changes",
    "Other Changes",
]

# Prefix applied to a description depending on its commit type
TYPE_PREFIX = {
    "refactor": "[Refactor]",
    "style": "[Style]",
    "styles": "[Style]",
    "test": "[Test]",
    "tests": "[Test]",
    "perf": "[Perf]",
}

# CHANGELOG index / ANALYSIS index
CHANGELOG, ANALYSIS = 0, 1

# "abc1234 (HEAD -> main) feat(release)!: support cloud" / "feat: something"
_COMMIT_RE = re.compile(
    r"^(?P<hash>[0-9a-f]{7,40})\s+"
    r"(?:\((?P<refs>[^)]*)\)\s+)?"
    r"(?P<type>[a-zA-Z]+)"
    r"(?:\((?P<scope>[^)]*)\))?"
    r"(?P<breaking>!)?"
    r":\s*(?P<description>.+)$"
)


def parse_subject(line):
    """Parse a git log subject line.

    Returns:
        ``(commit_type | None, description, breaking)``. ``commit_type`` is
        ``None`` when the subject does not follow the conventional-commit style.
    """
    match = _COMMIT_RE.match(line.strip())
    if not match:
        return None, line.strip(), False

    commit_type = match.group("type").lower()
    description = match.group("description").strip()
    if description:
        description = description[0].upper() + description[1:]

    if commit_type not in TYPE_CATEGORIES:
        return None, description, False

    return commit_type, description, bool(match.group("breaking"))


def decorate(commit_type, description):
    """Prefix a description with a hint for style/test/perf commits."""
    prefix = TYPE_PREFIX.get(commit_type)
    return f"{prefix} {description}" if prefix else description


def categorize(log_output, index=CHANGELOG):
    """Group git log lines by their category.

    Args:
        log_output: raw output of ``git log --oneline``
        index: ``CHANGELOG`` or ``ANALYSIS`` section naming

    Returns:
        ``{category: [description, ...]}``
    """
    categories = {}
    for raw in log_output.split("\n"):
        line = raw.strip()
        if not line:
            continue

        commit_type, description, breaking = parse_subject(line)
        if commit_type is None:
            categories.setdefault("Other Changes", []).append(strip_hash(line))
            continue
        if breaking:
            categories.setdefault("Breaking Changes", []).append(description)
            continue

        category = TYPE_CATEGORIES[commit_type][index]
        categories.setdefault(category, []).append(decorate(commit_type, description))

    return categories


def strip_hash(line):
    """Drop the hash/decorations from a git log line for readable output."""
    match = _COMMIT_RE.match(line.strip())
    if match:
        return match.group("description").strip()
    parts = line.strip().split(" ", 1)
    return parts[1].strip() if len(parts) > 1 else line.strip()
