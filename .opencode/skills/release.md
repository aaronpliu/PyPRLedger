---
name: release-version
description: Executes the project release workflow, including version bumping, changelog generation, dependency synchronization, and git tagging. Does NOT push to remote - requires manual confirmation.
version: 1.1.0
---

### 🎯 Objective
Assist the user in completing the project release process. You must strictly follow the steps below to ensure version consistency, accurate documentation updates, and correct Git tagging.

**⚠️ CRITICAL CONSTRAINT**: This skill will NEVER execute `git push` commands. All changes remain local until the user manually pushes them.

### 🛠️ Execution Steps

#### Step 1: Verify Current Version
**Action**: Execute command to check current version
```bash
python scripts/bump_version.py show
```

**Expected Output**: Current version number (e.g., `1.2.3`)

**Validation**:
- ✅ Command executes successfully
- ✅ Version format follows SemVer (major.minor.patch)
- ❌ If error occurs: Stop and report error message to user

**Next**: Record output as `current_version` and proceed to Step 2.

---

#### Step 2: Determine New Version
**Action**: Ask user for version upgrade type or specific version number

**Prompt User**:
```
Current version: {current_version}

Please specify the new version:
  Option 1: Semantic version bump (patch/minor/major)
  Option 2: Specific version number (e.g., 1.2.4)

Which would you prefer?
```

**Once user confirms `new_version`**:

**Action**: Execute command to set new version
```bash
python scripts/bump_version.py set <new_version>
```

**Validation**:
- ✅ Command executes successfully
- ✅ Version is updated in all relevant files
- ❌ If error occurs: Stop and report error message to user

**Next**: Proceed to Step 3.

---

#### Step 3: Analyze Changes Since Last Release
**Action 3.1**: Retrieve commit history
```bash
git log --oneline --decorate v{previous_version}..HEAD
```

**Note**: If tag not found, use:
```bash
git log --oneline --decorate -20
```

**Action 3.2**: Retrieve list of changed files
```bash
git diff --name-only v{previous_version}..HEAD
```

**Action 3.3**: Categorize changes
Analyze commits and files to categorize into:
- **Features**: New functionality
- **Bug Fixes**: Issue resolutions
- **Improvements**: Enhancements to existing features
- **Documentation**: Doc updates
- **Dependencies**: Library updates
- **Breaking Changes**: API or behavior changes

**Output Format**:
```markdown
## Summary of Changes

### Features
- Feature 1 description
- Feature 2 description

### Bug Fixes
- Fix 1 description

### Improvements
- Improvement 1 description

### Documentation
- Doc update 1

### Breaking Changes (if any)
- Breaking change description
```

**Next**: Show summary to user for review, then proceed to Step 4.

---

#### Step 4: Update Documentation

**Action 4.1**: Update CHANGELOG.md

**File**: `CHANGELOG.md`

**Changes**:
1. Add new section at the top with format:
```markdown
## [v{new_version}] - {YYYY-MM-DD}

### Features
- ...

### Bug Fixes
- ...
```

2. Keep existing entries below the new section

**Action 4.2**: Update README.md (if needed)

**Check for**:
- Version-specific download links
- Installation instructions with version numbers
- API version references

**Update if found**:
- Replace old version with `{new_version}`

**Action 4.3**: Update docs/ directory (if applicable)

**Files to check**:
- `docs/*.md` - version related references
- Any other version-specific documentation

**Validation**:
- ✅ All version references updated consistently
- ✅ CHANGELOG.md formatted correctly
- ✅ No broken links or references

**Next**: Show user a preview of documentation changes for approval before proceeding.

---

#### Step 5: Synchronize Dependencies

**Action**: Execute dependency synchronization
```bash
uv sync --all-extras
```

**Expected Behavior**:
- Updates `uv.lock` file
- Ensures all dependencies are consistent
- May update package versions if constraints changed

**Validation**:
- ✅ Command completes without errors
- ✅ `uv.lock` file is modified
- ✅ No dependency conflicts reported

**Frontend Synchronization**:
```bash
cd frontend && npm install
```

**Validation**:
- ✅ `package-lock.json` updated
- ✅ No dependency conflicts reported

**If errors occur**:
- Report error details to user
- Do NOT proceed to next step
- Wait for user guidance

**Next**: Proceed to Step 6.

---

#### Step 6: Stage and Commit Changes

**Action 6.1**: Review all changes
```bash
git status
```

**Expected Files to be Modified**:
- Version configuration files (from Step 2)
- `CHANGELOG.md` (from Step 4.1)
- `README.md` (if updated in Step 4.2)
- Documentation files (if updated in Step 4.3)
- `uv.lock` (from Step 5)
- `web/lib/` (if library files were added/updated)

**Action 6.2**: Stage all changes
```bash
git add .
```

**Action 6.3**: Create commit
```bash
git commit -m "Release v{new_version}

- Bump version to {new_version}
- Update CHANGELOG.md
- Synchronize dependencies
"
```

**Validation**:
- ✅ All expected files are staged
- ✅ Commit message is clear and descriptive
- ✅ No unintended files included

**Next**: Proceed to Step 7.

---

#### Step 7: Create Git Tag

**Action**: Create annotated tag
```bash
git tag -a v{new_version} -m "Release version {new_version}"
```

**Validation**:
- ✅ Tag created successfully
- ✅ Tag is annotated (not lightweight)
- ✅ Tag message includes version number

**Verify Tag**:
```bash
git tag -l | tail -5
git show v{new_version}
```

**Next**: Proceed to Final Step.

---

### ⚠️ Safety Constraints

#### Prohibited Actions
- ❌ **NEVER** execute `git push` commands
- ❌ **NEVER** execute `git push --tags`
- ❌ **NEVER** force push (`git push --force`)
- ❌ **NEVER** delete remote tags or branches
- ❌ **NEVER** modify remote repository state

#### Required Validations
- ✅ Always verify command success before proceeding
- ✅ Always show change summaries to user
- ✅ Always wait for user confirmation on critical steps
- ✅ Always report errors immediately and stop

#### Error Handling
- If any command fails: **STOP** and report error
- Do NOT attempt automatic recovery
- Wait for user guidance before continuing
- Provide clear error messages and context

---

### 📋 Checklist for User

Before pushing, verify:
- [ ] Version number is correct in all files
- [ ] CHANGELOG.md accurately reflects changes
- [ ] All tests pass locally
- [ ] `uv.lock` is up to date
- [ ] Git tag is created and annotated
- [ ] No unintended files are committed
- [ ] Ready to push to remote repository

---

### 🔍 Troubleshooting

#### Issue: `bump_version.py` returns error
**Solution**: 
- Check Python environment
- Verify script exists and is executable
- Report exact error message to user

#### Issue: `uv sync` fails
**Solution**:
- Check network connectivity
- Verify `pyproject.toml` syntax
- Review dependency conflicts
- Do NOT proceed until resolved

#### Issue: Git tag already exists
**Solution**:
- Inform user of conflict
- Suggest using different version number
- Do NOT delete existing tag

#### Issue: Uncommitted changes detected
**Solution**:
- Warn user about dirty working directory
- Suggest committing or stashing changes first
- Do NOT proceed with release