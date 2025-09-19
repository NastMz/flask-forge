"""
Run command module for Forge CLI.

This module provides utilities for running applications and services during development.
It handles automatic package detection, environment configuration, and module execution
for Clean Architecture projects.

Key features:
- Automatic package detection from project structure
- Development server startup with configurable ports
- Support for both __main__.py and main.py entry points
- Environment variable configuration (PORT)
- Rich console output with colored status messages
"""

from __future__ import annotations
import runpy
import os
from pathlib import Path
import typer
from rich import print as rprint

run = typer.Typer(help="Run utilities")


@run.command("dev")
def dev(module: str = typer.Option(None, help="Python package to run (auto-detect if omitted)"),
        port: int = typer.Option(8000, "--port", "-p")):
    """
    Start the development server for the application.

    Automatically detects the main package and runs it in development mode.
    Sets up the PORT environment variable and executes either __main__.py
    or main.py depending on what's available in the package.

    Args:
        module: Specific Python package to run. If omitted, auto-detects
                from the project structure by looking for main.py files
        port: Port number for the development server (default: 8000)

    Examples:
        forge run dev                    # Auto-detect package, use port 8000
        forge run dev --port 3000        # Auto-detect package, use port 3000
        forge run dev --module myapp     # Run specific package
        forge run dev -p 5000            # Short form for port option

    Entry Point Resolution:
        1. First tries to run <package>.__main__ (if __main__.py exists)
        2. Falls back to <package>.main (if main.py exists)

    Environment Variables:
        - PORT: Set to the specified port number for the application to use

    Note:
        Must be run from the project root directory containing a src/ folder.
    """
    # Detect target package
    pkg = module or _guess_package()
    if not pkg:
        rprint(
            "[red]Could not detect package. Pass --module <pkg> or run from project root.[/red]")
        raise typer.Exit(2)

    # Configure environment
    os.environ.setdefault("PORT", str(port))

    # Determine entry point
    target_module = _determine_entry_point(pkg)

    # Start the application
    rprint(f"[green]Starting[/green] python -m {target_module} on port {port}")
    try:
        runpy.run_module(target_module, run_name="__main__")
    except ModuleNotFoundError as e:
        rprint(
            f"[red]Error:[/red] Could not find module '{target_module}': {e}")
        raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]Error running application:[/red] {e}")
        raise typer.Exit(1)


def _determine_entry_point(pkg: str) -> str:
    """
    Determine the appropriate entry point module for the package.

    Checks for the existence of __main__.py and main.py files to decide
    which module should be used as the entry point.

    Args:
        pkg: Package name to check

    Returns:
        Full module path (e.g., "myapp.__main__" or "myapp.main")

    Priority:
        1. <package>.__main__ if __main__.py exists
        2. <package>.main if main.py exists
    """
    src_path = Path("src")
    pkg_path = src_path / pkg

    # Prefer __main__.py over main.py
    if (pkg_path / "__main__.py").exists():
        return f"{pkg}.__main__"
    else:
        return f"{pkg}.main"


def _guess_package() -> str | None:
    """
    Automatically detect the main package from the project structure.

    Searches the src/ directory for packages containing main.py files,
    which indicates they are likely the main application package.

    Returns:
        Package name if found, None if no suitable package is detected

    Detection Logic:
        - Looks for src/<package>/main.py files
        - Returns the first package found with this structure
        - Returns None if src/ directory doesn't exist or no packages found

    Example:
        For a project structure like:
        src/
          myapp/
            main.py
            __init__.py

        This function would return "myapp"
    """
    src_dir = Path("src")
    if not src_dir.exists():
        return None

    # Look for directories with main.py files
    for pkg_dir in src_dir.iterdir():
        if pkg_dir.is_dir() and (pkg_dir / "main.py").exists():
            return pkg_dir.name

    return None
