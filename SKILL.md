# Version Publish Skill

This document provides instructions for releasing and publishing new versions of PyPRLedger.

## Overview

PyPRLedger uses semantic versioning (SemVer) with the version stored in `pyproject.toml` as the single source of truth. Publishing involves bumping the version, updating changelog, tagging, building, and uploading to PyPI.

## Prerequisites

- PyPI account with API token configured (typically in `~/.pypirc`)
- Build tools installed: `pip install build twine`

## Release Workflow

### Step 1: Update Version

```bash
# Bump version (major, minor, or patch)
python scripts/bump_version.py minor  # 1.3.2 -> 1.4.0

# Or set specific version directly
python scripts/bump_version.py set 1.4.0
```

### Step 2: Update CHANGELOG.md

Edit `CHANGELOG.md`:
1. Move unreleased changes to new version section
2. Add release date in `[X.Y.Z] - YYYY-MM-DD` format
3. Use categories: Added, Changed, Deprecated, Removed, Fixed, Security

### Step 3: Commit Changes

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "Release version 1.4.0"
```

### Step 4: Create Git Tag

```bash
git tag -a v1.4.0 -m "Version 1.4.0"
```

### Step 5: Build Package

```bash
python -m build
```

This creates distribution files in `dist/` directory.

### Step 6: Upload to PyPI

```bash
twine upload dist/*
```

### Step 7: Push to Remote

```bash
git push origin main
git push origin v1.4.0
```

## Complete One-Liner

```bash
python scripts/bump_version.py set 1.4.0 && \
  git add pyproject.toml CHANGELOG.md && \
  git commit -m "Release version 1.4.0" && \
  git tag -a v1.4.0 -m "Version 1.4.0" && \
  python -m build && \
  twine upload dist/* && \
  git push origin main && \
  git push origin v1.4.0
```

## Docker Image Publishing (Optional)

```bash
docker build -t prledger:1.4.0 -t prledger:latest .
docker tag prledger:1.4.0 ghcr.io/aaronpliu/prledger:1.4.0
docker push ghcr.io/aaronpliu/prledger:1.4.0
docker push ghcr.io/aaronpliu/prledger:latest
```

## Troubleshooting

### "File already exists" on PyPI upload
Increment version and rebuild.

### Version not found at runtime
Ensure package is installed: `pip install -e .`

### Authentication errors
Check `~/.pypirc` configuration:

```ini
[pypi]
username = __token__
password = pypi-xxxxxxxxxxxxxxxxxxxx
```