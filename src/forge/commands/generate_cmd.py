from __future__ import annotations
import re
from pathlib import Path
import typer
from rich import print as rprint
from jinja2 import Environment, DictLoader
from ..utils.fs import ensure_init_files

generate = typer.Typer(help="Clean Architecture generators")

# --- templates ---
ENTITY_TMPL = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class {{Entity}}:
    id: int | None
    name: str
"""

REPO_IFACE_TMPL = """
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterable, Optional
from .entities import {{Entity}}

class I{{Entity}}Repository(ABC):
    @abstractmethod
    def get(self, id: int) -> Optional[{{Entity}}]: ...
    
    @abstractmethod
    def add(self, e: {{Entity}}) -> {{Entity}}: ...
    
    @abstractmethod
    def list(self) -> Iterable[{{Entity}}]: ...
"""

REPO_SQLA_TMPL = """
from __future__ import annotations
from typing import Iterable, Optional
from sqlalchemy import select, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, Session
from ...infra.db.base import Base
from ...domain.{{bc}}.entities import {{Entity}}
from ...domain.{{bc}}.repositories import I{{Entity}}Repository

class {{Entity}}Row(Base):
    __tablename__ = "{{table}}"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))


class SqlAlchemy{{Entity}}Repository(I{{Entity}}Repository):
    def __init__(self, session_factory):
        self._sf = session_factory
        
    def get(self, id: int) -> Optional[{{Entity}}]:
        with self._sf() as s:  # type: Session
            r = s.get({{Entity}}Row, id)
            return {{Entity}}(id=r.id, name=r.name) if r else None
            
    def add(self, e: {{Entity}}) -> {{Entity}}:
        with self._sf() as s:
            r = {{Entity}}Row(name=e.name)
            s.add(r); s.commit(); s.refresh(r)
            return {{Entity}}(id=r.id, name=r.name)
            
    def list(self) -> Iterable[{{Entity}}]:
        with self._sf() as s:
            return [{{Entity}}(id=r.id, name=r.name) for r in s.scalars(select({{Entity}}Row)).all()]
"""

SERVICE_TMPL = """
from __future__ import annotations
from ...domain.{{bc}}.repositories import I{{Entity}}Repository
from ...domain.{{bc}}.entities import {{Entity}}

class {{Entity}}Service:
    def __init__(self, repo: I{{Entity}}Repository):
        self._repo = repo
        
    def create(self, name: str) -> {{Entity}}:
        return self._repo.add({{Entity}}(id=None, name=name))
        
    def list(self) -> list[{{Entity}}]:
        return list(self._repo.list())
"""

CONTROLLER_TMPL = """
from __future__ import annotations
from flask import Blueprint, request, jsonify
from ....shared.di import Container

bp = Blueprint("{{name}}", __name__, url_prefix="/{{name}}")
_container: Container | None = None

def init_controller(container: Container) -> None:
    global _container
    _container = container

@bp.post("")
def create_{{name}}():
    if _container is None:
            raise RuntimeError("Controller not initialized")
    svc = _container.get("{{bc}}.{{name}}.service")
    data = request.get_json(force=True)
    item = svc.create(data.get("name", ""))
    return jsonify({"id": item.id, "name": item.name}), 201

@bp.get("")
def list_{{name}}():
    if _container is None:
            raise RuntimeError("Controller not initialized")
    svc = _container.get("{{bc}}.{{name}}.service")
    items = svc.list()
    return jsonify([{"id": i.id, "name": i.name} for i in items])
"""

API_REG_PATCH = """
from flask import Blueprint
from .{{bc}}.controller import bp as {{name}}_bp, init_controller as init_{{name}}_controller

def register_{{name}}(api: Blueprint, container) -> None:
    init_{{name}}_controller(container)
    api.register_blueprint({{name}}_bp)
