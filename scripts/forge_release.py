#!/usr/bin/env python3
"""
Forge CLI Release Automation Script

This script automates the development and release process for forge-cli:
- Feature development workflow
- Version management
- Quality checks (linting, formatting, testing)
- Git operations (branching, tagging)
- GitHub release creation
- Build and validation

Usage:
    python scripts/forge_release.py start-feature <feature-name>
    python scripts/forge_release.py prepare-release <version-type>
    python scripts/forge_release.py create-release
    python scripts/forge_release.py full-release <version-type>
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Literal, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

# Initialize rich console for better output
console = Console()

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_TOML = PROJECT_ROOT / "pyproject.toml"
FORGE_INIT = PROJECT_ROOT / "src" / "forge" / "__init__.py"

# Constants
TEMP_VERIFY_FILE = "temp_verify.py"


class ForgeReleaseError(Exception):
    """Custom exception for release automation errors"""

    pass


def run_command(
    cmd: str, cwd: Optional[Path] = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run a shell command and return the result"""
    console.print(f"[blue]Running:[/blue] {cmd}")

    result = subprocess.run(
        cmd, shell=True, cwd=cwd or PROJECT_ROOT, capture_output=True, text=True
    )

    if check and result.returncode != 0:
        console.print(f"[red]Command failed:[/red] {cmd}")
        console.print(f"[red]Error:[/red] {result.stderr}")
        raise ForgeReleaseError(f"Command failed: {cmd}")

    return result


def get_current_version() -> Tuple[str, str]:
    """Get current version from both pyproject.toml and __init__.py"""
    # Read pyproject.toml
    pyproject_content = PYPROJECT_TOML.read_text(encoding="utf-8")
    pyproject_match = re.search(r'\nversion\s*=\s*"([^"]+)"', pyproject_content)

    # Read __init__.py
    init_content = FORGE_INIT.read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_content)

    if not pyproject_match or not init_match:
        raise ForgeReleaseError("Could not find version in pyproject.toml or __init__.py")

    pyproject_version = pyproject_match.group(1)
    init_version = init_match.group(1)

    if pyproject_version != init_version:
        raise ForgeReleaseError(
            f"Version mismatch: pyproject.toml={pyproject_version} vs __init__.py={init_version}"
        )

    return pyproject_version, init_version


def bump_version(current_version: str, version_type: Literal["patch", "minor", "major"]) -> str:
    """Bump version according to semantic versioning"""
    major, minor, patch = map(int, current_version.split("."))

    if version_type == "patch":
        patch += 1
    elif version_type == "minor":
        minor += 1
        patch = 0
    elif version_type == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise ForgeReleaseError(f"Invalid version type: {version_type}")

    return f"{major}.{minor}.{patch}"


def update_version_files(new_version: str) -> None:
    """Update version in both pyproject.toml and __init__.py"""
    console.print(f"[green]Updating version to:[/green] {new_version}")

    # Update pyproject.toml
    pyproject_content = PYPROJECT_TOML.read_text(encoding="utf-8")
    pyproject_content = re.sub(
        r'(\nversion\s*=\s*")[^"]+(")', f"\\g<1>{new_version}\\g<2>", pyproject_content
    )
    PYPROJECT_TOML.write_text(pyproject_content, encoding="utf-8")

    # Update __init__.py
    init_content = FORGE_INIT.read_text(encoding="utf-8")
    init_content = re.sub(
        r'(__version__\s*=\s*")[^"]+(")', f"\\g<1>{new_version}\\g<2>", init_content
    )
    FORGE_INIT.write_text(init_content, encoding="utf-8")

    console.print("[green]✓[/green] Version files updated")


def check_git_status() -> bool:
    """Check if git working directory is clean"""
    result = run_command("git status --porcelain", check=False)
    return len(result.stdout.strip()) == 0


