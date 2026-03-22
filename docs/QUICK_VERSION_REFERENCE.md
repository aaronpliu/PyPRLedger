# Quick Reference: Version Management

## 🚀 Quick Start

**To release a new version, just run one command:**

```bash
# Bump minor version (e.g., 1.0.0 → 1.1.0)
python3 scripts/bump_version.py minor
```

That's it! The version is automatically updated everywhere.

---

## 📋 Common Commands

| Task | Command |
|------|---------|
| Show current version | `python3 scripts/bump_version.py show` |
| Bump major version | `python3 scripts/bump_version.py major` |
| Bump minor version | `python3 scripts/bump_version.py minor` |
| Bump patch version | `python3 scripts/bump_version.py patch` |
| Set specific version | `python3 scripts/bump_version.py set 2.1.0` |

---

## 🎯 Release Checklist

```bash
# 1. Update version
python3 scripts/bump_version.py minor

# 2. Verify the change
cat pyproject.toml | grep version

# 3. Update CHANGELOG.md
# Edit and document changes

# 4. Commit
git add pyproject.toml CHANGELOG.md
git commit -m "Release version 1.1.0"

# 5. Tag
git tag -a v1.1.0 -m "Version 1.1.0"
git push origin v1.1.0
```

---

## ℹ️ Where is the Version Stored?

**Single source of truth:** `pyproject.toml`

```toml
[project]
version = "1.0.0"  # ← Only update this file
```

All other files read from here automatically.

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