"""


@generate.command("resource")
def resource(bc: str = typer.Argument(..., help="Bounded context (e.g. catalog)"),
             entity: str = typer.Argument(..., help="Entity name (e.g. Product)")):
    """Generate domain entity + repo (SQLA) + service + controller and wire them."""
    pkg = _detect_package()
    bc = bc.replace("-", "_")
    Entity = entity[0].upper() + entity[1:]
    name = entity[0].lower() + entity[1:]
    table = name + "s"

    env = Environment(loader=DictLoader({
        "entity": ENTITY_TMPL,
        "repo_iface": REPO_IFACE_TMPL,
        "repo_sqla": REPO_SQLA_TMPL,
        "service": SERVICE_TMPL,
        "controller": CONTROLLER_TMPL,
        "api_reg": API_REG_PATCH,
    }))

    pkg_root = Path("src") / pkg
    ensure_init_files(pkg_root, [
        f"domain/{bc}",
        f"app/{bc}",
        f"infra/{bc}",
        f"interfaces/http/{bc}",
    ])

    # domain
    (Path(f"src/{pkg}/domain/{bc}")).mkdir(parents=True, exist_ok=True)
    (Path(f"src/{pkg}/domain/{bc}/entities.py")).write_text(
        env.get_template("entity").render(Entity=Entity), encoding="utf-8")
    (Path(f"src/{pkg}/domain/{bc}/repositories.py")).write_text(
        env.get_template("repo_iface").render(Entity=Entity), encoding="utf-8")

    # infra
    (Path(f"src/{pkg}/infra/{bc}")).mkdir(parents=True, exist_ok=True)
    (Path(f"src/{pkg}/infra/{bc}/repo_sqlalchemy.py")).write_text(env.get_template(
        "repo_sqla").render(Entity=Entity, bc=bc, table=table), encoding="utf-8")

    # app
    (Path(f"src/{pkg}/app/{bc}")).mkdir(parents=True, exist_ok=True)
    (Path(f"src/{pkg}/app/{bc}/services.py")).write_text(
        env.get_template("service").render(Entity=Entity, bc=bc), encoding="utf-8")

    # interfaces/http
    ih = Path(f"src/{pkg}/interfaces/http/{bc}")
    ih.mkdir(parents=True, exist_ok=True)
    (ih / "controller.py").write_text(env.get_template("controller").render(bc=bc,
                                                                            name=name), encoding="utf-8")

    # --- register into API surface (robust, idempotent) ---
    api_file = Path(f"src/{pkg}/interfaces/http/api.py")
    api_content = api_file.read_text(encoding="utf-8")

    import_line = f"from .{bc}.controller import bp as {name}_bp, init_controller as init_{name}_controller"
    register_line = f"    api.register_blueprint({name}_bp)"
    init_line = f"    init_{name}_controller(container)"

    def insert_once(text: str, needle: str, anchor: str, before: bool = False, fallback_pattern: str | None = None) -> str:
        if needle in text:
            return text
        if anchor in text:
            return text.replace(anchor, (needle + "\n" + anchor) if not before else (anchor + "\n" + needle))
        if fallback_pattern:
            m = re.search(fallback_pattern, text, re.DOTALL)
            if m:
                start, end = m.span()
                if before:
                    return text[:start] + needle + "\n" + text[start:]
                else:
                    return text[:end] + "\n" + needle + text[end:]
        return text.rstrip() + "\n" + needle + "\n"

    api_content = insert_once(
        api_content,
        import_line,
        anchor="# [forge:auto-imports]",
        fallback_pattern=r"(?ms)(^from\s+[^\n]+$|^import\s+[^\n]+$)(?:\n(?:from\s+[^\n]+$|import\s+[^\n]+$))*"
    )
    api_content = insert_once(
        api_content,
        register_line,
        anchor="    # [forge:auto-register]",
        fallback_pattern=r"(?ms)def\s+build_api_blueprint\([^\)]*\):\s*\n(.*?)\n\s*return\s+api"
    )
    api_content = insert_once(
        api_content,
        init_line,
        anchor="    # [forge:auto-init]",
        fallback_pattern=r"(?ms)def\s+register_http\([^\)]*\):\s*\n(.*?)\n\s*app\.register_blueprint\(api_bp\)"
    )
    api_file.write_text(api_content, encoding="utf-8")

    # --- DI wiring (imports + register_<name> + call in register_features) ---
    wiring = Path(f"src/{pkg}/shared/di_wiring.py")
    w = wiring.read_text(encoding="utf-8")

    import_repo = f"from {pkg}.infra.{bc}.repo_sqlalchemy import SqlAlchemy{Entity}Repository\n"
    import_service = f"from {pkg}.app.{bc}.services import {Entity}Service\n"

    def insert_after_line(text: str, after_pattern: str, payload: str) -> str:
        m = re.search(after_pattern, text)
        if not m:
            return text if payload in text else (payload + text)
        idx = m.end()
        return text if payload in text else (text[:idx] + payload + text[idx:])

    w = insert_after_line(
        w,
        after_pattern=r"from\s+\.\.\s*infra\.db\.base\s+import\s+init_engine\s*\n",
        payload=import_repo + import_service
    )

    func_head = f"def register_{name}(container"
    if func_head not in w:
        w += (
            f"\n\n\ndef register_{name}(container: Container) -> None:\n"
            f"    container.register(\n"
            f"        \"{bc}.{name}.repo\",\n"
            f"        lambda: SqlAlchemy{Entity}Repository(container.get(\"db.session_factory\")),\n"
            f"    )\n"
            f"    container.register(\n"
            f"        \"{bc}.{name}.service\",\n"
            f"        container.factory({Entity}Service, repo=\"{bc}.{name}.repo\"),\n"
            f"    )\n"
        )

    call_line = f"    register_{name}(container)\n"
    if "def register_features(" in w and call_line not in w:
        # inject just before end of function or after header
        w = re.sub(
            r"(def\s+register_features\(.*?\):\s*\n)",
            r"\1" + call_line,
            w,
            count=1,
            flags=re.DOTALL,
        )

    wiring.write_text(w, encoding="utf-8")

    rprint(
        f"[green]Resource generated:[/green] {bc}.{Entity} (domain/app/infra/interfaces + wiring)")


def _detect_package() -> str:
    for p in Path("src").glob("*/main.py"):
        return p.parent.name
    raise SystemExit("Could not detect src/<package>")
