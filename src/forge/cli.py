"""
Main CLI module for Forge - Clean Architecture Flask scaffolding CLI.

This module serves as the primary entry point for the Forge CLI tool, providing
project scaffolding capabilities for Clean Architecture Flask applications.
It integrates all command modules and handles project template rendering.

Key features:
- New project creation from templates
- Jinja2-based template rendering with variable substitution
- Directory and file path templating
- Package structure initialization
- Integration with run, database, and generate commands
- Interactive user prompts and confirmations
- Rich console output with colored messages

Commands:
- forge new <project-name>: Create a new Clean Architecture project
- forge run: Development server utilities
- forge db: Database migration commands
- forge generate: Code generation utilities
"""

from __future__ import annotations
import os
import shutil
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.prompt import Confirm
from jinja2 import Environment, FileSystemLoader

from .commands.run_cmd import run as run_cmd
from .commands.db_cmd import db as db_cmd
from .commands.generate_cmd import generate as generate_cmd
from .utils.fs import ensure_init_files

app = typer.Typer(help="Forge – Clean Architecture Flask scaffolding CLI")
app.add_typer(run_cmd, name="run")
app.add_typer(db_cmd, name="db")
app.add_typer(generate_cmd, name="generate")

# Default template to use for new projects
TEMPLATE = "clean"


def _project_exists(dst: Path) -> bool:
    """
    Check if a project directory exists and is not empty.

    Args:
        dst: Destination path to check

    Returns:
        True if the directory exists and contains files/folders, False otherwise
    """
    return dst.exists() and any(dst.iterdir())


def _render_path(env: Environment, rel: Path, context: dict[str, str]) -> Path:
    """
    Render each segment of a relative path as a Jinja2 template.

    This function treats each part of a path (directory names, filenames) as
    Jinja2 templates, allowing for dynamic path generation based on context
    variables like {{package_name}}.

    Args:
        env: Jinja2 environment for template rendering
        rel: Relative path with potentially templated segments
        context: Template variables for rendering

    Returns:
        New Path with all segments rendered using the provided context

    Example:
        rel = Path("{{package_name}}/domain/{{entity_name}}")
        context = {"package_name": "myapp", "entity_name": "user"}
        Result: Path("myapp/domain/user")
    """
    parts = [env.from_string(seg).render(**context) for seg in rel.parts]
    return Path(*parts)


def _render_template_dir(template_dir: Path, out_dir: Path, context: dict[str, str]) -> None:
    """
    Render an entire template directory structure with Jinja2 processing.

    Recursively processes a template directory, rendering both directory names
    and file contents as Jinja2 templates. Handles both text files (rendered
    as templates) and binary files (copied as-is).

    Args:
        template_dir: Source template directory to process
        out_dir: Destination directory for rendered output
        context: Template variables for Jinja2 rendering

    Process:
        1. Walk through all directories and files in template_dir
        2. Render directory paths using Jinja2 (allows {{variable}} in folder names)
        3. Render file names using Jinja2 (allows {{variable}} in file names)
        4. For text files: render content as Jinja2 template
        5. For binary files: copy directly without processing

    Template Features:
        - Directory names can contain variables: "{{package_name}}/domain"
        - File names can contain variables: "{{entity_name}}.py"
        - File contents are processed as Jinja2 templates
        - Binary files are detected and copied without modification

    Example:
        Template structure:
        templates/clean/
          src/
            {{package_name}}/
              main.py

        With context = {"package_name": "myapp"}
        Results in:
        output/
          src/
            myapp/
              main.py (with template variables rendered)
    """
    env = Environment(loader=FileSystemLoader(str(template_dir)), keep_trailing_newline=True)

    for root, _, files in os.walk(template_dir):
        root_path = Path(root)
        rel = root_path.relative_to(template_dir)

        # Render directory path with template variables
        rendered_rel = _render_path(env, rel, context)
        (out_dir / rendered_rel).mkdir(parents=True, exist_ok=True)

        for name in files:
            # Render filename with template variables
            rendered_name = env.from_string(name).render(**context)
            src_path = root_path / name
            out_path = out_dir / rendered_rel / rendered_name
            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Render file content as template, or copy binary files as-is
            try:
                text = src_path.read_text(encoding="utf-8")
                rendered = env.from_string(text).render(**context)
                out_path.write_text(rendered, encoding="utf-8")
            except UnicodeDecodeError:
                # Handle binary files by copying them directly
                shutil.copy2(src_path, out_path)


