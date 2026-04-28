#!/usr/bin/env python3
"""Get current backend and frontend versions."""

import json
import subprocess
import sys
from pathlib import Path


def get_backend_version():
    """Get backend version from pyproject.toml."""
    try:
        result = subprocess.run(
            ["python", "scripts/bump_version.py", "show"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error getting backend version: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def get_frontend_version():
    """Get frontend version from package.json."""
    try:
        pkg_path = Path("frontend/package.json")
        if not pkg_path.exists():
            return None
        with pkg_path.open() as f:
            pkg = json.load(f)
        return pkg.get("version")
    except Exception as e:
        print(f"Error reading frontend/package.json: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    backend = get_backend_version()
    frontend = get_frontend_version()
    print(f"Backend: {backend}")
    print(f"Frontend: {frontend or 'N/A'}")
