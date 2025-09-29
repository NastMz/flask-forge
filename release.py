#!/usr/bin/env python3
"""
Simple Release Script for Forge CLI

This is a user-friendly wrapper around the full forge_release.py script.
It provides the most common workflows in an easy-to-use format.

Usage:
    python release.py                    # Interactive mode
    python release.py feature <name>     # Start new feature
    python release.py patch              # Prepare patch release
    python release.py minor              # Prepare minor release
    python release.py major              # Prepare major release
    python release.py publish            # Create release (after PR merge)
"""

import sys
import subprocess
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table

console = Console()

SCRIPTS_DIR = Path(__file__).parent / "scripts"
FORGE_RELEASE_SCRIPT = SCRIPTS_DIR / "forge_release.py"


def run_forge_command(command: str, *args: str) -> int:
    """Run the main forge_release.py script with given command and args"""
    cmd = [sys.executable, str(FORGE_RELEASE_SCRIPT), command] + list(args)
    return subprocess.run(cmd).returncode


def show_help():
    """Show available commands"""
    console.print(Panel("[bold blue]Forge CLI Release Helper[/bold blue]"))

    table = Table(title="Available Commands")
    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Example", style="green")

    table.add_row(
        "feature <name>", "Start a new feature branch", "python release.py feature add-auth"
    )
    table.add_row("patch", "Prepare a patch release (bug fixes)", "python release.py patch")
    table.add_row("minor", "Prepare a minor release (new features)", "python release.py minor")
    table.add_row("major", "Prepare a major release (breaking changes)", "python release.py major")
    table.add_row("publish", "Create GitHub release and tag", "python release.py publish")
    table.add_row("interactive", "Interactive mode (guided workflow)", "python release.py")

    console.print(table)

    console.print("\n[bold blue]Typical Workflow:[/bold blue]")
    console.print("1. [cyan]python release.py feature my-feature[/cyan] - Start development")
    console.print("2. [dim]# ... implement your feature ...[/dim]")
    console.print("3. [cyan]python release.py patch[/cyan] - Prepare release")
    console.print("4. [dim]# ... create PR, get it reviewed and merged ...[/dim]")
    console.print("5. [cyan]python release.py publish[/cyan] - Create release")


def interactive_mode():
    """Interactive mode for guided workflow"""
    console.print(Panel("[bold blue]Interactive Release Mode[/bold blue]"))

    actions = [
        "Start a new feature",
        "Prepare a release (patch/minor/major)",
        "Create release (after PR is merged)",
        "Show help and exit",
    ]

    console.print("What would you like to do?")
    for i, action in enumerate(actions, 1):
        console.print(f"{i}. {action}")

    choice = Prompt.ask("Choose an option", choices=["1", "2", "3", "4"], default="4")

    if choice == "1":
        # Start feature
        feature_name = Prompt.ask("Enter feature name (e.g., 'add-auth-command')")
        if feature_name:
            return run_forge_command("start-feature", feature_name)

    elif choice == "2":
        # Prepare release
        console.print("\nWhat type of release?")
        console.print("• [green]patch[/green] - Bug fixes, small improvements (1.0.1 → 1.0.2)")
        console.print("• [blue]minor[/blue] - New features, backwards compatible (1.0.1 → 1.1.0)")
        console.print("• [red]major[/red] - Breaking changes (1.0.1 → 2.0.0)")

        version_type = Prompt.ask(
            "Version type", choices=["patch", "minor", "major"], default="patch"
        )
        return run_forge_command("prepare-release", version_type)

    elif choice == "3":
        # Create release
        if Confirm.ask("Are you on main branch with merged PR?"):
            return run_forge_command("create-release")
        else:
            console.print("[yellow]Please merge your PR first, then run this command[/yellow]")
            return 0

    elif choice == "4":
        show_help()
        return 0


def main():
    """Main entry point"""
    if not FORGE_RELEASE_SCRIPT.exists():
        console.print(f"[red]Error:[/red] Could not find {FORGE_RELEASE_SCRIPT}")
        return 1

    args = sys.argv[1:]

    # No arguments - interactive mode
    if not args:
        return interactive_mode()

    command = args[0].lower()

    # Handle special commands
    if command in ["help", "-h", "--help"]:
        show_help()
        return 0

    elif command == "feature":
        if len(args) < 2:
            feature_name = Prompt.ask("Enter feature name")
            if not feature_name:
                console.print("[red]Feature name is required[/red]")
                return 1
        else:
            feature_name = args[1]
        return run_forge_command("start-feature", feature_name)

    elif command in ["patch", "minor", "major"]:
        return run_forge_command("prepare-release", command)

    elif command == "publish":
        return run_forge_command("create-release")

    elif command == "interactive":
        return interactive_mode()

    else:
        console.print(f"[red]Unknown command:[/red] {command}")
        console.print("Run [cyan]python release.py help[/cyan] for available commands")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled[/yellow]")
        sys.exit(1)