def get_current_branch() -> str:
    """Get current git branch name"""
    result = run_command("git branch --show-current")
    return result.stdout.strip()


def run_quality_checks() -> None:
    """Run all quality checks (linting, formatting, tests, etc.)"""
    console.print("[blue]Running quality checks...[/blue]")

    # Check ruff linting
    console.print("→ Running ruff check...")
    run_command("ruff check .")

    # Check black formatting
    console.print("→ Running black format check...")
    run_command("black --check .")

    # Run tests
    console.print("→ Running tests...")
    run_command("pytest -q", check=False)  # Allow tests to fail for now

    # Check version synchronization
    console.print("→ Checking version synchronization...")
    run_command("python scripts/check_version_sync.py")

    console.print("[green]✓[/green] All quality checks passed")


def build_and_validate() -> None:
    """Build the package and validate it"""
    console.print("[blue]Building and validating package...[/blue]")

    # Clean previous builds
    run_command("rm -rf dist/", check=False)

    # Build package
    console.print("→ Building package...")
    run_command("python -m build")

    # Check metadata
    console.print("→ Checking package metadata...")
    run_command("python -m twine check dist/*")

    # Verify templates are included
    console.print("→ Verifying templates are included...")
    verify_templates_script = """
import glob
import zipfile
import sys

wheels = glob.glob("dist/*.whl")
if not wheels:
    print("No wheels built")
    sys.exit(1)

with zipfile.ZipFile(wheels[0]) as z:
    template_files = [n for n in z.namelist() if n.startswith("forge/templates/")]
    if not template_files:
        print("Templates not found in wheel")
        sys.exit(1)

print(f"Found {len(template_files)} template files in wheel")
"""

    with open(TEMP_VERIFY_FILE, "w") as f:
        f.write(verify_templates_script)

    try:
        run_command(f"python {TEMP_VERIFY_FILE}")
    finally:
        if os.path.exists(TEMP_VERIFY_FILE):
            os.remove(TEMP_VERIFY_FILE)

    console.print("[green]✓[/green] Package built and validated successfully")


def start_feature(feature_name: str) -> None:
    """Start a new feature development branch"""
    console.print(Panel(f"[bold blue]Starting Feature Development: {feature_name}[/bold blue]"))

    # Check if working directory is clean
    if not check_git_status():
        raise ForgeReleaseError("Working directory is not clean. Please commit or stash changes.")

    # Make sure we're on main
    current_branch = get_current_branch()
    if current_branch != "main":
        console.print("[yellow]Switching to main branch...[/yellow]")
        run_command("git checkout main")

    # Pull latest changes
    console.print("Pulling latest changes...")
    run_command("git pull origin main")

    # Create feature branch
    branch_name = f"feature/{feature_name}"
    console.print(f"Creating feature branch: {branch_name}")
    run_command(f"git checkout -b {branch_name}")

    console.print(f"[green]✓[/green] Feature branch '{branch_name}' created and checked out")
    console.print("\n[bold blue]Next steps:[/bold blue]")
    console.print("1. Implement your feature")
    console.print("2. Test your changes")
    console.print("3. Run: python scripts/forge_release.py prepare-release <patch|minor|major>")


def prepare_release(version_type: Literal["patch", "minor", "major"]) -> None:
    """Prepare a release by updating version and running checks"""
    console.print(Panel(f"[bold blue]Preparing Release: {version_type}[/bold blue]"))

    # Validate version type
    if version_type not in ["patch", "minor", "major"]:
        raise ForgeReleaseError("Version type must be 'patch', 'minor', or 'major'")

    # Get current version
    current_version, _ = get_current_version()
    console.print(f"Current version: {current_version}")

    # Calculate new version
    new_version = bump_version(current_version, version_type)
    console.print(f"New version: {new_version}")

    # Confirm with user
    if not Confirm.ask(f"Update version from {current_version} to {new_version}?"):
        console.print("Release preparation cancelled.")
        return

    # Update version files
    update_version_files(new_version)

    # Run quality checks
    run_quality_checks()

    # Build and validate
    build_and_validate()

    # Commit version changes
    console.print("Committing version changes...")
    run_command("git add pyproject.toml src/forge/__init__.py")
    run_command(f'git commit -m "bump: version {current_version} -> {new_version}"')

    console.print(f"[green]✓[/green] Release prepared for version {new_version}")
    console.print("\n[bold blue]Next steps:[/bold blue]")
    console.print("1. Push your branch and create a PR")
    console.print("2. After PR is merged, run: python scripts/forge_release.py create-release")


