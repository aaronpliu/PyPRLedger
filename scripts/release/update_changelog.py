#!/usr/bin/env python3
"""Update CHANGELOG.md with new release section from git commits."""

import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def run_git(cmd):
    """Run git command and return output."""
    result = subprocess.run(["git"] + cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def get_previous_version_tag(backend_version):
    """Find the most recent tag before the current version."""
    try:
        # Get all tags sorted by version, find the one before current
        tags = run_git(["tag", "--list", "v*", "--sort=-v:refname"]).split("\n")
        current_ver_parts = [int(x) for x in backend_version.split(".")]

        for tag in tags:
            if tag.startswith("v"):
                tag_ver = tag[1:]
                try:
                    tag_parts = [int(x) for x in tag_ver.split(".")]
                    # Compare versions
                    if tag_parts < current_ver_parts:
                        return tag
                except ValueError:
                    continue
    except Exception:
        pass
    return None


def categorize_commits(commit_range):
    """Categorize commits by analyzing commit messages."""
    # Use --no-decorate to avoid branch/tag info in output
    log_cmd = ["log", "--oneline", "--no-decorate", commit_range]
    log_output = run_git(log_cmd)

    categories = defaultdict(list)

    for line in log_output.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Extract commit message (skip hash)
        parts = line.split(" ", 1)
        if len(parts) < 2:
            categories["Other Changes"].append(line)
            continue
        message = parts[1]

        # Categorize based on conventional commit prefixes
        if message.startswith("feat:"):
            categories["Added"].append(message[5:].strip())
        elif message.startswith("fix:"):
            categories["Fixed"].append(message[4:].strip())
        elif message.startswith("improve:") or message.startswith("impr:"):
            categories["Improved"].append(message.split(":", 1)[1].strip())
        elif message.startswith("docs:") or message.startswith("doc:"):
            categories["Documentation"].append(message.split(":", 1)[1].strip())
        elif message.startswith("refactor:"):
            categories["Changed"].append(f"[Refactor] {message.split(':', 1)[1].strip()}")
        elif message.startswith("chore:") or message.startswith("build:"):
            categories["Dependencies"].append(message.split(":", 1)[1].strip())
        elif message.startswith("breaking:"):
            categories["Breaking Changes"].append(message.split(":", 1)[1].strip())
        else:
            categories["Other Changes"].append(line)

    return dict(categories)


def generate_changelog_entry(backend_version, frontend_version, categories):
    """Generate formatted changelog entry from categorized changes."""
    today = datetime.now().strftime("%Y-%m-%d")

    lines = [
        f"## [{backend_version}] - {today}",
        "",
        f"**Backend Version**: {backend_version}",
        f"**Frontend Version**: {frontend_version}",
        "",
    ]

    # Order of categories
    category_order = [
        "Added",
        "Fixed",
        "Improved",
        "Changed",
        "Documentation",
        "Dependencies",
        "Breaking Changes",
        "Other Changes",
    ]

    has_content = False

    for cat in category_order:
        if cat in categories and categories[cat]:
            has_content = True
            lines.append(f"### {cat}")
            for item in categories[cat]:
                # Clean up commit message formatting
                item = item.strip()
                # Remove issue references like (#123) for cleaner changelog
                if " (#" in item:
                    item = item.split(" (#")[0].strip()
                lines.append(f"- {item}")
            lines.append("")

    if not has_content:
        lines.append("### Other\n- No significant changes documented\n")
        lines.append("")

    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def update_changelog(backend_version, frontend_version):
    """Prepend new release section to CHANGELOG.md."""
    changelog_path = Path("CHANGELOG.md")
    if not changelog_path.exists():
        print("Error: CHANGELOG.md not found", file=sys.stderr)
        sys.exit(1)

    content = changelog_path.read_text()
    lines = content.split("\n")

    # Check if version already exists, if so remove it first
    version_heading = f"## [{backend_version}]"
    existing_idx = None
    for i, line in enumerate(lines):
        if line.startswith(version_heading):
            existing_idx = i
            break

    # Determine commit range for this release
    prev_tag = get_previous_version_tag(backend_version)
    commit_range = f"{prev_tag}..HEAD" if prev_tag else "HEAD~20..HEAD"

    # Categorize commits
    categories = categorize_commits(commit_range)

    # Generate new section
    today = datetime.now().strftime("%Y-%m-%d")
    new_section_lines = [
        f"## [{backend_version}] - {today}",
        "",
        f"**Backend Version**: {backend_version}",
        f"**Frontend Version**: {frontend_version}",
        "",
    ]

    # Order of categories
    category_order = [
        "Added",
        "Fixed",
        "Improved",
        "Changed",
        "Documentation",
        "Dependencies",
        "Breaking Changes",
        "Other Changes",
    ]

    has_content = False
    for cat in category_order:
        if cat in categories and categories[cat]:
            has_content = True
            new_section_lines.append(f"### {cat}")
            for item in categories[cat]:
                # Clean up commit message formatting
                item = item.strip()
                # Remove issue references like (#123) for cleaner changelog
                if " (#" in item:
                    item = item.split(" (#")[0].strip()
                new_section_lines.append(f"- {item}")
            new_section_lines.append("")

    if not has_content:
        new_section_lines.append("### Other")
        new_section_lines.append("- No significant changes documented")
        new_section_lines.append("")

    new_section_lines.append("---")
    new_section_lines.append("")

    new_section = "\n".join(new_section_lines)

    if existing_idx is not None:
        # Remove existing entry (including its content until next "## [" or "---")
        end_idx = existing_idx + 1
        while end_idx < len(lines):
            if lines[end_idx].startswith("## [") or (
                lines[end_idx].strip() == "---" and end_idx > existing_idx
            ):
                # Check if next non-empty line is a new version heading
                next_idx = end_idx + 1
                while next_idx < len(lines) and not lines[next_idx].strip():
                    next_idx += 1
                if next_idx < len(lines) and lines[next_idx].startswith("## ["):
                    break
                # If we hit a "---" that's followed by another version, that's the boundary
                if lines[end_idx].strip() == "---":
                    # Look ahead to see if next non-empty line is a version heading
                    next_content_idx = end_idx + 1
                    while next_content_idx < len(lines) and not lines[next_content_idx].strip():
                        next_content_idx += 1
                    if next_content_idx < len(lines) and lines[next_content_idx].startswith("## ["):
                        break
            end_idx += 1

        # Replace the section
        lines[existing_idx:end_idx] = [new_section]
    else:
        # Find insert position (after header, before first release)
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("## ["):
                insert_idx = i
                break
        lines.insert(insert_idx, new_section)

    changelog_path.write_text("\n".join(lines))
    print(f"✓ Updated CHANGELOG.md with v{backend_version}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: update_changelog.py <backend_version> <frontend_version>")
        sys.exit(1)

    backend_ver = sys.argv[1]
    frontend_ver = sys.argv[2]

    update_changelog(backend_ver, frontend_ver)