@app.command()
def new(
    project_name: str = typer.Argument(..., help="Destination folder / package name"),
    package: Optional[str] = typer.Option(
        None, help="Python package name (defaults to project_name)"
    ),
) -> None:
    """
    Create a new Clean Architecture Flask project from template.

    Generates a complete project structure following Clean Architecture principles,
    with proper separation of concerns across domain, application, infrastructure,
    and interface layers.

    Args:
        project_name: Name for the project directory and default package name.
                     Will be used as the folder name and Python package identifier.
        package: Optional custom Python package name. If not provided, defaults
                to project_name with hyphens converted to underscores.

    Generated Structure:
        project_name/
        ├── src/
        │   └── package_name/
        │       ├── __init__.py
        │       ├── main.py              # Application entry point
        │       ├── shared/              # Shared utilities (DI, config, logging)
        │       ├── domain/              # Business entities and rules
        │       ├── app/                 # Application services and use cases
        │       ├── infra/               # Infrastructure implementations
        │       │   └── db/              # Database configurations
        │       └── interfaces/          # External interfaces
        │           └── http/            # REST API controllers
        ├── tests/                       # Test files
        ├── migrations/                  # Database migrations (after db init)
        ├── pyproject.toml              # Project configuration
        ├── .env.example                # Environment variables template
        └── README.md                   # Project documentation

    Examples:
        forge new myapp                 # Creates myapp/ with myapp package
        forge new my-shop --package shop # Creates my-shop/ with shop package

    Interactive Features:
        - Prompts for confirmation if target directory exists and is not empty
        - Option to overwrite existing projects
        - Colored console output for user feedback

    Post-Creation Steps:
        1. Navigate to project directory: cd project_name
        2. Install dependencies: pip install -e '.[dev]'
        3. Copy environment config: cp .env.example .env
        4. Run the application: python -m package_name

    Note:
        The package name will have hyphens automatically converted to underscores
        to ensure valid Python identifier format.
    """
    # Resolve destination path
    dst = Path(project_name).resolve()

    # Check if project directory exists and handle overwrite confirmation
    if _project_exists(dst):
        if not Confirm.ask(f"[yellow]{dst} is not empty. Overwrite?[/yellow]"):
            rprint("[red]Aborted.[/red]")
            raise typer.Exit(1)

        # Clean existing directory contents
        for path in dst.iterdir():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    else:
        # Create new directory
        dst.mkdir(parents=True, exist_ok=True)

    # Determine package name (normalize hyphens to underscores)
    pkg = (package or project_name).strip().replace("-", "_")

    # Locate and render template
    template_dir = Path(__file__).with_suffix("").parent / "templates" / TEMPLATE
    context = {"project_name": project_name, "package_name": pkg}
    _render_template_dir(template_dir, dst, context)

    # Initialize Python package structure
    pkg_root = dst / "src" / pkg
    ensure_init_files(
        pkg_root,
        [
            "",  # src/package/__init__.py
            "shared",  # Shared utilities (DI, config, logging)
            "domain",  # Domain entities and business rules
            "app",  # Application services and use cases
            "infra",  # Infrastructure implementations
            "infra/db",  # Database configuration and base classes
            "interfaces",  # External interfaces
            "interfaces/http",  # HTTP/REST API controllers
        ],
    )

    # Success message with next steps
    rprint("[green]Project created![/green]")
    rprint(
        f"""Next steps:
  1) cd {dst.name}
  2) pip install -e '.[dev]'
  3) cp .env.example .env
  4) forge run dev -p 8000
"""
    )


if __name__ == "__main__":
    """
    Entry point for direct script execution.

    Allows the CLI to be run directly with: python -m forge.cli
    or when the module is executed as a script.
    """
    app()
