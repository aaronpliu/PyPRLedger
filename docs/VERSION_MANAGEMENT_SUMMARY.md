# Version Management Implementation Summary

## Overview

Version management now uses **two explicit sources of truth**:

- `pyproject.toml` for the backend/API version
- `frontend/package.json` for the frontend/UI version

## What Changed

### Before (❌ Stale and Mixed Version Sources)
```
pyproject.toml        → version = "0.1.0"
src/__init__.py       → __version__ = "1.0.0"
src/main.py           → version="1.0.0"
src/api/__init__.py   → __version__ = "1.0.0"
frontend/package.json → version = "1.0.0"
```

### After (✅ Explicit Backend and Frontend Sources)
```
pyproject.toml        → version = "1.6.0" (BACKEND/API SOURCE OF TRUTH)
frontend/package.json → version = "1.1.0" (FRONTEND/UI SOURCE OF TRUTH)
src/__init__.py       → reads from pyproject.toml via tomllib
src/main.py           → imports __version__ from src.__init__
frontend/src/config/versions.ts → reads UI version from package.json
```

## Files Modified

### 1. `src/__init__.py`
- Now uses `tomllib` to read version from `pyproject.toml`
- Includes fallback to `"1.0.0-dev"` for development environments
- Removed hardcoded version string

### 2. `src/main.py`
- Changed from hardcoded `version="1.0.0"` to `version=__version__`
- Imports version automatically from `src.__init__`

### 3. `scripts/bump_version.py` (NEW)
- Automated version bumping script
- Supports major, minor, patch bumps
- Can set specific versions
- Follows semantic versioning

### 4. `VERSIONING.md` (NEW)
- Comprehensive documentation on version management
- Usage examples and troubleshooting
- Release checklist

### 5. `README.md`
- Added version reference in header
- Points to `pyproject.toml` and bump script

### 6. `frontend/package.json`
- Stores the UI release version
- Consumed by `frontend/src/config/versions.ts` at build time

## How to Use

### Check Current Version
```bash
python3 scripts/bump_version.py show
```

### Bump Version
```bash
# Major release (1.5.0 → 2.0.0)
python3 scripts/bump_version.py major

# Minor release (1.5.0 → 1.6.0)
python3 scripts/bump_version.py minor

# Patch release (1.0.0 → 1.0.1)
python3 scripts/bump_version.py patch
```

### Set Specific Version
```bash
python3 scripts/bump_version.py set 1.2.3
```

### Manual Update
Edit `pyproject.toml` directly:
```toml
[project]
version = "1.2.3"
```

## Installation

For the version to be correctly detected at runtime, install the package:

```bash
# Development mode (editable)
pip install -e .

# Production mode
pip install .
```

After installation, you can access the version:
```python
from src import __version__
print(__version__)
```

## Benefits

✅ **Clear Ownership**: Backend and frontend versions are updated in their own package metadata
✅ **DRY Principle**: No duplication of backend runtime version strings
✅ **Automated Releases**: Easy version bumping with scripts
✅ **Consistency**: Backend runtime and OpenAPI use the same API version automatically
✅ **Modern Standard**: Follows PEP 621 and Python packaging best practices
✅ **CI/CD Friendly**: Easy to integrate with automated release pipelines

## Architecture

```
┌─────────────────┐
│ pyproject.toml  │ ← Backend/API source
│  version =      │
└────────┬────────┘
         │
         ├──────────────────────────────┐
         │                              │
    ┌────▼─────────┐           ┌────────▼────────┐
    │ tomllib      │           │ pip install -e .│
    │ file reader  │           │ (reads during   │
    └────┬─────────┘           │  installation)  │
         │                     └─────────────────┘
    ┌────▼─────────┐
    │ src/__init__ │
    │ __version__  │
    └────┬─────────┘
         │
    ┌────▼─────────┐
    │ src/main.py  │
    │ FastAPI app  │
    └──────────────┘

frontend/package.json → frontend/src/config/versions.ts → UI version label
```

## Troubleshooting

### Version shows as "0.1.0-dev"
This is normal in development mode if the package is not installed. Install it:
```bash
pip install -e .
```

### Need to update multiple places?
No! Just update `pyproject.toml` and everything else updates automatically.

## Migration Notes

If you have existing hardcoded versions in other files, please remove them and update to use the centralized version system.

## References

- [PEP 621](https://peps.python.org/pep-0621/) - Managing project metadata
- [Semantic Versioning](https://semver.org/) - Version numbering standard
- [importlib.metadata](https://docs.python.org/3/library/importlib.metadata.html) - Reading package metadata
