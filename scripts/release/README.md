# Release Management Scripts

Helper scripts used by the `release-manager` skill. These automate non-git operations during release preparation.

## Scripts

### `get_versions.py`
Prints current backend and frontend versions.
```bash
python scripts/release/get_versions.py
# Output: Backend: 1.8.0 / Frontend: 1.9.0
```

### `calculate_frontend_version.py`
Calculates frontend version from backend version using convention: frontend minor = backend minor + 1.
```bash
python scripts/release/calculate_frontend_version.py 1.8.0
# Output: 1.9.0
```

### `set_frontend_version.py`
Updates version in `frontend/package.json`.
```bash
python scripts/release/set_frontend_version.py 1.9.0
```

### `analyze_changes.py`
Generates categorized changelog summary from git commits.
```bash
python scripts/release/analyze_changes.py v1.7.1..HEAD
```
Uses conventional commit prefixes: `feat:`, `fix:`, `improve:`, `docs:`, `refactor:`, `chore:`.

### `update_changelog.py`
Prepends new release section to `CHANGELOG.md`.
```bash
python scripts/release/update_changelog.py 1.8.0 1.9.0
# Optionally pass summary file: python ... 1.8.0 1.9.0 summary.txt
```

### `sync_dependencies.sh`
Synchronizes all dependencies (backend + frontend).
```bash
bash scripts/release/sync_dependencies.sh
```
Runs `uv sync --all-extras` and `npm install` in frontend/.

### `prepare_commit.py`
Shows commit preview (files, message). Does NOT commit by default.
```bash
python scripts/release/prepare_commit.py 1.8.0 1.9.0
```
To execute commit automatically (with confirmation prompt):
```bash
python scripts/release/prepare_commit.py 1.8.0 1.9.0 --execute
```
User can also manually run `git add .` and `git commit`.

### `create_tag.py`
Creates annotated git tag (requires confirmation).
```bash
python scripts/release/create_tag.py 1.8.0
```
Creates tag `v1.8.0` with message "Release version 1.8.0".

## Usage

These scripts are called automatically by the `release-manager` skill during the release workflow. They can also be run manually for debugging or custom workflows.

All Python scripts exit with non-zero code on error. Bash scripts use `set -e`.
