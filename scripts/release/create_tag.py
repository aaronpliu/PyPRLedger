#!/usr/bin/env python3
"""Create annotated git tag for release with confirmation."""

import subprocess
import sys


def create_tag(version, auto_confirm=False):
    """Create annotated git tag."""
    tag_name = f"v{version}"
    tag_message = f"Release version {version}"

    print("\nTag Details:")
    print(f"  Name:    {tag_name}")
    print(f"  Message: {tag_message}")

    # Get current commit
    commit_hash, _ = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True
    )
    print(f"  Commit:  {commit_hash.strip()}")

    if auto_confirm:
        print("\nAuto-creating tag (--execute flag)...")
        proceed = True
    else:
        print("\n" + "=" * 40)
        proceed = input("Create annotated tag? (yes/no): ").strip().lower() == "yes"

    if not proceed:
        print("Tag creation cancelled.")
        return 1

    # Create tag
    result = subprocess.run(
        ["git", "tag", "-a", tag_name, "-m", tag_message], capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"Error creating tag: {result.stderr}", file=sys.stderr)
        return 1

    print(f"✓ Tag created: {tag_name}")

    # Show verification
    print("\nVerification:")
    subprocess.run(["git", "tag", "-l", "|", "tail", "-5"], shell=True)
    subprocess.run(["git", "show", tag_name, "--no-patch", "--format='%ai %s'"], shell=True)
    return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: create_tag.py <version> [--execute]")
        print("  --execute: Auto-confirm, no prompt")
        sys.exit(1)

    version = sys.argv[1]
    auto_confirm = "--execute" in sys.argv

    sys.exit(create_tag(version, auto_confirm))


if __name__ == "__main__":
    main()
