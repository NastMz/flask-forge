"""
Database command module for Forge CLI.

This module provides database migration and management capabilities using Alembic.
It handles the setup and management of database schemas in Clean Architecture projects,
with automatic model discovery and robust migration generation.

Key features:
- Automatic Alembic configuration setup
- Eager loading of all SQLAlchemy models from infrastructure layer
- Database migration generation and execution
- Support for upgrade/downgrade operations
- Environment-based database URL configuration
"""

from __future__ import annotations
import subprocess
from pathlib import Path
import typer

DB_FOLDER = "migrations"

db = typer.Typer(help="Database / Alembic commands")


@db.command("init")
def init(rewrite: bool = typer.Option(False, help="Rewrite Alembic env.py if it exists")):
    """
    Initialize Alembic for database migrations.

    Sets up the complete Alembic environment including:
    - migrations/ directory structure
    - env.py with eager model loading
    - alembic.ini configuration file
    - script.py.mako template for migrations

    The generated env.py automatically discovers and imports all SQLAlchemy
    models from the infrastructure layer, ensuring proper table detection.

    Args:
        rewrite: Force rewrite of env.py even if it exists

    Example:
        forge db init
        forge db init --rewrite  # Force regenerate env.py
    """
    pkg = _detect_package_name()

    # Create migrations directory structure
    Path("migrations/versions").mkdir(parents=True, exist_ok=True)

    # Generate env.py with robust model discovery
    if rewrite or not Path("migrations/env.py").exists():
        _write_env_py(pkg)
        typer.echo("Created migrations/env.py (robust eager-import template).")

    # Create minimal alembic.ini configuration
    _create_alembic_ini()

    # Create migration template
    _create_migration_template()


def _create_alembic_ini() -> None:
    """Create minimal alembic.ini configuration file."""
    ini_file = Path("alembic.ini")
    if not ini_file.exists():
        ini_content = (
            "[alembic]\n"
            "script_location = migrations\n"
            "sqlalchemy.url = sqlite:///app.db\n"
        )
        ini_file.write_text(ini_content, encoding="utf-8")
        typer.echo("Created alembic.ini")


def _create_migration_template() -> None:
    """Create script.py.mako template for migration files."""
    template_file = Path("migrations/script.py.mako")
    if not template_file.exists():
        template_content = '''"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '${up_revision}'
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)|n}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)|n}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)|n}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
'''
        template_file.write_text(template_content, encoding="utf-8")
        typer.echo("Created migrations/script.py.mako")


@db.command("migrate")
def migrate(message: str = typer.Option("auto", "--message", "-m")):
    """
    Generate a new database migration.

    Creates a new Alembic migration file by comparing the current database
    schema with the SQLAlchemy models. Uses autogenerate to detect changes
    automatically.

    Args:
        message: Description for the migration (default: "auto")

    Example:
        forge db migrate -m "Add user table"
        forge db migrate  # Uses "auto" as message

    Note:
        Must be run from the project root directory.
    """
    _ensure_root()
    subprocess.check_call(
        ["alembic", "revision", "--autogenerate", "-m", message])


@db.command("upgrade")
def upgrade(revision: str = typer.Argument("head")):
    """
    Upgrade database to a specific revision.

    Applies pending migrations to bring the database schema up to date.
    By default, upgrades to the latest revision ("head").

    Args:
        revision: Target revision (default: "head" for latest)

    Examples:
        forge db upgrade           # Upgrade to latest
        forge db upgrade abc123    # Upgrade to specific revision
        forge db upgrade +1        # Upgrade one revision forward

    Note:
        Must be run from the project root directory.
    """
    _ensure_root()
    subprocess.check_call(["alembic", "upgrade", revision])


@db.command("downgrade")
def downgrade(revision: str = typer.Argument("-1")):
    """
    Downgrade database to a previous revision.

    Rolls back database migrations to undo schema changes.
    By default, downgrades by one revision.

    Args:
        revision: Target revision (default: "-1" for one step back)

    Examples:
        forge db downgrade         # Downgrade one revision
        forge db downgrade abc123  # Downgrade to specific revision
        forge db downgrade -2      # Downgrade two revisions back
        forge db downgrade base    # Downgrade to initial state

    Warning:
        Downgrading can result in data loss. Use with caution.

    Note:
        Must be run from the project root directory.
    """
    _ensure_root()
    subprocess.check_call(["alembic", "downgrade", revision])


