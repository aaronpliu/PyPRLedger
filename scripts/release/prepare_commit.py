#!/usr/bin/env python3
"""Prepare and optionally execute commit with user confirmation."""

import subprocess
import sys


def run_cmd(cmd, capture=False):
    """Run shell command."""
    if capture:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.returncode
    else:
        result = subprocess.run(cmd, shell=True)
        return result.returncode


def get_git_status():
    """Get git status output."""
    stdout, _ = run_cmd("git status", capture=True)
    return stdout


def get_changed_files():
    """Get list of changed files."""
    stdout, _ = run_cmd("git diff --name-only", capture=True)
    return [f for f in stdout.split("\n") if f]


def get_commit_hash():
    """Get current HEAD commit hash."""
    stdout, _ = run_cmd("git rev-parse --short HEAD", capture=True)
    return stdout


def prepare_commit_message(backend_version, frontend_version):
    """Generate commit message."""
    return f"""Release v{backend_version}

- Bump backend version to {backend_version}
- Bump frontend version to {frontend_version}
- Update CHANGELOG.md
- Synchronize dependencies"""


def execute_commit(backend_version, frontend_version):
    """Execute git add and git commit."""
    commit_msg = prepare_commit_message(backend_version, frontend_version)

    print("Staging changes...")
    if run_cmd("git add .") != 0:
        print("Error: git add failed", file=sys.stderr)
        return False

    print("Creating commit...")
    result = subprocess.run(["git", "commit", "-m", commit_msg], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        return False

    print("✓ Commit created")
    print(result.stdout)
    return True


def main():
    if len(sys.argv) < 3:
        print("Usage: prepare_commit.py <backend_version> <frontend_version> [--execute]")
        print("  --execute: Automatically run git add and git commit after showing preview")
        sys.exit(1)

    backend_ver = sys.argv[1]
    frontend_ver = sys.argv[2]
    auto_execute = "--execute" in sys.argv

    print("\n" + "=" * 60)
    print("PREPARE COMMIT")
    print("=" * 60)

    # Show status
    print("\n1. Current git status:")
    print("-" * 40)
    print(get_git_status())

    # Show changed files
    files = get_changed_files()
    print(f"\n2. Files to be committed ({len(files)}):")
    print("-" * 40)
    for f in files:
        print(f"  {f}")

    # Show commit message
    commit_msg = prepare_commit_message(backend_ver, frontend_ver)
    print("\n3. Commit message:")
    print("-" * 40)
    print(commit_msg)

    print("\n" + "=" * 60)

    if auto_execute:
        print("AUTO-EXECUTING commit (--execute flag)...")
        success = execute_commit(backend_ver, frontend_ver)
        sys.exit(0 if success else 1)
    else:
        print("ACTIONS REQUIRED:")
        print("  1. Stage changes:  git add .")
        print("  2. Create commit:  git commit -m 'Release v{backend_ver}...'")
        print("\nOr run with --execute to automate (will prompt before committing).")
        print("=" * 60)


if __name__ == "__main__":
    main()