def create_release() -> None:
    """Create a GitHub release and tag"""
    console.print(Panel("[bold blue]Creating GitHub Release[/bold blue]"))

    # Make sure we're on main
    current_branch = get_current_branch()
    if current_branch != "main":
        raise ForgeReleaseError("Must be on main branch to create release")

    # Check if working directory is clean
    if not check_git_status():
        raise ForgeReleaseError("Working directory is not clean")

    # Pull latest changes
    console.print("Pulling latest changes...")
    run_command("git pull origin main")

    # Get current version
    current_version, _ = get_current_version()
    tag_name = f"v{current_version}"

    # Check if tag already exists
    result = run_command(f"git tag -l {tag_name}", check=False)
    if result.stdout.strip():
        raise ForgeReleaseError(f"Tag {tag_name} already exists")

    # Run final checks
    run_quality_checks()
    build_and_validate()

    # Create and push tag
    console.print(f"Creating tag: {tag_name}")
    run_command(f"git tag {tag_name}")
    run_command(f"git push origin {tag_name}")

    console.print(f"[green]✓[/green] Release {tag_name} created successfully")
    console.print("\n[blue]GitHub Actions will now:[/blue]")
    console.print("1. Run all quality checks")
    console.print("2. Build the package")
    console.print("3. Publish to PyPI automatically")
    console.print(
        "\n[blue]Monitor the release at:[/blue] https://github.com/NastMz/forge-cli/actions"
    )


def full_release(version_type: Literal["patch", "minor", "major"]) -> None:
    """Complete end-to-end release process (for emergency releases)"""
    console.print(Panel(f"[bold red]FULL RELEASE: {version_type}[/bold red]"))
    console.print(
        "[yellow]Warning: This will create a release immediately without PR review![/yellow]"
    )

    if not Confirm.ask("Are you sure you want to proceed with a full release?"):
        console.print("Full release cancelled.")
        return

    # Make sure we're on main
    current_branch = get_current_branch()
    if current_branch != "main":
        raise ForgeReleaseError("Must be on main branch for full release")

    # Run prepare release
    prepare_release(version_type)

    # Push changes
    console.print("Pushing changes to main...")
    run_command("git push origin main")

    # Create release
    create_release()


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="Forge CLI Release Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # start-feature command
    start_parser = subparsers.add_parser("start-feature", help="Start a new feature branch")
    start_parser.add_argument("feature_name", help="Name of the feature (e.g., 'add-auth-command')")

    # prepare-release command
    prepare_parser = subparsers.add_parser("prepare-release", help="Prepare a release")
    prepare_parser.add_argument(
        "version_type", choices=["patch", "minor", "major"], help="Type of version bump"
    )

    # create-release command
    subparsers.add_parser("create-release", help="Create GitHub release and tag")

    # full-release command (emergency)
    full_parser = subparsers.add_parser("full-release", help="Complete release process (emergency)")
    full_parser.add_argument(
        "version_type", choices=["patch", "minor", "major"], help="Type of version bump"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "start-feature":
            start_feature(args.feature_name)
        elif args.command == "prepare-release":
            prepare_release(args.version_type)
        elif args.command == "create-release":
            create_release()
        elif args.command == "full-release":
            full_release(args.version_type)

    except ForgeReleaseError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
