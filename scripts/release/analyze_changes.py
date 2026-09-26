#!/usr/bin/env python3
"""Analyze git changes and generate categorized changelog summary."""

import subprocess
import sys

from commit_parser import ANALYSIS, ANALYSIS_ORDER, categorize


def run_git(cmd):
    """Run git command and return output."""
    result = subprocess.run(["git"] + cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def categorize_changes(commit_range):
    """Categorize commits by analyzing commit messages and changed files."""
    # Get commit log
    log_cmd = ["log", "--oneline", "--decorate", commit_range]
    log_output = run_git(log_cmd)

    # Get changed files
    files_cmd = ["diff", "--name-only", commit_range]
    files_output = run_git(files_cmd).split("\n") if run_git(files_cmd) else []

    # Categorization relies on conventional commit subjects, scopes included
    categories = categorize(log_output, ANALYSIS)

    # Also check for specific file patterns
    frontend_changes = [f for f in files_output if f.startswith("frontend/")]
    backend_changes = [f for f in files_output if f.startswith("src/")]

    return dict(categories), frontend_changes, backend_changes


def generate_summary(categories, frontend_files, backend_files):
    """Generate markdown summary of changes."""
    lines = ["## Summary of Changes\n"]

    for cat in ANALYSIS_ORDER:
        if cat in categories and categories[cat]:
            lines.append(f"### {cat}")
            for item in categories[cat][:10]:  # Limit to first 10
                lines.append(f"- {item}")
            if len(categories[cat]) > 10:
                lines.append(f"- ... and {len(categories[cat]) - 10} more")
            lines.append("")

    lines.append(f"**Files changed:** {len(frontend_files) + len(backend_files)} total")
    lines.append(f"- Backend files: {len(backend_files)}")
    lines.append(f"- Frontend files: {len(frontend_files)}")

    return "\n".join(lines)


if __name__ == "__main__":
    # Get commit range from args or use default
    commit_range = sys.argv[1] if len(sys.argv) > 1 else "HEAD~10..HEAD"

    try:
        categories, frontend_files, backend_files = categorize_changes(commit_range)
        summary = generate_summary(categories, frontend_files, backend_files)
        print(summary)
    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}", file=sys.stderr)
        sys.exit(1)
