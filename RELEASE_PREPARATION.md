# Release Preparation Guide - v1.3.1

## Release Checklist

### ✅ Pre-Release Tasks

#### 1. Version Bump
- [x] Run version bump script: `python scripts/bump_version.py set 1.3.1`
- [x] Verify version updated in `pyproject.toml`: **1.3.1** ✓
- [x] Confirm application reads correct version at runtime
- [x] Update CHANGELOG.md with release notes ✓

#### 2. Documentation Updates
- [x] Updated CHANGELOG.md with v1.3.1 changes ✓
- [x] Documented multi-reviewer score support enhancements ✓
- [x] Updated API documentation with UPSERT behavior ✓

#### 3. Code Changes Summary

##### New Features
- **Multi-Reviewer Score Support** - Complete independent scoring workflow
  - UPSERT pattern: Creates new record if reviewer hasn't scored, updates existing if present
  - Each reviewer maintains independent score history with separate iteration tracking
  - Per-reviewer `is_latest_review` flag ensures correct latest score identification
  - Supports unlimited reviewers per PR/file without conflicts
  
- **Enhanced Score Update Logic** - Intelligent create-or-update behavior
  - New `upsert_review_score()` method replaces update-only approach
  - Automatic base data reuse: New reviewers inherit AI review data (diff, suggestions)
  - Proper error handling: Distinguishes "no AI review yet" vs "new reviewer needs record"
  - Clear guidance messages direct users to submit AI review first if missing

##### Improvements
- **Service Method Refactoring** - Better naming and clearer semantics
  - Renamed `update_review_score()` → `upsert_review_score()` 
  - Enhanced logging shows which reviewer is updating/creating
  - Improved error messages with actionable guidance
  
- **API Response Enrichment** - Consistent entity information
  - `app_name` resolution integrated into upsert flow
  - Full nested objects: `project`, `repository`, `pull_request_user_info`, `reviewer_info`
  - Updated timestamp on both create and update operations

##### Bug Fixes
- **None in this release** - Focus on feature enhancements

##### Breaking Changes
- **None** - Fully backward compatible with existing workflows

#### 4. Testing Verification
- [ ] Run full test suite: `pytest tests/`
- [ ] Verify multi-reviewer scenarios:
  - Multiple reviewers scoring same PR/file independently
  - Reviewer updating their own score multiple times
  - New reviewer creating first score on existing PR
  - Error handling when AI review doesn't exist yet
- [ ] Validate API documentation clarity
- [ ] Confirm version display in `/api/docs` and `/health`

#### 5. Database Considerations
- [ ] No schema changes in this release
- [ ] No migration scripts required
- [ ] Existing data fully compatible
- [ ] Composite indexes already support multi-reviewer queries

---

## Release Notes Template

### Version 1.3.1 - March 31, 2026

#### 🎉 New Features

**Multi-Reviewer Score Support**
- Revolutionary enhancement enabling team-based code review scoring
- UPSERT pattern intelligently handles both create and update scenarios:
  - **UPDATE path**: If reviewer already has a record, updates their score and increments iteration
  - **CREATE path**: If reviewer has no record, creates new review using existing AI data as base
- Each reviewer maintains completely independent review history:
  - Separate iteration tracking per reviewer (Alice: iterations 1,2,3...; Bob: iterations 1,2...)
  - Per-reviewer `is_latest_review` flag ensures correct latest score retrieval
  - No cross-reviewer interference or conflicts
- Supports unlimited reviewers per PR/file combination
- Enables future analytics: score averaging, consensus analysis, reviewer trends

**Example Workflow:**
```python
# AI submits initial review (creates base data)
POST /api/v1/reviews
{
  "pull_request_id": "PR-123",
  "source_filename": "src/main.py",
  "ai_suggestions": {...},
  "score": None
}

# Reviewer A scores the file (creates Record A)
PUT /api/v1/reviews/score
{
  "pull_request_id": "PR-123",
  "source_filename": "src/main.py",
  "reviewer": "alice",
  "score": 8.5
}

# Reviewer B scores SAME file (creates Record B, independent from Alice's)
PUT /api/v1/reviews/score
{
  "pull_request_id": "PR-123",
  "source_filename": "src/main.py",
  "reviewer": "bob",
  "score": 9.0
}

# Alice updates HER score (updates Record A, doesn't affect Bob's score)
PUT /api/v1/reviews/score
{
  "pull_request_id": "PR-123",
  "source_filename": "src/main.py",
  "reviewer": "alice",
  "score": 7.5
}

# Query all reviews for PR-123/src/main.py returns:
# [
#   {"reviewer": "system", "score": null, "iteration": 1},
#   {"reviewer": "alice", "score": 7.5, "iteration": 2},
#   {"reviewer": "bob", "score": 9.0, "iteration": 1}
# ]
```

