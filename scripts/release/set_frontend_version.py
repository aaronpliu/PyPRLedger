#!/usr/bin/env python3
"""Set frontend version in package.json."""

import json
import sys
from pathlib import Path


def set_frontend_version(version: str):
    """Update version in frontend/package.json."""
    pkg_path = Path("frontend/package.json")
    if not pkg_path.exists():
        print(f"Error: {pkg_path} not found", file=sys.stderr)
        sys.exit(1)

    with pkg_path.open() as f:
        pkg = json.load(f)

    old_version = pkg.get("version")
    pkg["version"] = version

    with pkg_path.open("w") as f:
        json.dump(pkg, f, indent=2)
        f.write("\n")

    print(f"Frontend version: {old_version} → {version}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: set_frontend_version.py <version>")
        sys.exit(1)

    set_frontend_version(sys.argv[1])
