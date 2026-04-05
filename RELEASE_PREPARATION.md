# Release Preparation Guide - v1.3.2

## Release Checklist

### ✅ Pre-Release Tasks

#### 1. Version Bump
- [x] Run version bump script: `python scripts/bump_version.py set 1.3.2`
- [x] Verify version updated in `pyproject.toml`: **1.3.2** ✓
- [x] Confirm application reads correct version at runtime
- [x] Update CHANGELOG.md with release notes ✓

#### 2. Documentation Updates
- [x] Updated CHANGELOG.md with v1.3.2 changes ✓
- [x] Documented version bump and continued development ✓

#### 3. Code Changes Summary

##### New Features
- **None in this release** - Maintenance version bump

##### Improvements
- **Version Management** - Continued incremental improvements
  - Patch version bump to 1.3.2 for ongoing development
  - Maintains full backward compatibility with 1.3.x series
  - No breaking changes from previous releases

##### Bug Fixes
- **None in this release** - Focus on version progression

##### Breaking Changes
- **None** - Fully backward compatible with all previous versions

#### 4. Testing Verification
- [ ] Run full test suite: `pytest tests/`
- [ ] Validate API documentation clarity
- [ ] Confirm version display in `/api/docs` and `/health`

#### 5. Database Considerations
- [ ] No schema changes in this release
- [ ] No migration scripts required
- [ ] Existing data fully compatible
- [ ] All database operations unchanged

---

## Release Notes Template

### Version 1.3.2 - April 5, 2026

#### 🎉 New Features

*None in this release - maintenance version bump*

#### 🔧 Improvements

**Version Progression**
- Incremental patch version bump to 1.3.2
- Continues stable development cycle from 1.3.1
- Maintains all features and improvements from previous releases:
  - Multi-reviewer score support (from 1.3.1)
  - Project registry system (from 1.3.0)
  - Enhanced review score update endpoint (from 1.2.0)
  - Logging system and critical bug fixes (from 1.0.1)

#### 🐛 Bug Fixes

*None in this release*

#### ⚠️ Breaking Changes

**None** - This release is fully backward compatible:
- All existing APIs continue to work unchanged
- Database schema unchanged
- No migration required
- Compatible with all 1.3.x clients

#### 📦 Technical Details

**Version Management:**
```bash
# Version bump executed via
python scripts/bump_version.py set 1.3.2

# Single source of truth in pyproject.toml
version = "1.3.2"

# Runtime detection via dynamic TOML parsing
import tomllib
from pathlib import Path
```

**Key Points:**
- **Semantic Versioning**: Follows MAJOR.MINOR.PATCH format
- **Backward Compatibility**: Full compatibility with 1.3.x series
- **No Schema Changes**: Database remains unchanged
- **No Migration Required**: Direct upgrade path available

---

## Deployment Instructions

### Using Docker Compose (Production)

1. **Pull latest changes:**
   ```bash
   git pull origin main
   ```

2. **Rebuild containers:**
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

3. **Verify deployment:**
   ```bash
   docker-compose logs api
   curl http://localhost:8000/health
   # Expected: {"status": "healthy", "version": "1.3.2"}
   ```

### Local Development

1. **Update dependencies (if any):**
   ```bash
   pip install -r requirements/dev.txt
   ```

2. **Start application:**
   ```bash
   uvicorn src.main:app --reload
   ```

3. **Verify version:**
   ```bash
   curl http://localhost:8000/health
   python scripts/bump_version.py show
   ```

---

## Rollback Plan

If issues are encountered after deployment:

1. **Revert to previous version:**
   ```bash
   git checkout <previous-tag>
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

2. **Database rollback:** Not required (no schema changes)

3. **Report issues:** Document any issues in issue tracker for investigation

---

## Post-Release Tasks

- [ ] Monitor application logs for errors
- [ ] Check Prometheus metrics for anomalies
- [ ] Verify all endpoints functioning correctly
- [ ] Update any external documentation or wikis
- [ ] Notify team/stakeholders of release
- [ ] Create GitHub release with changelog notes
- [ ] Tag commit with version: `git tag v1.3.2 && git push origin v1.3.2`

---

## Contributors

- Core development and maintenance
- Version management and release preparation

---

**Release Date:** April 5, 2026  
**Version:** 1.3.2  
**Status:** Ready for Release ✅
