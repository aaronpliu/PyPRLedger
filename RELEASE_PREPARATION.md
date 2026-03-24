# Release Preparation Guide - v1.1.0

## Release Checklist

### ✅ Pre-Release Tasks

#### 1. Version Bump
- [x] Run version bump script: `python scripts/bump_version.py set 1.1.0`
- [x] Verify version updated in `pyproject.toml`: **1.1.0** ✓
- [x] Confirm application reads correct version: **1.1.0** ✓
- [x] Update CHANGELOG.md with release notes ✓

#### 2. Documentation Updates
- [x] Updated CHANGELOG.md with v1.1.0 changes ✓
- [x] Documented new features and fixes ✓
- [x] Updated version history summary table ✓

#### 3. Code Changes Summary

##### New Features
- **Enhanced Review Score Update Endpoint** (`PUT /api/v1/reviews/score`)
  - Complete composite key-based record identification
  - Mandatory parameters: `project_key`, `repository_slug`, `pull_request_id`, `reviewer`, `source_filename`, `score`
  - In-place score update without creating new iterations
  - Prevents cross-project/cross-repository data collisions

- **Improved Version Management**
  - Direct reading from `pyproject.toml` using Python's `tomllib`
  - No package installation required for development
  - Single source of truth maintained
  - Automatic fallback to `1.0.0-dev` on errors

##### Bug Fixes
- **SQLAlchemy Boolean Query Syntax**
  - Fixed all `column == True` comparisons to `column.is_(True)`
  - Resolves "Review not found" errors in boolean filtering
  - Applied to all `is_latest_review` queries across review service

- **API Route Ordering**
  - Reorganized endpoints to prevent route matching conflicts
  - Moved `/score` before parameterized routes like `/{pull_request_id}`

##### Breaking Changes
- **Review Score Update API**
  - `source_filename` parameter is now **mandatory** (was optional)
  - All 5 composite key fields must be provided for score updates
  - Ensures precise record targeting and data integrity

#### 4. Testing Verification
- [ ] Run full test suite: `pytest tests/`
- [ ] Verify API endpoints manually or with Postman
- [ ] Test score update endpoint with all required parameters
- [ ] Confirm boolean query fixes resolve previous errors
- [ ] Validate version display in `/api/docs` and `/health`

#### 5. Database Considerations
- [ ] No schema changes in this release
- [ ] No migration scripts required
- [ ] Existing data fully compatible

---

## Release Notes Template

### Version 1.1.0 - March 25, 2026

#### 🎉 New Features

**Enhanced Review Score Update Endpoint**
- Introduced dedicated `PUT /api/v1/reviews/score` endpoint for precise score updates
- Uses complete business key combination for record identification:
  - `project_key` - Project identifier (e.g., "ECOM")
  - `repository_slug` - Repository slug (e.g., "frontend-store")
  - `pull_request_id` - Pull request ID (e.g., "pr-123")
  - `source_filename` - Source filename being reviewed (mandatory)
  - `reviewer` - Reviewer username (e.g., "john_doe")
  - `score` - New score value (0-10)
- Performs in-place score updates without creating new iterations
- Prevents data collisions across projects and repositories
- All parameters mandatory to ensure precise record targeting

**Improved Version Management**
- Direct version reading from `pyproject.toml` using Python's built-in `tomllib`
- No longer requires package installation (`pip install -e .`) for version detection
- Works seamlessly in pure development mode with `uvicorn src.main:app --reload`
- Single source of truth maintained in `pyproject.toml`
- Automatic fallback to `1.0.0-dev` if file read fails

#### 🐛 Bug Fixes

**SQLAlchemy Boolean Query Syntax**
- Updated all boolean column comparisons from `column == True` to `column.is_(True)`
- Ensures proper SQL generation for boolean identity checks
- Improves compatibility with nullable boolean columns
- Applied to all `is_latest_review` queries in review service
- Resolves "Review not found" errors caused by incorrect boolean comparison

**API Route Ordering**
- Reorganized review endpoints for correct route matching
- Moved `/score` endpoint before parameterized routes like `/{pull_request_id}`
- Prevents FastAPI from treating "score" as a path parameter value
- Ensures deterministic route resolution

#### ⚠️ Breaking Changes

**Review Score Update API**
- `source_filename` parameter is now **mandatory** (previously optional)
- All 5 composite key fields must be provided for score updates
- This ensures precise record targeting and maintains data integrity
- Aligns with database unique constraint requirements

**Example API Call:**
```bash
curl -X PUT "http://localhost:8000/api/v1/reviews/score" \
  -G \
  --data-urlencode "project_key=ECOM" \
  --data-urlencode "repository_slug=frontend-store" \
  --data-urlencode "pull_request_id=pr-123" \
  --data-urlencode "reviewer=john_doe" \
  --data-urlencode "source_filename=src/services/cart.py" \
  --data-urlencode "score=9" \
  -H "Content-Type: application/json" \
  -d '{}'
```

#### 📦 Technical Details

- **Composite Key Pattern**: Full business key ensures data integrity across multi-tenant deployments
- **Performance**: Single UPDATE query, no INSERT operations or iteration increments
- **Type Safety**: Proper SQLAlchemy `.is_()` usage for boolean comparisons
- **Development Workflow**: Simplified version management without package installation overhead

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
   # Expected: {"status": "healthy", "version": "1.1.0"}
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
- [ ] Verify API endpoints responding correctly
- [ ] Update any external documentation or wikis
- [ ] Notify team/stakeholders of release
- [ ] Create GitHub release with changelog notes
- [ ] Tag commit with version: `git tag v1.1.0 && git push origin v1.1.0`

---

## Contributors

- Core development and maintenance
- Bug fixes and feature enhancements

---

**Release Date:** March 25, 2026  
**Version:** 1.1.0  
**Status:** Ready for Release ✅
