---
name: release-version
description: Executes the project release workflow, including version bumping, changelog generation, dependency synchronization, and git tagging.
version: 1.0.0
---

### 🎯 Objective
Assist the user in completing the project release process. You must strictly follow the steps below to ensure version consistency, accurate documentation updates, and correct Git tagging.

### 🛠️ Execution Steps

#### 1. Verify Current Version
- Execute command: `python scripts/bump_version.py show`
- **Note**: Record the output as `current_version`.

#### 2. Determine New Version
- Ask the user for the new version number (e.g., is it a SemVer patch, minor, or major upgrade?).
- Once `new_version` is confirmed, execute command: `python scripts/bump_version.py set <new_version>`.

#### 3. Analyze Changes
- Retrieve commit history since the last release.
    - Execute command: `git log <previous_version_tag>..HEAD --oneline` (If the tag is not found, look for the last specified commit).
- Retrieve the list of changed files:
    - Execute command: `git diff <previous_version_tag>..HEAD --name-only`.
- **Reasoning**: Based on the commit messages and changed files, summarize the core updates for this release (to be used for the Changelog).

#### 4. Update Documentation
- **Update CHANGELOG.md**:
    - Add the new version number and date at the top of the file.
    - Write the summary of updates generated in Step 3.
- **Update README.md**:
    - Check for any version-specific references (e.g., download links, installation instructions) and update them to `new_version`.
- **Update docs/ Directory**:
    - Check if there are files in `docs/` that require version synchronization (e.g., `docs/conf.py` or `docs/index.md`) and update them accordingly.

#### 5. Synchronize Dependencies
- Execute command: `uv sync --all-extras`
- **Verify**: Ensure the `uv.lock` file has been updated and reflects the new project version.

#### 6. Create Git Tag
- Ensure all changes (including code version, documentation, and lock file) are added to the staging area.
- Execute command: `git tag -a v<new_version> -m "Release version <new_version>"`
- Inform the user that the tag has been created and ask if they would like to push it (`git push origin v<new_version>`).

### ⚠️ Notes
- Before modifying files, it is best to show the user the planned changes for confirmation.
- If `scripts/bump_version.py` returns an error, stop immediately and report the error message.
- Ensure `uv sync` executes successfully, as this is a critical step for maintaining environment consistency.