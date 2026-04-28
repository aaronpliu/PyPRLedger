---
name: release-manager
description: Streamlined release workflow with user confirmation for all git operations. Uses helper scripts in scripts/release/ for automation.
version: 2.0.0
---

### 🎯 Objective
Guide users through release preparation with explicit confirmation at each git operation. No automatic commits or pushes.

**Principles:**
1. ❌ No auto `git commit` / `git push`
2. ✅ User confirms versions, docs, commit, tag
3. 🔄 Scripts automate non-git tasks
4. 📤 Manual push only

---

### 📊 Workflow

```
1. Verify Versions   → Run: scripts/release/get_versions.py
2. Choose Versions   → User input + auto-calc frontend
3. Set Versions      → Run: bump_version.py + set_frontend_version.py
4. Analyze Changes   → Run: scripts/release/analyze_changes.py
5. Update Docs       → Run: scripts/release/update_changelog.py
6. Sync Dependencies → Run: scripts/release/sync_dependencies.sh
7. Prepare Commit    → Show details, ask: "Execute git add + git commit?"
8. Create Tag        → Show details, ask: "Create git tag?"
9. Manual Push       → Provide instructions
```

---

### 🛠️ Execution Steps

#### Step 1: Verify Current Versions

**Action**: Run version check script
```bash
python scripts/release/get_versions.py
```

**Expected**:
```
Backend: X.Y.Z
Frontend: A.B.C
```

**Record**: `backend_version`, `frontend_version`

---

#### Step 2: Determine New Versions

**Prompt**:
```
Current:
  Backend:  {backend_version}
  Frontend: {frontend_version}

Frontend minor = Backend minor + 1

Options:
1. Auto-calc frontend (recommended)
2. Specify both versions
3. Backend only

Choice (1-3) or exact backend version:
```

**On choice**:

- **Option 1/backend version** → Calculate: `frontend_new = backend_major.(backend_minor+1).backend_patch`
- **Option 2** → Ask: "Enter frontend version:"
- **Option 3** → `frontend_new = frontend_version` (unchanged)

**Display plan**:
```
Version Plan:
  Backend:  {backend_version} → {backend_new_version}
  Frontend: {frontend_version} → {frontend_new_version}
```

**Ask**: "Confirm? (yes/no)"

**On confirm**:
- Run: `python scripts/bump_version.py set {backend_new_version}`
- Run: `python scripts/release/set_frontend_version.py {frontend_new_version}` (if changed)

**Validation**:
- ✅ `pyproject.toml` updated
- ✅ `frontend/package.json` updated (if changed)

---

#### Step 3: Analyze Changes

**Action**: Run analysis script
```bash
python scripts/release/analyze_changes.py v{old_backend}..HEAD
```

**Output**: Categorized summary (Features, Bug Fixes, Improvements, Docs)

**Display**: Full summary to user

**Ask**: "Ready to update docs? (yes/no)"

---

#### Step 4: Update Documentation

**Action**: Run documentation update script
```bash
python scripts/release/update_changelog.py {backend_new_version} {frontend_new_version}
```

**What it does**:
- Prepends new section to `CHANGELOG.md`
- Includes both backend and frontend versions
- Uses today's date

**Optional**: Manually edit `CHANGELOG.md` to fill in actual change details

**Display**: Show updated CHANGELOG.md head

**Ask**: "Docs ready. Proceed to dependency sync? (yes/no)"

---

#### Step 5: Synchronize Dependencies (Automatic)

**Action**: Run sync script
```bash
bash scripts/release/sync_dependencies.sh
```

**Does**:
1. `uv sync --all-extras` (backend)
2. `cd frontend && npm install` (frontend)

**Validation**:
- ✅ No errors
- ✅ `uv.lock` updated
- ✅ `package-lock.json` updated

---

#### Step 6: Prepare Commit (User Action)

**⚠️ NO auto-commit. User must execute git commands.**

**Action 6.1**: Show prepared commit details

Run preview script:
```bash
python scripts/release/prepare_commit.py {backend_new_version} {frontend_new_version}
```

**Displays**:
- Git status
- Files changed
- Commit message

**Action 6.2**: Ask user

```
All changes ready.

Execute commit now? (yes/no)
  yes → Run: git add . && git commit -m "Release v{backend_new_version}..."
  no  → Stop, wait for user
```

