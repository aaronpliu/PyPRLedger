# Version Management Guide

This document describes how to manage versions in PRLedger.

## Version Sources

PRLedger now tracks backend and frontend versions separately:

- **Backend/API version**: `pyproject.toml`
- **Frontend/UI version**: `frontend/package.json`

```toml
[project]
name = "prledger"
version = "1.6.0"  # ← Backend/API version source of truth
```

```json
{
   "name": "frontend",
   "version": "1.1.0"
}
```

All backend runtime locations read from `pyproject.toml`, while the Vue frontend reads from `frontend/package.json` at build time.

## Automatic Version Detection

The backend automatically reads the version from `pyproject.toml` at runtime using Python's `tomllib`:

```python
# src/__init__.py
import tomllib
from pathlib import Path

try:
   pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
   with Path.open(pyproject_path, "rb") as f:
      __version__ = tomllib.load(f).get("project", {}).get("version", "1.0.0-dev")
except Exception:
   __version__ = "1.0.0-dev"
```

This ensures consistency across all parts of the application.

## How to Update Version

### Option 1: Using the Version Bump Script (Recommended)

We provide a convenient script to manage the backend/API version:

```bash
# Show current version
python scripts/bump_version.py show

# Bump major version (1.0.0 -> 2.0.0)
python scripts/bump_version.py major

# Bump minor version (1.5.0 -> 1.6.0)
python scripts/bump_version.py minor

# Bump patch version (1.0.0 -> 1.0.1)
python scripts/bump_version.py patch

# Set a specific version
python scripts/bump_version.py set 1.2.3
```

### Option 2: Manual Update

Edit `pyproject.toml` directly for the backend, and `frontend/package.json` directly for the UI:

```bash
# Backend/API
version = "1.6.0"

# Frontend/UI
"version": "1.1.0"
```

## Semantic Versioning

PRLedger follows [Semantic Versioning](https://semver.org/) (SemVer):

- **MAJOR** version for incompatible changes
- **MINOR** version for backwards-compatible features
- **PATCH** version for backwards-compatible bug fixes

Format: `MAJOR.MINOR.PATCH` (e.g., `1.6.0`)

## Version Release Checklist

When releasing a new version:

1. **Update backend/API version** using the bump script
   ```bash
   python scripts/bump_version.py set 1.6.0
   ```

2. **Update frontend/UI version** in `frontend/package.json`
   ```bash
   # Set package.json version to 1.1.0
   ```

3. **Update CHANGELOG.md** with the new version and changes

4. **Commit the changes**
   ```bash
   git add pyproject.toml frontend/package.json CHANGELOG.md
   git commit -m "Release v1.6.0"
   ```

5. **Create a git tag**
   ```bash
   git tag -a v1.6.0 -m "Version 1.6.0"
   ```

6. **Build and publish** (if applicable)
   ```bash
   pip install build twine
   python -m build
   twine upload dist/*
   ```

7. **Update Docker image tags** (if using Docker)
   ```bash
   docker build -t pypreledger:1.6.0 -t pypreledger:latest .
   docker push pypreledger:latest
   ```

## Development Versions

During development, you can use dev versions:

```bash
# Set a dev version
python scripts/bump_version.py set 1.2.0-dev

# Or with commit hash
python scripts/bump_version.py set 1.2.0-dev+abc123
```

## Checking Version at Runtime

You can check the application version in several ways:

```python
# In Python code
from src import __version__
print(f"Running version {__version__}")

# Via API (when running)
curl http://localhost:8000/api/docs
# Check the version field in the OpenAPI spec
```

## Troubleshooting

### Version shows as "0.1.0-dev"

This happens when the package is not installed. The fallback version is used in development environments. To fix:

```bash
# Install in editable mode
pip install -e .
```

### Version mismatch between files

All files should read from `pyproject.toml`. If you see hardcoded versions anywhere, please report it as a bug.

## Architecture Decision

**Why pyproject.toml?**

- Modern Python standard (PEP 621)
- Single source of truth
- Automatically picked up by packaging tools
- No need to sync multiple files
- Works seamlessly with CI/CD pipelines

**Why not hardcode in multiple places?**

- Error-prone (easy to forget updating one location)
- Violates DRY principle
- Makes automated releases harder
- Increases maintenance burden

---

For more information about version numbering, see [semver.org](https://semver.org).
