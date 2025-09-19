from __future__ import annotations
import subprocess
from pathlib import Path
import typer
from rich import print as rprint

DB_FOLDER = "migrations"

db = typer.Typer(help="Database / Alembic commands")


@db.command("init")
def init(rewrite: bool = typer.Option(False, help="Rewrite Alembic env.py if it exists")):
    pkg = _detect_package_name()
    Path("migrations/versions").mkdir(parents=True, exist_ok=True)

    # env.py (robust)
    if rewrite or not Path("migrations/env.py").exists():
        _write_env_py(pkg)
        typer.echo("Created migrations/env.py (robust eager-import template).")

    # alembic.ini (minimal)
    ini = Path("alembic.ini")
    if not ini.exists():
        ini.write_text(
            "[alembic]\nscript_location = migrations\nsqlalchemy.url = sqlite:///app.db\n",
            encoding="utf-8",
        )
        typer.echo("Created alembic.ini")

    # script.py.mako (required by alembic revision)
    mako = Path("migrations/script.py.mako")
    if not mako.exists():
        mako.write_text(
            '''"""${message}

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
''',
            encoding="utf-8",
        )
        typer.echo("Created migrations/script.py.mako")


@db.command("migrate")
def migrate(message: str = typer.Option("auto", "--message", "-m")):
    _ensure_root()
    subprocess.check_call(
        ["alembic", "revision", "--autogenerate", "-m", message])


@db.command("upgrade")
def upgrade(revision: str = typer.Argument("head")):
    _ensure_root()
    subprocess.check_call(["alembic", "upgrade", revision])


@db.command("downgrade")
def downgrade(revision: str = typer.Argument("-1")):
    _ensure_root()
    subprocess.check_call(["alembic", "downgrade", revision])


def _ensure_root() -> None:
    if not Path("pyproject.toml").exists():
        raise SystemExit("Run from project root (pyproject.toml not found)")


def _write_env_py(pkg: str) -> None:
    mig = Path("migrations")
    (mig / "versions").mkdir(parents=True, exist_ok=True)

    env_py = mig / "env.py"
    content = f'''# isort: skip_file
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
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
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
    env_py.write_text(content, encoding="utf-8")


def _detect_package_name() -> str:
    for p in Path("src").glob("*/infra/db/base.py"):
        # src/<pkg>/infra/db/base.py  -> package = <pkg>
        return p.parent.parent.parent.name
    raise SystemExit("Could not find src/<package>/infra/db/base.py")
