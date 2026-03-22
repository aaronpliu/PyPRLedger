# Pre-commit Hooks Setup Guide

This project uses [pre-commit](https://pre-commit.com/) hooks to ensure code quality and consistency.

## Quick Setup

### 1. Install pre-commit

```bash
pip install pre-commit
```

Or with development dependencies:
```bash
pip install -e ".[dev]"
```

### 2. Install Git Hooks

```bash
pre-commit install
```

This sets up the pre-commit hooks in your local git repository. Now hooks will run automatically on `git commit`.

### 3. (Optional) Run Against All Files

To verify all files in the repository:

```bash
pre-commit run --all-files
```

## What Hooks Are Configured?

### Code Quality
- **Ruff Linting** - Fast Python linting with automatic fixes
- **Ruff Formatting** - Consistent code formatting
- **Check YAML/TOML/JSON** - Validate configuration files
- **End of File Fixer** - Ensure files end with newline
- **Trailing Whitespace** - Remove unnecessary whitespace

### Security
- **Detect Secrets** - Scan for accidentally committed secrets
- **Detect Private Keys** - Prevent committing private keys
- **Debug Statements** - Catch debugger imports

### Repository Maintenance
- **Large Files** - Prevent committing files > 5MB
- **Merge Conflicts** - Check for unresolved merge conflicts
- **Case Conflicts** - Detect filename case conflicts
- **Windows Names** - Check for invalid Windows filenames

## Common Commands

```bash
# Run all hooks manually
pre-commit run --all-files

# Run specific hook
pre-commit run ruff --all-files

# Update hooks to latest versions
pre-commit autoupdate

# Temporarily skip hooks (not recommended)
git commit --no-verify
```

## Troubleshooting

### Hook Fails on Commit
If a hook fails, fix the issues it reports and re-stage your files:
```bash
# Fix the reported issues
# Then re-stage and commit again
git add <files>
git commit
```

### Auto-fix Available
Some hooks can auto-fix issues:
```bash
pre-commit run --fix
```

### Skip Specific Hook (Temporary)
```bash
SKIP=hook-name git commit -m "message"
```

## Configuration

Hooks are configured in `.pre-commit-config.yaml` at the project root.

See [pre-commit documentation](https://pre-commit.com/) for more details.

## CI/CD Integration

Pre-commit is configured to run in CI/CD pipelines automatically. The configuration includes:
- Automatic fixes committed by pre-commit.ci
- Weekly autoupdates
- PR integration

---

**Note**: Keep pre-commit hooks installed and active for consistent code quality across the team.
