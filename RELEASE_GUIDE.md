# 🚀 Forge CLI Release Automation

This set of scripts completely automates the development and release process for forge-cli, eliminating manual errors and ensuring a consistent workflow.

## 📁 Included Files

- **`scripts/forge_release.py`** - Main script with all automation functions
- **`release.py`** - Simple and easy-to-use wrapper script
- **`RELEASE_GUIDE.md`** - This documentation

## 🎯 Quick Usage

### Option 1: Simple Script (Recommended)

```bash
# Interactive mode (guided step by step)
python release.py

# Direct commands
python release.py feature add-auth-command    # Start new feature
python release.py patch                       # Prepare patch release
python release.py minor                       # Prepare minor release
python release.py major                       # Prepare major release
python release.py publish                     # Create final release
```

### Option 2: Full Script (Advanced)

```bash
python scripts/forge_release.py start-feature <name>
python scripts/forge_release.py prepare-release <patch|minor|major>
python scripts/forge_release.py create-release
python scripts/forge_release.py full-release <patch|minor|major>  # Emergency only
```

## 📋 Automated Workflow

### 🌟 1. Start New Feature

```bash
python release.py feature my-new-feature
```

**What does it do automatically?**

- ✅ Verifies that the working directory is clean
- ✅ Switches to `main` branch if you're not on it
- ✅ Runs `git pull origin main` to get latest changes
- ✅ Creates and switches to new branch `feature/my-new-feature`

### 🔧 2. Development (Manual)

- Implement your feature
- Pre-commit hooks run automatically
- Make commits normally: `git commit -m "feat: description"`

### 📦 3. Prepare Release

```bash
python release.py patch    # For bug fixes (1.0.1 → 1.0.2)
python release.py minor    # For new features (1.0.1 → 1.1.0)
python release.py major    # For breaking changes (1.0.1 → 2.0.0)
```

**What does it do automatically?**

- ✅ Gets current version from `pyproject.toml` and `__init__.py`
- ✅ Calculates new version according to semantic versioning
- ✅ Updates both files with the new version
- ✅ Runs all quality checks:
  - Linting with `ruff check .`
  - Formatting with `black --check .`
  - Tests with `pytest -q`
  - Version synchronization
- ✅ Builds package with `python -m build`
- ✅ Validates metadata with `twine check`
- ✅ Verifies that templates are included
- ✅ Commits version changes

### 🔄 4. Create Pull Request (Manual)

```bash
git push origin feature/my-new-feature
```

Then create the PR on GitHub. CI automatically:

- ✅ Runs all quality checks
- ✅ Validates package build
- ✅ Verifies that templates are included

### 🚀 5. Publish Release

**After the PR is approved and merged:**

```bash
python release.py publish
```

**What does it do automatically?**

- ✅ Verifies you're on `main` branch
- ✅ Verifies directory is clean
- ✅ Runs `git pull origin main`
- ✅ Runs final quality checks
- ✅ Builds and validates final package
- ✅ Creates tag `vX.Y.Z`
- ✅ Pushes tag to GitHub
- ✅ GitHub Actions automatically publishes to PyPI

## ⚡ Interactive Mode

For users less familiar with command line:

```bash
python release.py
```

The script will guide you step by step with interactive menus.

## 🛡️ Automatic Quality Checks

All scripts automatically run these verifications:

### 🔍 Code Checks

- **Ruff**: Linting and problem detection
- **Black**: Code formatting verification
- **Pre-commit**: Automatic hooks on each commit

### 📋 Project Checks

- **Version synchronization**: `pyproject.toml` and `__init__.py` match
- **Build**: Package builds correctly
- **Metadata**: Validation with twine
- **Templates**: Jinja2 templates are included in the wheel

### 🌿 Git Checks

- **Clean directory**: No uncommitted changes
- **Correct branch**: Operations on appropriate branches
- **Synchronization**: Latest repository state

## 🚨 Emergency Commands

### Full Release (No PR)

```bash
python scripts/forge_release.py full-release patch
```

**⚠️ Warning**: This creates a release immediately without PR review. For emergencies only.

### Manual Checks

```bash
# Only check quality without changes
ruff check .
black --check .
python scripts/check_version_sync.py

# Only build and validate
python -m build
python -m twine check dist/*
```

## 🔧 Required Configuration

### Dependencies

The scripts require these dependencies (already in `pyproject.toml`):

```toml
[project.optional-dependencies]
dev = [
    "rich>=13.7",      # For colorful output
    "requests",        # For GitHub API interactions
    "typer>=0.12",     # Already included in project
]
```

### Environment Variables (Optional)

For advanced GitHub functionality:

```bash
export GITHUB_TOKEN="your_token_here"  # For advanced GitHub API operations
```

## 📊 Complete Session Example

```bash
# 1. Start new feature
$ python release.py feature add-json-output
✓ Feature branch 'feature/add-json-output' created and checked out

# 2. Develop (manual)
# ... implement feature ...
$ git add .
$ git commit -m "feat: add JSON output option to forge commands"

# 3. Prepare release
$ python release.py minor
Current version: 1.0.2
New version: 1.1.0
Update version from 1.0.2 to 1.1.0? [y/N]: y
→ Running ruff check...
→ Running black format check...
→ Running tests...
→ Checking version synchronization...
→ Building package...
→ Checking package metadata...
→ Verifying templates are included...
✓ Release prepared for version 1.1.0

# 4. Create PR and wait for merge (manual)
$ git push origin feature/add-json-output
# ... create PR, review, merge ...

# 5. Publish release
$ python release.py publish
✓ Release v1.1.0 created successfully

GitHub Actions will now:
1. Run all quality checks
2. Build the package
3. Publish to PyPI automatically
```

## 🐛 Troubleshooting

### Error: "Working directory is not clean"

```bash
git status                    # See which files have changes
git add . && git commit -m "wip: save changes"  # Or
git stash                     # Save changes temporarily
```

### Error: "Version mismatch"

```bash
python scripts/check_version_sync.py  # See the problem
# Manually edit pyproject.toml or src/forge/__init__.py
```

### Error: "Command failed"

```bash
# See detailed error output
# The scripts show exactly which command failed and why
```

### Build or Test Errors

```bash
# Run manually to see details
python -m build
pytest -v
ruff check .
black --check .
```

## 🎨 Customization

### Modify Checks

Edit the `run_quality_checks()` function in `scripts/forge_release.py`:

```python
def run_quality_checks() -> None:
    # Add new checks here
    run_command("mypy src/")  # Example: add type checking
```

### Change Versioning Behavior

Modify the `bump_version()` function for different versioning schemes.

### Add New Commands

Extend the `release.py` script with new options in the `main()` function.

---

With these scripts, your development and release workflow is completely automated! 🎉
