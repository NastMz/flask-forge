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
    pkg = module or _guess_package()
    if not pkg:
        rprint(
            "[red]Could not detect package. Pass --module <pkg> or run from project root.[/red]")
        raise typer.Exit(2)
    os.environ.setdefault("PORT", str(port))
    target = f"{pkg}.__main__" if (
        Path("src") / pkg / "__main__.py").exists() else f"{pkg}.main"
    rprint(f"[green]Starting[/green] python -m {target} on port {port}")
    runpy.run_module(target, run_name="__main__")


def _guess_package() -> str | None:
    src = Path("src")
    if not src.exists():
        return None
    for pkg_dir in src.iterdir():
        if (pkg_dir / "main.py").exists():
            return pkg_dir.name
    return None