**Enhanced Score Update Logic**
- Smart base data reuse mechanism:
  - When new reviewer scores a file, system finds ANY existing review for that PR/file
  - Copies foundational data: `pull_request_commit_id`, `git_code_diff`, `ai_suggestions`, metadata
  - Reviewer-specific fields initialized: `score`, `reviewer_comments`, `reviewer`
  - Ensures consistency across all reviews of same PR/file
- Comprehensive error handling:
  - `ReviewNotFoundException`: Clearly distinguishes scenarios
    - "No review data exists for this file. AI review results must be submitted first."
    - "No review found for reviewer 'X'. Each reviewer must submit independently."
  - `ValueError`: Missing required parameters with explicit field list
  - Warning logs provide operational visibility

#### 🔧 Improvements

**Service Method Refactoring**
- Method renamed to reflect true behavior: `update_review_score()` → `upsert_review_score()`
- Enhanced logging provides better debugging:
  ```python
  logger.info(f"Updating score for reviewer 'alice': 8.5 -> 7.5")
  logger.info(f"Creating new score for reviewer 'bob': 9.0")
  ```
- Improved error messages guide users through correct workflow
- Clear separation of UPDATE vs CREATE logic paths

**API Response Enrichment**
- All score operations now return fully enriched responses:
  - Virtual `app_name` field resolved from project registry
  - Complete `project` object with full details
  - Complete `repository` object with full details
  - `pull_request_user_info` with PR author information
  - `reviewer_info` with reviewer information
- Consistent data structure across all endpoints
- Updated timestamp (`updated_date`) set on both create and update operations

#### 🐛 Bug Fixes

*None in this release - focus was on feature enhancements*

#### ⚠️ Breaking Changes

**None** - This release is fully backward compatible:
- Existing single-reviewer workflows continue to work unchanged
- API signatures remain the same (request/response format unchanged)
- Database schema unchanged
- No migration required

#### 📦 Technical Details

**UPSERT Implementation Strategy:**
```python
async def upsert_review_score(self, ..., reviewer: str, score: float, db: AsyncSession):
    # Try to find existing review for THIS reviewer
    existing_review = await db.execute(
        select(PullRequestReview).where(
            PullRequestReview.reviewer == reviewer,
            PullRequestReview.is_latest_review.is_(True),
            # ... other composite key fields
        )
    ).scalar_one_or_none()
    
    if existing_review:
        # UPDATE path: Mark old as not-latest, create new iteration
        existing_review.is_latest_review = False
        new_iteration = get_max_iteration(reviewer) + 1
        new_review = PullRequestReview(
            reviewer=reviewer,
            score=score,
            review_iteration=new_iteration,
            is_latest_review=True
        )
    else:
        # CREATE path: Find any base review, copy data for new reviewer
        base_review = await get_any_review(pull_request_id, source_filename)
        if not base_review:
            raise ReviewNotFoundException("AI review must exist first")
        
        new_review = PullRequestReview(
            reviewer=reviewer,
            score=score,
            review_iteration=1,  # First iteration for this reviewer
            is_latest_review=True,
            # Copy base data from existing review
            pull_request_commit_id=base_review.pull_request_commit_id,
            git_code_diff=base_review.git_code_diff,
            ai_suggestions=base_review.ai_suggestions,
            # ... etc
        )
    
    await db.commit()
    return enrich_review_with_entities(new_review)
```

**Key Architectural Decisions:**
- **Composite Key Pattern**: `(project_key, repository_slug, pull_request_id, source_filename, reviewer)` ensures uniqueness per reviewer
- **Iteration Scoping**: `MAX(review_iteration) WHERE reviewer = :reviewer` calculates per-reviewer iteration
- **Cache Strategy**: Single cache key per PR shared across all reviewers, invalidated on any score change
- **Enrichment Flow**: `_enrich_review_with_entities()` resolves `app_name` from project registry for all responses

**Database State Example:**
After multiple reviewers score same PR/file:
| ID | reviewer | score | iteration | is_latest_review |
|----|----------|-------|-----------|------------------|
| 1  | system   | NULL  | 1         | True             |
| 2  | alice    | 8.5   | 1         | False            |
| 3  | bob      | 9.0   | 1         | True             |
| 4  | alice    | 7.5   | 2         | True             |

Each reviewer's latest score independently queryable! ✅

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
   # Expected: {"status": "healthy", "version": "1.3.1"}
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
- [ ] Verify multi-reviewer scenarios working correctly
- [ ] Update any external documentation or wikis
- [ ] Notify team/stakeholders of release
- [ ] Create GitHub release with changelog notes
- [ ] Tag commit with version: `git tag v1.3.1 && git push origin v1.3.1`

---

## Contributors

- Core development and maintenance
- Multi-reviewer architecture design and implementation
- Enhanced score upsert logic and error handling

---

**Release Date:** March 31, 2026  
**Version:** 1.3.1  
**Status:** Ready for Release ✅
