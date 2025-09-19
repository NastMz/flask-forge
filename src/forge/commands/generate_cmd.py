"""
Generate command module for Forge CLI.

This module provides code generation capabilities following Clean Architecture principles.
It includes templates and commands to scaffold complete CRUD resources with proper
layering (domain, application, infrastructure, and interface layers).

The main functionality includes:
- Entity generation with domain models
- Repository pattern implementation (interface + SQLAlchemy)
- Service layer for business logic
- HTTP controllers with Flask blueprints
- Automatic dependency injection wiring
"""

from __future__ import annotations
import re
from pathlib import Path
import typer
from rich import print as rprint
from jinja2 import Environment, DictLoader
from ..utils.fs import ensure_init_files

generate = typer.Typer(help="Clean Architecture generators")

# --- Jinja2 Templates for Code Generation ---
# These templates define the structure for different architectural layers

# Domain Entity Template - Represents core business objects
ENTITY_TMPL = """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class {{Entity}}:
    id: int | None
    name: str
"""

# Repository Interface Template - Defines data access contract
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

# SQLAlchemy Repository Implementation Template - Data access layer
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

# Service Layer Template - Business logic and use cases
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

# HTTP Controller Template - REST API endpoints
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

# API Registration Template - Wires controllers into the main API
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
    """
    Generate a complete CRUD resource following Clean Architecture principles.

    This command creates:
    - Domain entity with dataclass
    - Repository interface and SQLAlchemy implementation
    - Service layer for business logic
    - HTTP controller with REST endpoints
    - Automatic dependency injection wiring

    Args:
        bc: Bounded context name (e.g., 'catalog', 'users')
        entity: Entity name in PascalCase (e.g., 'Product', 'User')

    Example:
        forge generate resource catalog Product

    This will create a complete Product resource within the catalog bounded context.
    """
    pkg = _detect_package()
    bc = bc.replace("-", "_")  # Normalize bounded context name
    entity_class = entity[0].upper() + entity[1:]  # PascalCase for class names
    entity_name = entity[0].lower() + entity[1:]   # camelCase for instances
    table_name = entity_name + "s"  # Pluralized table name

    # Generate all code files
    _generate_code_files(pkg, bc, entity_class, entity_name, table_name)

    # Wire into API surface
    _wire_api_integration(pkg, bc, entity_name)

    # Setup dependency injection
    _setup_dependency_injection(pkg, bc, entity_class, entity_name)

    rprint(
        f"[green]Resource generated:[/green] {bc}.{entity_class} (domain/app/infra/interfaces + wiring)")


def _generate_code_files(pkg: str, bc: str, entity_class: str, entity_name: str, table_name: str) -> None:
    """Generate all the code files for the resource."""
    env = Environment(loader=DictLoader({
        "entity": ENTITY_TMPL,
        "repo_iface": REPO_IFACE_TMPL,
        "repo_sqla": REPO_SQLA_TMPL,
        "service": SERVICE_TMPL,
        "controller": CONTROLLER_TMPL,
        "api_reg": API_REG_PATCH,
    }))

    pkg_root = Path("src") / pkg

    # Ensure all necessary directories and __init__.py files exist
    ensure_init_files(pkg_root, [
        f"domain/{bc}",
        f"app/{bc}",
        f"infra/{bc}",
        f"interfaces/http/{bc}",
    ])

    # Generate domain layer files
    _generate_domain_files(pkg, bc, entity_class, env)

    # Generate infrastructure layer files
    _generate_infrastructure_files(pkg, bc, entity_class, table_name, env)

    # Generate application layer files
    _generate_application_files(pkg, bc, entity_class, env)

    # Generate interface layer files
    _generate_interface_files(pkg, bc, entity_name, env)


def _generate_domain_files(pkg: str, bc: str, entity_class: str, env: Environment) -> None:
    """Generate domain layer files (entities and repository interfaces)."""
    domain_path = Path(f"src/{pkg}/domain/{bc}")
    domain_path.mkdir(parents=True, exist_ok=True)

    # Generate entity
    (domain_path / "entities.py").write_text(
        env.get_template("entity").render(Entity=entity_class), encoding="utf-8")

    # Generate repository interface
    (domain_path / "repositories.py").write_text(
        env.get_template("repo_iface").render(Entity=entity_class), encoding="utf-8")


def _generate_infrastructure_files(pkg: str, bc: str, entity_class: str, table_name: str, env: Environment) -> None:
    """Generate infrastructure layer files (repository implementations)."""
    infra_path = Path(f"src/{pkg}/infra/{bc}")
    infra_path.mkdir(parents=True, exist_ok=True)

    # Generate SQLAlchemy repository implementation
    (infra_path / "repo_sqlalchemy.py").write_text(
        env.get_template("repo_sqla").render(
            Entity=entity_class, bc=bc, table=table_name),
        encoding="utf-8")


def _generate_application_files(pkg: str, bc: str, entity_class: str, env: Environment) -> None:
    """Generate application layer files (services)."""
    app_path = Path(f"src/{pkg}/app/{bc}")
    app_path.mkdir(parents=True, exist_ok=True)

    # Generate service
    (app_path / "services.py").write_text(
        env.get_template("service").render(Entity=entity_class, bc=bc), encoding="utf-8")