**On yes**:
- Execute `git add .`
- Execute `git commit -m "..."`
- Or run: `python scripts/release/prepare_commit.py {backend_new_version} {frontend_new_version} --execute`

**Show result**: `git log -1 --oneline`

---

#### Step 7: Create Git Tag (User Confirmation)

**Action 7.1**: Show tag details

```
Tag: v{backend_new_version}
Message: Release version {backend_new_version}
Commit: <current HEAD>
```

**Action 7.2**: Ask

```
Create annotated tag? (yes/no)

Command: git tag -a v{backend_new_version} -m "Release version {backend_new_version}"

Or run: python scripts/release/create_tag.py {backend_new_version} --execute
```

**On yes**:
- Run: `python scripts/release/create_tag.py {backend_new_version} --execute`
- Or manually: `git tag -a v{backend_new_version} -m "Release version {backend_new_version}"`

**On no**: Stop, wait for user

---

### 🏁 Final: Manual Push

**Provide instructions**:
```bash
# Push commit
git push origin <branch>

# Push tag
git push origin v{backend_new_version}
```

---

### ⚠️ Safety Constraints

**NEVER auto-execute**:
- ❌ `git commit` (without confirmation)
- ❌ `git push` / `git push --tags`
- ❌ `git push --force`
- ❌ Branch deletion
- ❌ Remote modifications

**ALWAYS ask before**:
- ✅ `git add .`
- ✅ `git commit`
- ✅ `git tag`
- ✅ Any destructive operation

---

### 📋 User Checklist

**Before starting**:
- [ ] Working directory clean (or stashed)
- [ ] Tests passing: `pytest -v`
- [ ] No broken builds

**After versions set**:
- [ ] Backend version in `pyproject.toml` ✓
- [ ] Frontend version in `frontend/package.json` ✓

**Before commit**:
- [ ] `CHANGELOG.md` content accurate
- [ ] All intended files modified
- [ ] No unintended changes

**After release**:
- [ ] Commit created
- [ ] Tag created
- [ ] Pushed to remote

---

### 🔧 Helper Scripts Reference

All scripts in `scripts/release/`:

| Script | Purpose |
|--------|---------|
| `get_versions.py` | Show current backend & frontend versions |
| `calculate_frontend_version.py` | Compute frontend version from backend |
| `set_frontend_version.py` | Update `frontend/package.json` version |
| `analyze_changes.py` | Generate changelog summary from git log |
| `update_changelog.py` | Prepend new release section to CHANGELOG.md |
| `sync_dependencies.sh` | Run `uv sync` + `npm install` |
| `prepare_commit.py` | Preview commit details |
| `create_tag.py` | Create annotated git tag |

---

### 🎯 Version Convention

```
Backend:  X.Y.Z    (e.g., 1.8.0)
Frontend: X.(Y+1).Z (e.g., 1.9.0)
```

Frontend releases more frequently; minor version always one ahead.

---

### 🔍 Troubleshooting

**User declines step** → Respect decision, wait for instruction

**Script error** → Show error, suggest manual alternative

**Git conflicts** → Warn user, suggest `git status`/`git diff` review

**Frontend bump fails** → Edit `frontend/package.json` manually, then `npm install`

---

### 📚 Example Session

```bash
# 1. Check versions
$ python scripts/release/get_versions.py
Backend: 1.7.1
Frontend: 1.2.1

# 2. Choose: backend 1.8.0 → frontend auto-calc = 1.9.0
# Confirm: yes

# 3. Analyze changes
$ python scripts/release/analyze_changes.py v1.7.1..HEAD
## Summary of Changes...
# Confirm: yes

# 4. Update docs
$ python scripts/release/update_changelog.py 1.8.0 1.9.0
✓ Updated CHANGELOG.md
# Edit CHANGELOG.md to fill details
# Confirm: yes

# 5. Sync deps
$ bash scripts/release/sync_dependencies.sh
✓ Dependencies synchronized

# 6. Prepare & commit
$ python scripts/release/prepare_commit.py 1.8.0 1.9.0
# Review output
# Execute: git add . && git commit -m "Release v1.8.0..."

# 7. Tag
$ python scripts/release/create_tag.py 1.8.0
✓ Tag v1.8.0 created

# 8. Push (manual)
$ git push origin feature/xyz
$ git push origin v1.8.0
```
