# Version Management Guide

This document describes how to manage versions in PRLedger.

## Single Source of Truth

The project version is maintained in **one place only**: `pyproject.toml`

```toml
[project]
name = "pycodereviewsaver"
version = "1.0.0"  # ← This is the single source of truth
```

All other locations (src/__init__.py, src/main.py, etc.) read the version dynamically from this file.

## Automatic Version Detection

The application automatically reads the version from `pyproject.toml` at runtime using Python's `importlib.metadata`:

```python
# src/__init__.py
import importlib.metadata

try:
    __version__ = importlib.metadata.version("pycodereviewsaver")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.1.0-dev"  # Fallback for development
```

This ensures consistency across all parts of the application.

## How to Update Version

### Option 1: Using the Version Bump Script (Recommended)

We provide a convenient script to manage versions:

```bash
# Show current version
python scripts/bump_version.py show

# Bump major version (1.0.0 -> 2.0.0)
python scripts/bump_version.py major

# Bump minor version (1.0.0 -> 1.1.0)
python scripts/bump_version.py minor

# Bump patch version (1.0.0 -> 1.0.1)
python scripts/bump_version.py patch

# Set a specific version
python scripts/bump_version.py set 1.2.3
```

### Option 2: Manual Update

Edit `pyproject.toml` directly:

```bash
# Open pyproject.toml and update the version line
version = "1.0.1"
```

## Semantic Versioning

PRLedger follows [Semantic Versioning](https://semver.org/) (SemVer):

- **MAJOR** version for incompatible changes
- **MINOR** version for backwards-compatible features
- **PATCH** version for backwards-compatible bug fixes

Format: `MAJOR.MINOR.PATCH` (e.g., `1.0.0`)

## Version Release Checklist

When releasing a new version:

1. **Update version** using the bump script
   ```bash
   python scripts/bump_version.py minor
   ```

2. **Update CHANGELOG.md** with the new version and changes

3. **Commit the changes**
   ```bash
   git add pyproject.toml CHANGELOG.md
   git commit -m "Release version 1.1.0"
   ```

4. **Create a git tag**
   ```bash
   git tag -a v1.1.0 -m "Version 1.1.0"
   git push origin v1.1.0
   ```

5. **Build and publish** (if applicable)
   ```bash
   pip install build twine
   python -m build
   twine upload dist/*
   ```

6. **Update Docker image tags** (if using Docker)
   ```bash
   docker build -t pypreledger:1.1.0 -t pypreledger:latest .
   docker push pypreledger:1.1.0
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
