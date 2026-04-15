# Quick Reference: Version Management

## 🚀 Quick Start

**To release a new backend version, run:**

```bash
# Set backend/API version
python3 scripts/bump_version.py set 1.6.0
```

Then update `frontend/package.json` for the UI version, for example `1.1.0`.

---

## 📋 Common Commands

| Task | Command |
|------|---------|
| Show current version | `python3 scripts/bump_version.py show` |
| Bump major version | `python3 scripts/bump_version.py major` |
| Bump minor version | `python3 scripts/bump_version.py minor` |
| Bump patch version | `python3 scripts/bump_version.py patch` |
| Set backend/API version | `python3 scripts/bump_version.py set 1.6.0` |

---

## 🎯 Release Checklist

```bash
# 1. Update backend/API version
python3 scripts/bump_version.py set 1.6.0

# 2. Update frontend/UI version
# Edit frontend/package.json and set "version": "1.1.0"

# 3. Verify the change
cat pyproject.toml | grep version

# 4. Update CHANGELOG.md
# Edit and document changes

# 5. Commit
git add pyproject.toml frontend/package.json CHANGELOG.md
git commit -m "Release v1.6.0"

# 6. Tag
git tag -a v1.6.0 -m "Version 1.6.0"
```

---

## ℹ️ Where is the Version Stored?

**Backend source of truth:** `pyproject.toml`  
**Frontend source of truth:** `frontend/package.json`

```toml
[project]
version = "1.6.0"  # ← Backend/API version
```

```json
{
	"version": "1.1.0"
}
```

---

## 🔍 Checking Version in Code

```python
from src import __version__
print(f"Running PRLedger v{__version__}")
```

---

## 🐛 Troubleshooting

**Q: Version shows as "0.1.0-dev"**  
A: Install the package: `pip install -e .`

**Q: Need to update multiple files?**  
A: No! Just update `pyproject.toml` only.

---

## 📚 Full Documentation

See [VERSIONING.md](VERSIONING.md) for complete guide.