def _generate_interface_files(pkg: str, bc: str, entity_name: str, env: Environment) -> None:
    """Generate interface layer files (HTTP controllers)."""
    interface_path = Path(f"src/{pkg}/interfaces/http/{bc}")
    interface_path.mkdir(parents=True, exist_ok=True)

    # Generate HTTP controller
    (interface_path / "controller.py").write_text(
        env.get_template("controller").render(bc=bc, name=entity_name), encoding="utf-8")


def _wire_api_integration(pkg: str, bc: str, entity_name: str) -> None:
    """Wire the new resource into the API surface with robust, idempotent operations."""
    api_file = Path(f"src/{pkg}/interfaces/http/api.py")
    api_content = api_file.read_text(encoding="utf-8")

    # Define the lines to be inserted
    import_line = f"from .{bc}.controller import bp as {entity_name}_bp, init_controller as init_{entity_name}_controller"
    register_line = f"    api.register_blueprint({entity_name}_bp)"
    init_line = f"    init_{entity_name}_controller(container)"

    # Insert import, register, and init lines
    api_content = _insert_line_once(api_content, import_line, "# [forge:auto-imports]",
                                    r"(?ms)(^from\s+[^\n]+$|^import\s+[^\n]+$)(?:\n(?:from\s+[^\n]+$|import\s+[^\n]+$))*")

    api_content = _insert_line_once(api_content, register_line, "    # [forge:auto-register]",
                                    r"(?ms)def\s+build_api_blueprint\([^\)]*\):\s*\n(.*?)\n\s*return\s+api")

    api_content = _insert_line_once(api_content, init_line, "    # [forge:auto-init]",
                                    r"(?ms)def\s+register_http\([^\)]*\):\s*\n(.*?)\n\s*app\.register_blueprint\(api_bp\)")

    api_file.write_text(api_content, encoding="utf-8")


def _setup_dependency_injection(pkg: str, bc: str, entity_class: str, entity_name: str) -> None:
    """Setup dependency injection wiring for the new resource."""
    wiring_file = Path(f"src/{pkg}/shared/di_wiring.py")
    wiring_content = wiring_file.read_text(encoding="utf-8")

    # Add imports for repository and service
    import_repo = f"from {pkg}.infra.{bc}.repo_sqlalchemy import SqlAlchemy{entity_class}Repository\n"
    import_service = f"from {pkg}.app.{bc}.services import {entity_class}Service\n"

    wiring_content = _insert_after_line(
        wiring_content,
        r"from\s+\.\.\s*infra\.db\.base\s+import\s+init_engine\s*\n",
        import_repo + import_service
    )

    # Add registration function if it doesn't exist
    func_signature = f"def register_{entity_name}(container"
    if func_signature not in wiring_content:
        registration_func = (
            f"\n\n\ndef register_{entity_name}(container: Container) -> None:\n"
            f"    \"\"\"Register {entity_class} dependencies in the DI container.\"\"\"\n"
            f"    container.register(\n"
            f"        \"{bc}.{entity_name}.repo\",\n"
            f"        lambda: SqlAlchemy{entity_class}Repository(container.get(\"db.session_factory\")),\n"
            f"    )\n"
            f"    container.register(\n"
            f"        \"{bc}.{entity_name}.service\",\n"
            f"        container.factory({entity_class}Service, repo=\"{bc}.{entity_name}.repo\"),\n"
            f"    )\n"
        )
        wiring_content += registration_func

    # Add call to registration function in register_features
    call_line = f"    register_{entity_name}(container)\n"
    if "def register_features(" in wiring_content and call_line not in wiring_content:
        wiring_content = re.sub(
            r"(def\s+register_features\(.*?\):\s*\n)",
            r"\1" + call_line,
            wiring_content,
            count=1,
            flags=re.DOTALL,
        )

    wiring_file.write_text(wiring_content, encoding="utf-8")


def _insert_line_once(text: str, needle: str, anchor: str, fallback_pattern: str | None = None) -> str:
    """
    Insert a line into text only if it doesn't already exist.

    Args:
        text: The text to modify
        needle: The line to insert
        anchor: The anchor line to insert after
        fallback_pattern: Regex pattern for fallback insertion point

    Returns:
        Modified text with the needle inserted
    """
    if needle in text:
        return text
    if anchor in text:
        return text.replace(anchor, anchor + "\n" + needle)
    if fallback_pattern:
        match = re.search(fallback_pattern, text, re.DOTALL)
        if match:
            _, end = match.span()
            return text[:end] + "\n" + needle + text[end:]
    return text.rstrip() + "\n" + needle + "\n"


def _insert_after_line(text: str, after_pattern: str, payload: str) -> str:
    """
    Insert payload after a line matching the given pattern.

    Args:
        text: The text to modify
        after_pattern: Regex pattern to find insertion point
        payload: Text to insert

    Returns:
        Modified text with payload inserted
    """
    match = re.search(after_pattern, text)
    if not match:
        return text if payload in text else (payload + text)
    idx = match.end()
    return text if payload in text else (text[:idx] + payload + text[idx:])


def _detect_package() -> str:
    """
    Detect the package name by looking for main.py in src/ subdirectories.

    Returns:
        Package name

    Raises:
        SystemExit: If no package is detected
    """
    for path in Path("src").glob("*/main.py"):
        return path.parent.name
    raise SystemExit("Could not detect src/<package>")
