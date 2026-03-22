#!/usr/bin/env python3
"""
Version management script for PRLedger

This script provides easy version bumping capabilities following semantic versioning.
The version is maintained in a single source of truth: pyproject.toml

Usage:
    python scripts/bump_version.py major  # Bump major version (1.0.0 -> 2.0.0)
    python scripts/bump_version.py minor  # Bump minor version (1.0.0 -> 1.1.0)
    python scripts/bump_version.py patch  # Bump patch version (1.0.0 -> 1.0.1)
    python scripts/bump_version.py show   # Show current version
    python scripts/bump_version.py set X.Y.Z  # Set specific version
"""

import re
import sys
from pathlib import Path


def get_project_root():
    """Get the project root directory"""
    return Path(__file__).parent.parent


def read_version():
    """Read current version from pyproject.toml"""
    pyproject_path = get_project_root() / "pyproject.toml"
    content = pyproject_path.read_text()
    
    # Match version line in pyproject.toml
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if match:
        return match.group(1)
    raise ValueError("Version not found in pyproject.toml")


def write_version(new_version):
    """Write new version to pyproject.toml"""
    pyproject_path = get_project_root() / "pyproject.toml"
    content = pyproject_path.read_text()
    
    # Replace version line
    new_content = re.sub(
        r'^(version\s*=\s*)"[^"]+"',
        f'\\1"{new_version}"',
        content,
        flags=re.MULTILINE
    )
    
    pyproject_path.write_text(new_content)
    print(f"✓ Updated version in pyproject.toml to {new_version}")


def parse_version(version_str):
    """Parse version string into components"""
    parts = version_str.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {version_str}. Expected X.Y.Z")
    return [int(p) for p in parts]


def bump_version(bump_type):
    """Bump version by type (major, minor, or patch)"""
    current_version = read_version()
    major, minor, patch = parse_version(current_version)
    
    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}. Use 'major', 'minor', or 'patch'")
    
    new_version = f"{major}.{minor}.{patch}"
    write_version(new_version)
    return new_version


def set_version(version_str):
    """Set a specific version"""
    # Validate version format
    parse_version(version_str)
    write_version(version_str)
    return version_str


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    try:
        if command == "show":
            version = read_version()
            print(f"Current version: {version}")
        
        elif command in ["major", "minor", "patch"]:
            new_version = bump_version(command)
            print(f"✓ Bumped {command} version: {read_version()}")
        
        elif command == "set":
            if len(sys.argv) < 3:
                print("Error: Please specify version number (e.g., 'set 1.2.3')")
                sys.exit(1)
            new_version = set_version(sys.argv[2])
            print(f"✓ Set version to: {new_version}")
        
        else:
            print(f"Error: Unknown command '{command}'")
            print(__doc__)
            sys.exit(1)
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