def _ensure_root() -> None:
    """
    Ensure the command is run from the project root directory.

    Validates that pyproject.toml exists in the current directory,
    which indicates this is the project root.

    Raises:
        SystemExit: If pyproject.toml is not found in current directory
    """
    if not Path("pyproject.toml").exists():
        raise SystemExit("Run from project root (pyproject.toml not found)")


def _write_env_py(pkg: str) -> None:
    """
    Generate a robust env.py file for Alembic migrations.

    Creates an env.py that automatically discovers and imports all SQLAlchemy
    models from the infrastructure layer. This ensures that all mapped classes
    are registered with SQLAlchemy's metadata before migration generation.

    Key features:
    - Eager loading of all modules in the infra package
    - Environment variable support for DATABASE_URL
    - Proper error handling and logging
    - Support for both online and offline migration modes

    Args:
        pkg: Package name containing the infrastructure models
    """
    migrations_dir = Path("migrations")
    (migrations_dir / "versions").mkdir(parents=True, exist_ok=True)

    env_py_file = migrations_dir / "env.py"
    env_content = f'''# isort: skip_file
# ruff: noqa: E402
from __future__ import annotations
from pathlib import Path
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name and Path(config.config_file_name).exists():
    try:
        fileConfig(config.config_file_name, disable_existing_loggers=False)
    except KeyError:
        # alembic.ini is minimal and has no logging config -> ignore
        pass

def _load_metadata():
    """
    Load SQLAlchemy metadata with eager import of all infrastructure models.
    
    This function ensures all mapped classes are discovered by:
    1. Adding src/ to Python path
    2. Setting up DATABASE_URL from environment
    3. Importing Base from the infrastructure layer
    4. Eagerly importing all modules in the infra package
    5. Validating that tables were found
    
    Returns:
        SQLAlchemy metadata object with all mapped tables
    """
    # All imports *inside* the function so IDEs won't reorder them
    import os, sys, pkgutil, importlib
    from pathlib import Path

    # Ensure src/ on path BEFORE importing your package
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

    # Database URL (env var wins; default to sqlite in repo root)
    os.environ.setdefault("DATABASE_URL", "sqlite:///app.db")
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

    # Import Base and EAGER-LOAD ALL infra modules so mapped classes register
    from {pkg}.infra.db.base import Base
    import {pkg}.infra as infra_pkg

    count = 0
    for _, modname, _ in pkgutil.walk_packages(infra_pkg.__path__, infra_pkg.__name__ + "."):
        importlib.import_module(modname)
        count += 1

    tables = sorted(Base.metadata.tables)
    print(f"[alembic] eager-imported modules: {{count}}, mapped tables: {{tables}}")

    if not Base.metadata.tables:
        raise RuntimeError(
            "No mapped tables found. Ensure __init__.py exists under packages and "
            "your mapped classes (e.g., *Row(Base)) live under {pkg}.infra.*"
        )
    return Base.metadata

target_metadata = _load_metadata()

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    
    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation, we don't even need a DBAPI to be available.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    
    In this scenario we need to create an Engine and associate a connection
    with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''
    env_py_file.write_text(env_content, encoding="utf-8")


def _detect_package_name() -> str:
    """
    Detect the package name by looking for the base.py file.

    Searches for src/<package>/infra/db/base.py to determine the package
    structure and extract the package name.

    Returns:
        Package name (e.g., 'myapp' from src/myapp/infra/db/base.py)

    Raises:
        SystemExit: If the expected package structure is not found
    """
    for path in Path("src").glob("*/infra/db/base.py"):
        # src/<pkg>/infra/db/base.py  -> package = <pkg>
        return path.parent.parent.parent.name
    raise SystemExit("Could not find src/<package>/infra/db/base.py")
