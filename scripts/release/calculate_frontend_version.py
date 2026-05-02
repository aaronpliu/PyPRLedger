#!/usr/bin/env python3
"""Calculate frontend version from backend version according to convention."""

import sys

from packaging import version


def calculate_frontend_version(backend_version: str) -> str:
    """
    Calculate frontend version from backend version.
    Convention: frontend minor = backend minor + 1
    Example: backend 1.8.0 -> frontend 1.9.0
    """
    v = version.parse(backend_version)
    if not isinstance(v, version.Version):
        raise ValueError(f"Invalid version format: {backend_version}")

    # Frontend minor = backend minor + 1
    frontend_minor = v.minor + 1
    return f"{v.major}.{frontend_minor}.{v.micro}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: calculate_frontend_version.py <backend_version>")
        sys.exit(1)

    backend_ver = sys.argv[1]
    try:
        frontend_ver = calculate_frontend_version(backend_ver)
        print(frontend_ver)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
