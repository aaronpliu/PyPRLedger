#!/usr/bin/env python3
"""Update CHANGELOG.md with new release section."""

import sys
from datetime import datetime
from pathlib import Path


def update_changelog(backend_version, frontend_version, changes_summary):
    """Prepend new release section to CHANGELOG.md."""
    changelog_path = Path("CHANGELOG.md")
    if not changelog_path.exists():
        print("Error: CHANGELOG.md not found", file=sys.stderr)
        sys.exit(1)

    content = changelog_path.read_text()

    # Find the position after the header and before first release
    # Look for the first "## [" pattern (release header)
    lines = content.split("\n")
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("## ["):
            insert_idx = i
            break

    today = datetime.now().strftime("%Y-%m-%d")

    new_section = f"""## [{backend_version}] - {today}

**Backend Version**: {backend_version}
**Frontend Version**: {frontend_version}

{changes_summary}

---

"""

    lines.insert(insert_idx, new_section)
    changelog_path.write_text("\n".join(lines))
    print(f"✓ Updated CHANGELOG.md with v{backend_version}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Usage: update_changelog.py <backend_version> <frontend_version> [changes_summary_file]"
        )
        sys.exit(1)

    backend_ver = sys.argv[1]
    frontend_ver = sys.argv[2]
    summary_file = sys.argv[3] if len(sys.argv) > 3 else None

    if summary_file:
        summary = Path(summary_file).read_text()
    else:
        summary = "### Features\n- TBD\n\n### Bug Fixes\n- TBD"

    update_changelog(backend_ver, frontend_ver, summary)
