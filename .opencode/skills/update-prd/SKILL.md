---
name: update-prd
description: Maintain the Product Requirements Document (PRD) at docs/PRD.md when system changes occur. Scans modified code (models, services, endpoints, schemas, frontend views, routes), compares against current PRD content, identifies gaps, and updates the PRD with new/modified features, data model changes, API endpoints, frontend routes, and non-functional requirements. Use when the user says "update PRD", "update the PRD", "sync PRD", or "/update-prd".
---

# Update PRD

Maintain the Product Requirements Document (PRD) to reflect the current state of the PRLedger system.

## When to Use

- After implementing new features or capabilities
- After modifying existing features (API changes, new fields, behavior changes)
- After adding/removing database tables or columns
- After adding/removing API endpoints
- After adding/removing frontend pages or routes
- After significant architectural changes
- Periodically to ensure PRD accuracy

## Workflow

### Phase 1: Detect Changes

Determine what changed since the last PRD update:

```bash
# Check git history since last PRD modification
git log --oneline --since="$(git log -1 --format=%ci -- docs/PRD.md)" -- src/ frontend/src/ alembic/
```

Or ask the user what changed if git history is unclear.

### Phase 2: Scan Affected Areas

Based on detected changes, scan the relevant source files:

| Change Type | Files to Scan | PRD Sections to Update |
|---|---|---|
| New/modified models | `src/models/*.py` | Section 6 (Data Model) |
| New/modified endpoints | `src/api/v1/endpoints/*.py` | Section 7 (API Specification) |
| New/modified schemas | `src/schemas/*.py` | Section 7 (API Specification) |
| New/modified services | `src/services/*.py` | Section 5 (Feature Specifications) |
| New/modified frontend views | `frontend/src/views/**/*.vue` | Section 8 (Frontend Specification) |
| New/modified routes | `frontend/src/router/index.ts` | Section 8 (Frontend Specification) |
| New/modified composables | `frontend/src/composables/*.ts` | Section 8 (Frontend Specification) |
| Config changes | `src/core/config.py` | Section 9 (Non-Functional Requirements) |
| Migration changes | `alembic/versions/*.py` | Section 6 (Data Model) |
| New dependencies | `pyproject.toml`, `frontend/package.json` | Section 4 (System Architecture) |

### Phase 3: Compare and Identify Gaps

Read the current PRD at `docs/PRD.md` and compare against scanned code:

1. **Features (Section 5)**: Are there new capabilities not documented?
2. **Data Model (Section 6)**: Are there new/modified/removed tables or fields?
3. **API Endpoints (Section 7)**: Are there new/modified/removed endpoints?
4. **Frontend (Section 8)**: Are there new/modified/removed pages or routes?
5. **Non-Functional (Section 9)**: Have performance targets or constraints changed?
6. **Architecture (Section 4)**: Has the tech stack or architecture changed?

### Phase 4: Update PRD

Apply changes to `docs/PRD.md`:

1. **Add new features**: Create new subsections in Section 5 with functional requirement tables
2. **Update existing features**: Modify requirement IDs, descriptions, or priorities
3. **Update data model**: Add/remove/modify table entries in Section 6
4. **Update API spec**: Add/remove/modify endpoint tables in Section 7
5. **Update frontend**: Add/remove/modify page routes in Section 8
6. **Update glossary**: Add new terms to Section 11

### Phase 5: Version and Metadata

Update the document metadata table at the top of the PRD:

```markdown
| Field | Value |
|---|---|
| **Document Version** | [increment minor: 1.0 → 1.1, or major for breaking changes: 1.x → 2.0] |
| **Status** | Updated |
| **Last Updated** | [current date] |
```

## PRD Format Standards

### Feature Requirements Table Format

Each feature section uses this format:

```markdown
### 5.X Feature Name

**Description**: Brief description of the feature.

**Functional Requirements:**

| ID | Requirement | Priority |
|---|---|---|
| FR-5.X.1 | System SHALL [do something] | P0/P1/P2 |
```

Priority levels:
- **P0**: Core functionality, must-have
- **P1**: Important, should-have
- **P2**: Nice-to-have, future enhancement

### Data Model Table Format

```markdown
| Table | Purpose | Key Fields |
|---|---|---|
| `table_name` | Brief purpose | `field1`, `field2` (FK), `field3` |
```

### API Endpoint Table Format

```markdown
#### Group Name (`/api/v1/prefix`)

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/path` | What it does | JWT/PAT/role |
```

### Frontend Route Table Format

```markdown
| Route | Page | Access |
|---|---|---|
| `/path` | Page name | Role requirement |
```

## Checklist

Before completing the update, verify:

- [ ] All new features documented with requirement IDs
- [ ] Data model reflects current database schema
- [ ] API endpoints match actual route definitions
- [ ] Frontend routes match router configuration
- [ ] Document version incremented
- [ ] No orphaned references to removed features
- [ ] Glossary updated with new terms
- [ ] Non-functional requirements updated if changed
- [ ] Architecture diagram updated if structural changes occurred

## Tips

- **Incremental updates**: Only update sections affected by changes
- **Preserve existing IDs**: Don't renumber existing requirements; add new ones
- **Be specific**: Use "System SHALL" language for requirements
- **Reference code**: Mention file paths when helpful for developers
- **Keep it current**: Run this skill after each significant change, not just at release time
