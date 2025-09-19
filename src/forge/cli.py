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

TEMPLATE = "clean"


def _project_exists(dst: Path) -> bool:
    return dst.exists() and any(dst.iterdir())


def _render_path(env: Environment, rel: Path, context: dict) -> Path:
    """Render each segment of a relative path as a Jinja template."""
    parts = [env.from_string(seg).render(**context) for seg in rel.parts]
    return Path(*parts)


def _render_template_dir(template_dir: Path, out_dir: Path, context: dict) -> None:
    env = Environment(loader=FileSystemLoader(
        str(template_dir)), keep_trailing_newline=True)

    for root, _, files in os.walk(template_dir):
        root_path = Path(root)
        rel = root_path.relative_to(template_dir)

        # render directory path
        rendered_rel = _render_path(env, rel, context)
        (out_dir / rendered_rel).mkdir(parents=True, exist_ok=True)

        for name in files:
            # render filename too
            rendered_name = env.from_string(name).render(**context)
            src_path = root_path / name
            out_path = out_dir / rendered_rel / rendered_name
            out_path.parent.mkdir(parents=True, exist_ok=True)

            # render file content, copy binary as-is
            try:
                text = src_path.read_text(encoding="utf-8")
                rendered = env.from_string(text).render(**context)
                out_path.write_text(rendered, encoding="utf-8")
            except UnicodeDecodeError:
                shutil.copy2(src_path, out_path)


@app.command()
def new(
    project_name: str = typer.Argument(...,
                                       help="Destination folder / package name"),
    package: Optional[str] = typer.Option(
        None, help="Python package name (defaults to project_name)"),
) -> None:
    """Create a new Clean Architecture Flask project."""
    dst = Path(project_name).resolve()
    if _project_exists(dst):
        if not Confirm.ask(f"[yellow]{dst} is not empty. Overwrite?[/yellow]"):
            rprint("[red]Aborted.[/red]")
            raise typer.Exit(1)
        for p in dst.iterdir():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
    else:
        dst.mkdir(parents=True, exist_ok=True)

    pkg = (package or project_name).strip().replace("-", "_")

    template_dir = Path(__file__).with_suffix(
        "").parent / "templates" / TEMPLATE
    context = {"project_name": project_name, "package_name": pkg}
    _render_template_dir(template_dir, dst, context)

    pkg_root = dst / "src" / pkg
    ensure_init_files(pkg_root, [
        "",             # src/shop/__init__.py
        "shared",
        "domain",
        "app",
        "infra",
        "infra/db",
        "interfaces",
        "interfaces/http",
    ])

    rprint("[green]Project created![/green]")
    rprint(f"""Next steps:
  1) cd {dst.name}
  2) pip install -e '.[dev]'
  3) cp .env.example .env
  4) python -m {pkg}
""")


if __name__ == "__main__":
    app()
