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

# Help text constants
BC_HELP = "Bounded context (e.g. catalog)"
ENTITY_HELP = "Entity name (e.g. Product)"
SERVICE_HELP = "Service name (e.g. ProductService)"
CONTROLLER_HELP = "Controller name (e.g. product)"

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
from .entity import {{Entity}}

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
from ....infra.db.base import Base
from ....domain.{{bc}}.{{entity_name}}.entity import {{Entity}}
from ....domain.{{bc}}.{{entity_name}}.repository import I{{Entity}}Repository

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
from ....domain.{{bc}}.{{entity_name}}.repository import I{{Entity}}Repository
from ....domain.{{bc}}.{{entity_name}}.entity import {{Entity}}

class {{Entity}}Service:
    def __init__(self, repo: I{{Entity}}Repository):
        self._repo = repo
        
    def create(self, name: str) -> {{Entity}}:
        return self._repo.add({{Entity}}(id=None, name=name))
        
    def list(self) -> list[{{Entity}}]:
        return list(self._repo.list())
"""

# HTTP Controller Template - REST API endpoints with OpenAPI integration
CONTROLLER_TMPL = """
from __future__ import annotations
from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import Schema, fields
from {{pkg}}.shared.di import Container

# Create blueprint with OpenAPI integration
bp = Blueprint(
    "{{bc|title}} - {{name|title}}", 
    __name__, 
    url_prefix="/{{name}}", 
    description="{{name|title}} management endpoints"
)
_container: Container | None = None

def init_controller(container: Container) -> None:
    global _container
    _container = container

# Schemas for OpenAPI documentation
class {{name|title}}Schema(Schema):
    id = fields.Integer(dump_only=True)
    name = fields.String(required=True)

class {{name|title}}CreateSchema(Schema):
    name = fields.String(required=True)

class {{name|title}}ListSchema(Schema):
    items = fields.List(fields.Nested({{name|title}}Schema))

@bp.route("")
class {{name|title}}Collection(MethodView):
    @bp.response(200, {{name|title}}ListSchema)
    @bp.doc(summary="List all {{name}}s", description="Retrieve a list of all {{name}}s")
    def get(self):
        \"\"\"List all {{name}}s\"\"\"
        if _container is None:
            raise RuntimeError("Controller not initialized")
        svc = _container.get("{{bc}}.{{name}}.service")
        items = svc.list()
        return {"items": [{"id": i.id, "name": i.name} for i in items]}

    @bp.arguments({{name|title}}CreateSchema)
    @bp.response(201, {{name|title}}Schema)
    @bp.doc(summary="Create a new {{name}}", description="Create a new {{name}} with the provided data")
    def post(self, new_item):
        \"\"\"Create a new {{name}}\"\"\"
        if _container is None:
            raise RuntimeError("Controller not initialized")
        svc = _container.get("{{bc}}.{{name}}.service")
        item = svc.create(new_item["name"])
        return {"id": item.id, "name": item.name}
"""

# HTTP Controller Template - Traditional Flask blueprint without OpenAPI
CONTROLLER_BASIC_TMPL = """
from __future__ import annotations
from flask import Blueprint, request, jsonify
from {{pkg}}.shared.di import Container

# Create basic Flask blueprint
bp = Blueprint(
    "{{bc}}_{{name}}", 
    __name__, 
    url_prefix="/{{name}}"
)
_container: Container | None = None

def init_controller(container: Container) -> None:
    global _container
    _container = container

@bp.route("", methods=["GET"])
def list_{{name}}s():
    \"\"\"List all {{name}}s\"\"\"
    if _container is None:
        raise RuntimeError("Controller not initialized")
    svc = _container.get("{{bc}}.{{name}}.service")
    items = svc.list()
    return jsonify({"items": [{"id": i.id, "name": i.name} for i in items]})

@bp.route("", methods=["POST"])
def create_{{name}}():
    \"\"\"Create a new {{name}}\"\"\"
    if _container is None:
        raise RuntimeError("Controller not initialized")
    data = request.get_json()
    if not data or "name" not in data:
        return jsonify({"error": "Missing required field: name"}), 400
    
    svc = _container.get("{{bc}}.{{name}}.service")
    item = svc.create(data["name"])
    return jsonify({"id": item.id, "name": item.name}), 201
"""

# API Registration Template - Wires controllers into the main API
API_REG_PATCH = """
from flask import Blueprint
from .{{bc}}.{{name}}_controller import bp as {{name}}_bp, init_controller as init_{{name}}_controller

def register_{{name}}(api: Blueprint, container) -> None:
    init_{{name}}_controller(container)
    api.register_blueprint({{name}}_bp)
"""

# --- Test Templates ---
# These templates define basic tests for each layer

# Domain Layer Test Template - Validates entity behavior
TEST_DOMAIN_TMPL = """
from {pkg}.domain.{bc}.entities import {Entity}

def test_entity_can_be_constructed():
    e = {Entity}(id=None, name="X")
    assert e.name == "X"
"""

# Application Layer Test Template - Validates service logic
TEST_APP_TMPL = """
from {pkg}.app.{bc}.services import {Entity}Service
from {pkg}.domain.{bc}.entities import {Entity}

class FakeRepo:
    def __init__(self):
        self.items = []
    def add(self, e: {Entity}):
        e.id = 1; self.items.append(e); return e
    def list(self):
        return list(self.items)

def test_service_create_and_list():
    svc = {Entity}Service(repo=FakeRepo())
    created = svc.create("A")
    assert created.id == 1
    assert [x.name for x in svc.list()] == ["A"]
"""

# Infrastructure Layer Test Template - Validates repository implementation
TEST_INFRA_TMPL = """
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from {pkg}.infra.db.base import Base
from {pkg}.infra.{bc}.repo_sqlalchemy import SqlAlchemy{Entity}Repository, {Entity}Row


def test_sqlalchemy_repo_roundtrip(tmp_path):
    url = f"sqlite:///{tmp_path}/test.db"
    engine = create_engine(url, future=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    repo = SqlAlchemy{Entity}Repository(Session)
    one = repo.add(type("E", (), {"id": None, "name": "X"}))
    assert one.id is not None
    assert [x.name for x in repo.list()] == ["X"]
"""

# Interface Layer Test Template - Validates HTTP endpoints
TEST_HTTP_TMPL = """
from importlib import import_module

def test_http_smoke():
    pkg = import_module("{pkg}")
    app = pkg.create_app()
    c = app.test_client()
    r = c.post("/api/{name}", json={'name': 'X'})
    assert r.status_code == 201
    r = c.get("/api/{name}")
    assert r.status_code == 200
"""

# --- Command Implementations ---


@generate.command("bc")
def bounded_context(name: str = typer.Argument(..., help="Bounded context name (e.g. catalog)")):
    """
    Generate a bounded context structure.

    Creates the directory structure for a bounded context following
    Clean Architecture principles:
    - domain/<bc>/ - Domain layer (entities, repositories)
    - app/<bc>/ - Application layer (services)
    - infra/<bc>/ - Infrastructure layer (implementations)
    - interfaces/http/<bc>/ - Interface layer (controllers)

    Args:
        name: Bounded context name (e.g., 'catalog', 'users')

    Example:
        forge generate bc catalog
    """
    pkg = _detect_package()
    bc = name.replace("-", "_")  # Normalize bounded context name

    pkg_root = Path("src") / pkg

    # Ensure all necessary directories and __init__.py files exist
    ensure_init_files(
        pkg_root,
        [
            f"domain/{bc}",
            f"app/{bc}",
            f"infra/{bc}",
            f"interfaces/http/{bc}",
        ],
    )

    rprint(f"[green]Bounded context created:[/green] {bc} (domain/app/infra/interfaces)")


@generate.command("entity")
def entity(
    bc: str = typer.Argument(..., help=BC_HELP), name: str = typer.Argument(..., help=ENTITY_HELP)
):
    """
    Generate a domain entity with repository interface.

    Creates:
    - Domain entity as a dataclass
    - Repository interface for data access

    Args:
        bc: Bounded context name (e.g., 'catalog', 'users')
        name: Entity name in PascalCase (e.g., 'Product', 'User')

    Example:
        forge generate entity catalog Product
    """
    pkg = _detect_package()
    bc = bc.replace("-", "_")  # Normalize bounded context name
    entity_class = name[0].upper() + name[1:]  # PascalCase for class names

    env = Environment(
        loader=DictLoader(
            {
                "entity": ENTITY_TMPL,
                "repo_iface": REPO_IFACE_TMPL,
            }
        )
    )

    pkg_root = Path("src") / pkg

    # Ensure domain directory exists
    ensure_init_files(pkg_root, [f"domain/{bc}"])

    # Generate domain layer files
    _generate_domain_files(pkg, bc, entity_class, env)

    rprint(
        f"[green]Entity generated:[/green] {bc}.{entity_class} (domain entity + repository interface)"
    )


@generate.command("repo")
def repository(
    bc: str = typer.Argument(..., help=BC_HELP),
    entity: str = typer.Argument(..., help=ENTITY_HELP),
    impl: str = typer.Option("sqlalchemy", "--impl", help="Repository implementation type"),
):
    """
    Generate a repository implementation.

    Creates repository implementation for the specified entity.
    Currently supports SQLAlchemy implementation.

    Args:
        bc: Bounded context name (e.g., 'catalog', 'users')
        entity: Entity name in PascalCase (e.g., 'Product', 'User')
        impl: Implementation type (currently only 'sqlalchemy')

    Example:
        forge generate repo catalog Product --impl=sqlalchemy
    """
    pkg = _detect_package()
    bc = bc.replace("-", "_")  # Normalize bounded context name
    entity_class = entity[0].upper() + entity[1:]  # PascalCase for class names
    entity_name = entity[0].lower() + entity[1:]  # camelCase for instances
    table_name = entity_name + "s"  # Pluralized table name

    if impl != "sqlalchemy":
        rprint(
            f"[red]Error:[/red] Implementation '{impl}' not supported. Currently only 'sqlalchemy' is available."
        )
        raise typer.Exit(1)

    env = Environment(
        loader=DictLoader(
            {
                "repo_sqla": REPO_SQLA_TMPL,
            }
        )
    )

    pkg_root = Path("src") / pkg

    # Ensure infrastructure directory exists
    ensure_init_files(pkg_root, [f"infra/{bc}"])

    # Generate infrastructure layer files
    _generate_infrastructure_files(pkg, bc, entity_class, table_name, env)

    rprint(f"[green]Repository generated:[/green] {bc}.{entity_class} ({impl} implementation)")


@generate.command("service")
def service(
    bc: str = typer.Argument(..., help=BC_HELP), name: str = typer.Argument(..., help=SERVICE_HELP)
):
    """
    Generate a service class for business logic.

    Creates an application service that encapsulates business logic
    and coordinates between domain and infrastructure layers.

    Args:
        bc: Bounded context name (e.g., 'catalog', 'users')
        name: Service name ending with 'Service' (e.g., 'ProductService')

    Example:
        forge generate service catalog ProductService
    """
    pkg = _detect_package()
    bc = bc.replace("-", "_")  # Normalize bounded context name

    # Extract entity name from service name (remove 'Service' suffix)
    if name.endswith("Service"):
        entity_class = name[:-7]  # Remove 'Service' suffix
    else:
        entity_class = name
        name = name + "Service"  # Add 'Service' suffix if not present

    env = Environment(
        loader=DictLoader(
            {
                "service": SERVICE_TMPL,
            }
        )
    )

    pkg_root = Path("src") / pkg

    # Ensure application directory exists
    ensure_init_files(pkg_root, [f"app/{bc}"])

    # Generate application layer files
    _generate_application_files(pkg, bc, entity_class, env)

    rprint(f"[green]Service generated:[/green] {bc}.{name} (application service)")


@generate.command("controller")
def controller(
    bc: str = typer.Argument(..., help=BC_HELP),
    name: str = typer.Argument(..., help=CONTROLLER_HELP),
):
    """
    Generate a Flask blueprint controller.

    Creates an HTTP controller with REST endpoints following
    Flask blueprint patterns. Automatically detects if OpenAPI
    is enabled and generates appropriate controller type.

    Args:
        bc: Bounded context name (e.g., 'catalog', 'users')
        name: Controller name in lowercase (e.g., 'product', 'user')

    Example:
        forge generate controller catalog product
    """
    pkg = _detect_package()
    bc = bc.replace("-", "_")  # Normalize bounded context name
    entity_name = name.lower()  # Ensure lowercase for URL patterns

    # Detect if OpenAPI is enabled in the project
    has_openapi = _has_openapi_enabled(pkg)

    # Choose appropriate template based on OpenAPI availability
    template_name = "controller" if has_openapi else "controller_basic"
    templates = {
        "controller": CONTROLLER_TMPL,
        "controller_basic": CONTROLLER_BASIC_TMPL,
    }

    env = Environment(loader=DictLoader(templates))

    pkg_root = Path("src") / pkg

    # Ensure interface directory exists
    ensure_init_files(pkg_root, [f"interfaces/http/{bc}"])

    # Generate interface layer files with appropriate template
    _generate_interface_files(pkg, bc, entity_name, env, template_name)

    # Wire the controller into the API surface
    _wire_api_integration(pkg, bc, entity_name)

    controller_type = "OpenAPI-enabled" if has_openapi else "basic Flask"
    rprint(f"[green]Controller generated:[/green] {bc}.{entity_name} ({controller_type} blueprint)")


def _has_openapi_enabled(pkg: str) -> bool:
    """
    Check if OpenAPI is enabled in the project by looking for:
    1. OpenAPI extension file
    2. flask-smorest dependency in pyproject.toml
    3. OpenAPI imports in api.py

    Args:
        pkg: Package name

    Returns:
        True if OpenAPI is enabled, False otherwise
    """
    # Check for OpenAPI extension file
    openapi_ext_file = Path(f"src/{pkg}/interfaces/http/ext/openapi.py")
    if openapi_ext_file.exists():
        return True

    # Check for flask-smorest in pyproject.toml
    pyproject_file = Path("pyproject.toml")
    if pyproject_file.exists():
        content = pyproject_file.read_text(encoding="utf-8")
        if "flask-smorest" in content:
            return True

    # Check for OpenAPI imports in api.py
    api_file = Path(f"src/{pkg}/interfaces/http/api.py")
    if api_file.exists():
        content = api_file.read_text(encoding="utf-8")
        if "from .ext.openapi import" in content or "configure_openapi" in content:
            return True

    return False


@generate.command("resource")
def resource(
    bc: str = typer.Argument(..., help=BC_HELP), entity: str = typer.Argument(..., help=ENTITY_HELP)
):
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
    entity_name = entity[0].lower() + entity[1:]  # camelCase for instances
    table_name = entity_name + "s"  # Pluralized table name

    # Generate all code files
    _generate_code_files(pkg, bc, entity_class, entity_name, table_name)

    # Wire into API surface
    _wire_api_integration(pkg, bc, entity_name)

    # Setup dependency injection
    _setup_dependency_injection(pkg, bc, entity_class, entity_name)

    rprint(
        f"[green]Resource generated:[/green] {bc}.{entity_class} (domain/app/infra/interfaces + wiring)"
    )


def _generate_code_files(
    pkg: str, bc: str, entity_class: str, entity_name: str, table_name: str
) -> None:
    """Generate all the code files for the resource."""
    env = Environment(
        loader=DictLoader(
            {
                "entity": ENTITY_TMPL,
                "repo_iface": REPO_IFACE_TMPL,
                "repo_sqla": REPO_SQLA_TMPL,
                "service": SERVICE_TMPL,
                "controller": CONTROLLER_TMPL,
                "api_reg": API_REG_PATCH,
            }
        )
    )

    pkg_root = Path("src") / pkg
    entity_name = entity_class.lower()

    # Ensure all necessary directories and __init__.py files exist
    ensure_init_files(
        pkg_root,
        [
            f"domain/{bc}",
            f"domain/{bc}/{entity_name}",
            f"app/{bc}",
            f"app/{bc}/{entity_name}",
            f"infra/{bc}",
            f"infra/{bc}/{entity_name}",
            f"interfaces/http/{bc}",
            f"interfaces/http/{bc}/{entity_name}",
        ],
    )

    # Generate domain layer files
    _generate_domain_files(pkg, bc, entity_class, env)

    # Generate infrastructure layer files
    _generate_infrastructure_files(pkg, bc, entity_class, table_name, env)

    # Generate application layer files
    _generate_application_files(pkg, bc, entity_class, env)

    # Generate interface layer files
    _generate_interface_files(pkg, bc, entity_name, env)

    # Generate test files for all layers
    _generate_test_files(pkg, bc, entity_class, entity_name)


def _append_to_entities_file(entities_file: Path, entity_class: str, env: Environment) -> None:
    """Append entity to entities.py file or create it if it doesn't exist."""
    if not entities_file.exists():
        # Create new file with header
        content = f"""from __future__ import annotations
from dataclasses import dataclass

{env.get_template("entity").render(Entity=entity_class).strip()}
"""
    else:
        # Read existing content and append new entity
        existing_content = entities_file.read_text(encoding="utf-8")
        if f"class {entity_class}:" not in existing_content:
            entity_code = env.get_template("entity").render(Entity=entity_class).strip()
            # Remove the imports and dataclass import from the template
            entity_lines = entity_code.split("\n")
            entity_only = []
            skip_until_dataclass = True
            for line in entity_lines:
                if line.strip().startswith("@dataclass"):
                    skip_until_dataclass = False
                if not skip_until_dataclass:
                    entity_only.append(line)

            content = existing_content.rstrip() + "\n\n" + "\n".join(entity_only) + "\n"
        else:
            content = existing_content

    entities_file.write_text(content, encoding="utf-8")


def _append_to_repositories_file(repos_file: Path, entity_class: str, env: Environment) -> None:
    """Append repository interface to repositories.py file or create it if it doesn't exist."""
    if not repos_file.exists():
        # Create new file
        content = env.get_template("repo_iface").render(Entity=entity_class)
    else:
        # Read existing content and append new repository interface
        existing_content = repos_file.read_text(encoding="utf-8")
        if f"class I{entity_class}Repository(" not in existing_content:
            repo_code = env.get_template("repo_iface").render(Entity=entity_class)
            # Extract just the class definition from the template
            repo_lines = repo_code.split("\n")
            class_start = None
            for i, line in enumerate(repo_lines):
                if line.startswith(f"class I{entity_class}Repository("):
                    class_start = i
                    break

            if class_start is not None:
                class_lines = repo_lines[class_start:]
                # Add import for the entity if not present
                if f"from .entities import {entity_class}" not in existing_content:
                    # Find the last import line and add after it
                    lines = existing_content.split("\n")
                    last_import_idx = 0
                    for i, line in enumerate(lines):
                        if line.startswith("from .entities import"):
                            last_import_idx = i

                    # Update the import line to include the new entity
                    import_line = lines[last_import_idx]
                    if import_line.endswith(")"):
                        # Multi-line import
                        lines[last_import_idx] = import_line[:-1] + f", {entity_class})"
                    else:
                        # Single line import
                        lines[last_import_idx] = import_line + f", {entity_class}"

                    existing_content = "\n".join(lines)

                content = existing_content.rstrip() + "\n\n" + "\n".join(class_lines) + "\n"
            else:
                content = existing_content
        else:
            content = existing_content

    repos_file.write_text(content, encoding="utf-8")


def _append_to_sqlalchemy_repo_file(
    repo_file: Path, entity_class: str, table_name: str, bc: str, env: Environment
) -> None:
    """Append SQLAlchemy repository to repo_sqlalchemy.py file or create it if it doesn't exist."""
    if not repo_file.exists():
        # Create new file
        content = env.get_template("repo_sqla").render(Entity=entity_class, bc=bc, table=table_name)
    else:
        # Read existing content and append new repository implementation
        existing_content = repo_file.read_text(encoding="utf-8")
        if f"class SqlAlchemy{entity_class}Repository(" not in existing_content:
            repo_code = env.get_template("repo_sqla").render(
                Entity=entity_class, bc=bc, table=table_name
            )

            # Extract the class definitions from the template (both Row and Repository classes)
            repo_lines = repo_code.split("\n")

            # Find the start of the Row class and Repository class
            row_class_start = None
            repo_class_start = None

            for i, line in enumerate(repo_lines):
                if line.startswith(f"class {entity_class}Row("):
                    row_class_start = i
                elif line.startswith(f"class SqlAlchemy{entity_class}Repository("):
                    repo_class_start = i

            if row_class_start is not None and repo_class_start is not None:
                # Get the row class and repository class code
                new_classes = repo_lines[row_class_start:]

                # Add import for the entity if not present
                if f"from ...domain.{bc}.entities import {entity_class}" not in existing_content:
                    # Find the last domain import and add after it
                    lines = existing_content.split("\n")
                    last_domain_import_idx = 0
                    for i, line in enumerate(lines):
                        if "from ...domain." in line and ".entities import" in line:
                            last_domain_import_idx = i

                    # Update the import line to include the new entity
                    import_line = lines[last_domain_import_idx]
                    if import_line.endswith(")"):
                        # Multi-line import - shouldn't happen with current template
                        lines[last_domain_import_idx] = import_line[:-1] + f", {entity_class})"
                    else:
                        # Single line import
                        entity_name = import_line.split(" import ")[1]
                        lines[last_domain_import_idx] = import_line.replace(
                            entity_name, f"{entity_name}, {entity_class}"
                        )

                    existing_content = "\n".join(lines)

                # Add repository interface import if not present
                if (
                    f"from ...domain.{bc}.repositories import I{entity_class}Repository"
                    not in existing_content
                ):
                    lines = existing_content.split("\n")
                    last_repo_import_idx = 0
                    for i, line in enumerate(lines):
                        if "from ...domain." in line and ".repositories import" in line:
                            last_repo_import_idx = i

                    # Update the repository import line
                    import_line = lines[last_repo_import_idx]
                    if import_line.endswith(")"):
                        lines[last_repo_import_idx] = (
                            import_line[:-1] + f", I{entity_class}Repository)"
                        )
                    else:
                        repo_name = import_line.split(" import ")[1]
                        lines[last_repo_import_idx] = import_line.replace(
                            repo_name, f"{repo_name}, I{entity_class}Repository"
                        )

                    existing_content = "\n".join(lines)

                content = existing_content.rstrip() + "\n\n\n" + "\n".join(new_classes) + "\n"
            else:
                content = existing_content
        else:
            content = existing_content

    repo_file.write_text(content, encoding="utf-8")


def _append_to_services_file(
    services_file: Path, entity_class: str, bc: str, env: Environment
) -> None:
    """Append service to services.py file or create it if it doesn't exist."""
    if not services_file.exists():
        # Create new file
        content = env.get_template("service").render(Entity=entity_class, bc=bc)
    else:
        # Read existing content and append new service
        existing_content = services_file.read_text(encoding="utf-8")
        if f"class {entity_class}Service:" not in existing_content:
            service_code = env.get_template("service").render(Entity=entity_class, bc=bc)

            # Extract the class definition from the template
            service_lines = service_code.split("\n")
            class_start = None
            for i, line in enumerate(service_lines):
                if line.startswith(f"class {entity_class}Service:"):
                    class_start = i
                    break

            if class_start is not None:
                class_lines = service_lines[class_start:]

                # Add imports if not present
                if (
                    f"from ...domain.{bc}.repositories import I{entity_class}Repository"
                    not in existing_content
                ):
                    lines = existing_content.split("\n")
                    last_repo_import_idx = 0
                    for i, line in enumerate(lines):
                        if "from ...domain." in line and ".repositories import" in line:
                            last_repo_import_idx = i

                    # Update the repository import line
                    import_line = lines[last_repo_import_idx]
                    repo_name = import_line.split(" import ")[1]
                    lines[last_repo_import_idx] = import_line.replace(
                        repo_name, f"{repo_name}, I{entity_class}Repository"
                    )
                    existing_content = "\n".join(lines)

                if f"from ...domain.{bc}.entities import {entity_class}" not in existing_content:
                    lines = existing_content.split("\n")
                    last_entity_import_idx = 0
                    for i, line in enumerate(lines):
                        if "from ...domain." in line and ".entities import" in line:
                            last_entity_import_idx = i

                    # Update the entity import line
                    import_line = lines[last_entity_import_idx]
                    entity_name = import_line.split(" import ")[1]
                    lines[last_entity_import_idx] = import_line.replace(
                        entity_name, f"{entity_name}, {entity_class}"
                    )
                    existing_content = "\n".join(lines)

                content = existing_content.rstrip() + "\n\n" + "\n".join(class_lines) + "\n"
            else:
                content = existing_content
        else:
            content = existing_content

    services_file.write_text(content, encoding="utf-8")


def _generate_domain_files(pkg: str, bc: str, entity_class: str, env: Environment) -> None:
    """Generate domain layer files (entities and repository interfaces)."""
    entity_name = entity_class.lower()

    # Create entity-specific subdirectory
    entity_domain_path = Path(f"src/{pkg}/domain/{bc}/{entity_name}")
    entity_domain_path.mkdir(parents=True, exist_ok=True)

    # Generate entity in entity.py
    entity_file = entity_domain_path / "entity.py"
    entity_file.write_text(env.get_template("entity").render(Entity=entity_class), encoding="utf-8")

    # Generate repository interface in repository.py
    repo_file = entity_domain_path / "repository.py"
    repo_file.write_text(
        env.get_template("repo_iface").render(Entity=entity_class), encoding="utf-8"
    )

    # Create __init__.py for the entity subdirectory
    init_file = entity_domain_path / "__init__.py"
    init_file.write_text("", encoding="utf-8")


def _generate_infrastructure_files(
    pkg: str, bc: str, entity_class: str, table_name: str, env: Environment
) -> None:
    """Generate infrastructure layer files (repository implementations)."""
    entity_name = entity_class.lower()

    # Create entity-specific subdirectory
    entity_infra_path = Path(f"src/{pkg}/infra/{bc}/{entity_name}")
    entity_infra_path.mkdir(parents=True, exist_ok=True)

    # Generate SQLAlchemy repository implementation in repo_sqlalchemy.py
    repo_file = entity_infra_path / "repo_sqlalchemy.py"
    repo_file.write_text(
        env.get_template("repo_sqla").render(
            Entity=entity_class, bc=bc, table=table_name, entity_name=entity_name
        ),
        encoding="utf-8",
    )

    # Create __init__.py for the entity subdirectory
    init_file = entity_infra_path / "__init__.py"
    init_file.write_text("", encoding="utf-8")


def _generate_application_files(pkg: str, bc: str, entity_class: str, env: Environment) -> None:
    """Generate application layer files (services)."""
    entity_name = entity_class.lower()

    # Create entity-specific subdirectory
    entity_app_path = Path(f"src/{pkg}/app/{bc}/{entity_name}")
    entity_app_path.mkdir(parents=True, exist_ok=True)

    # Generate service in service.py
    services_file = entity_app_path / "service.py"
    services_file.write_text(
        env.get_template("service").render(Entity=entity_class, bc=bc, entity_name=entity_name),
        encoding="utf-8",
    )

    # Create __init__.py for the entity subdirectory
    init_file = entity_app_path / "__init__.py"
    init_file.write_text("", encoding="utf-8")


def _generate_interface_files(
    pkg: str, bc: str, entity_name: str, env: Environment, template_name: str = "controller"
) -> None:
    """Generate interface layer files (HTTP controllers)."""
    # Create entity-specific subdirectory
    entity_interface_path = Path(f"src/{pkg}/interfaces/http/{bc}/{entity_name}")
    entity_interface_path.mkdir(parents=True, exist_ok=True)

    # Generate HTTP controller in controller.py using specified template
    controller_file = entity_interface_path / "controller.py"
    controller_file.write_text(
        env.get_template(template_name).render(pkg=pkg, bc=bc, name=entity_name), encoding="utf-8"
    )

    # Create __init__.py for the entity subdirectory
    init_file = entity_interface_path / "__init__.py"
    init_content = """from .controller import bp, init_controller

__all__ = ["bp", "init_controller"]
"""
    init_file.write_text(init_content, encoding="utf-8")


def _wire_api_integration(pkg: str, bc: str, entity_name: str) -> None:
    """Wire the new resource into the API surface with robust, idempotent operations."""
    api_file = Path(f"src/{pkg}/interfaces/http/api.py")
    api_content = api_file.read_text(encoding="utf-8")

    # Define the lines to be inserted with subdirectory structure
    import_line = f"from .{bc}.{entity_name}.controller import bp as {bc}_{entity_name}_bp, init_controller as init_{bc}_{entity_name}_controller"
    register_line = f"    api.register_blueprint({bc}_{entity_name}_bp)"
    init_line = f"    init_{bc}_{entity_name}_controller(container)"

    # Check if OpenAPI is available
    has_openapi = "from .ext.openapi import configure_openapi" in api_content

    if has_openapi:
        # For OpenAPI integration, ensure we have the necessary imports and wiring function
        openapi_import = "from .ext.openapi import get_api_instance"

        # Add the _wire_api_integration function if it doesn't exist
        wire_function = f"""
def _wire_api_integration():
    \"\"\"Wire OpenAPI integration after it's been configured.\"\"\"
    openapi_api = get_api_instance()
    if openapi_api:
        # Register OpenAPI-capable controllers with the API instance
        if hasattr({bc}_{entity_name}_bp, 'doc'):
            try:
                openapi_api.register_blueprint({bc}_{entity_name}_bp)
            except Exception:
                pass  # Already registered or error"""

        # Insert OpenAPI import if not present
        if openapi_import not in api_content:
            api_content = _insert_line_once(
                api_content,
                openapi_import,
                "# [forge:auto-imports]",
                r"(?ms)(^from\s+[^\n]+$|^import\s+[^\n]+$)(?:\n(?:from\s+[^\n]+$|import\s+[^\n]+$))*",
            )

        # Add the wire function if it doesn't exist
        if "_wire_api_integration" not in api_content:
            # Insert before register_http function
            pattern = r"(def register_http)"
            replacement = wire_function + "\n\n\\1"
            api_content = re.sub(pattern, replacement, api_content)

        # Update the register_http function to call _wire_api_integration
        if "_wire_api_integration()" not in api_content:
            # Insert the call after configure_openapi
            pattern = r"(configure_openapi\(app\))"
            replacement = "\\1\n    \n    # Wire OpenAPI integration after configuring it\n    _wire_api_integration()"
            api_content = re.sub(pattern, replacement, api_content)

    # Insert import, register, and init lines
    api_content = _insert_line_once(
        api_content,
        import_line,
        "# [forge:auto-imports]",
        r"(?ms)(^from\s+[^\n]+$|^import\s+[^\n]+$)(?:\n(?:from\s+[^\n]+$|import\s+[^\n]+$))*",
    )

    api_content = _insert_line_once(
        api_content,
        register_line,
        "    # [forge:auto-register]",
        r"(?ms)def\s+build_api_blueprint\([^\)]*\):\s*\n(.*?)\n\s*return\s+api",
    )

    api_content = _insert_line_once(
        api_content,
        init_line,
        "    # [forge:auto-init]",
        r"(?ms)def\s+register_http\([^\)]*\):\s*\n(.*?)\n\s*app\.register_blueprint\(api_bp\)",
    )

    api_file.write_text(api_content, encoding="utf-8")


def _setup_dependency_injection(pkg: str, bc: str, entity_class: str, entity_name: str) -> None:
    """Setup dependency injection wiring for the new resource."""
    wiring_file = Path(f"src/{pkg}/shared/di_wiring.py")
    wiring_content = wiring_file.read_text(encoding="utf-8")

    # Add imports for repository and service from subdirectories
    import_repo = f"from {pkg}.infra.{bc}.{entity_name}.repo_sqlalchemy import SqlAlchemy{entity_class}Repository\n"
    import_service = f"from {pkg}.app.{bc}.{entity_name}.service import {entity_class}Service\n"

    wiring_content = _insert_after_line(
        wiring_content,
        r"from\s+\.\.\s*infra\.db\.base\s+import\s+init_engine\s*\n",
        import_repo + import_service,
    )

    # Add registration function if it doesn't exist
    func_signature = f"def register_{entity_name}(container"
    if func_signature not in wiring_content:
        registration_func = (
            f"\n\n\ndef register_{entity_name}(container: Container) -> None:\n"
            f'    """Register {entity_class} dependencies in the DI container."""\n'
            f"    container.register(\n"
            f'        "{bc}.{entity_name}.repo",\n'
            f'        lambda: SqlAlchemy{entity_class}Repository(container.get("db.session_factory")),\n'
            f"    )\n"
            f"    container.register(\n"
            f'        "{bc}.{entity_name}.service",\n'
            f'        container.factory({entity_class}Service, repo="{bc}.{entity_name}.repo"),\n'
            f"    )\n"
        )
        wiring_content += registration_func

    # Add call to registration function in register_features
    call_line = f"    register_{entity_name}(container)"
    if "def register_features(" in wiring_content and call_line not in wiring_content:
        # Find the register_features function and add the call
        lines = wiring_content.split("\n")
        new_lines = []
        in_register_features = False
        added_call = False

        for i, line in enumerate(lines):
            new_lines.append(line)

            # Detect start of register_features function
            if "def register_features(container: Container) -> None:" in line:
                in_register_features = True
                continue

            # If we're in register_features and find the end of function
            if (
                in_register_features
                and line.strip() == ""
                and i + 1 < len(lines)
                and lines[i + 1].strip()
                and not lines[i + 1].startswith("    ")
            ):
                # End of function, add call before this line if not added yet
                if not added_call:
                    # Insert before the empty line
                    new_lines.insert(-1, call_line)
                    added_call = True
                in_register_features = False
                continue

            # If we're in register_features and find a pass statement, replace it
            if in_register_features and line.strip() == "pass":
                new_lines[-1] = call_line  # Replace the pass line
                added_call = True
                continue

            # If we're in register_features and find an existing register call, add after all calls
            if (
                in_register_features
                and "register_" in line
                and "(container)" in line
                and not added_call
            ):
                # Look ahead to see if there are more register calls
                has_more_calls = False
                for j in range(i + 1, len(lines)):
                    if lines[j].strip() == "":
                        break
                    if "register_" in lines[j] and "(container)" in lines[j]:
                        has_more_calls = True
                        break

                # If no more calls after this one, add our call
                if not has_more_calls:
                    new_lines.append(call_line)
                    added_call = True

        wiring_content = "\n".join(new_lines)

    wiring_file.write_text(wiring_content, encoding="utf-8")


def _generate_test_files(pkg: str, bc: str, entity_class: str, entity_name: str) -> None:
    """Generate test files for each layer of the resource."""
    env = Environment(
        loader=DictLoader(
            {
                "test_domain": TEST_DOMAIN_TMPL,
                "test_app": TEST_APP_TMPL,
                "test_infra": TEST_INFRA_TMPL,
                "test_http": TEST_HTTP_TMPL,
            }
        )
    )

    pkg_root = Path("src") / pkg

    # Ensure test directories and __init__.py files exist
    ensure_init_files(
        pkg_root,
        [
            f"tests/domain/{bc}",
            f"tests/app/{bc}",
            f"tests/infra/{bc}",
            "tests/interfaces/http",
        ],
    )

    # Generate domain layer test
    (pkg_root / f"tests/domain/{bc}/test_entities.py").write_text(
        env.get_template("test_domain").render(pkg=pkg, bc=bc, Entity=entity_class),
        encoding="utf-8",
    )

    # Generate application layer test
    (pkg_root / f"tests/app/{bc}/test_services.py").write_text(
        env.get_template("test_app").render(pkg=pkg, bc=bc, Entity=entity_class),
        encoding="utf-8",
    )

    # Generate infrastructure layer test
    (pkg_root / f"tests/infra/{bc}/test_repo_sqlalchemy.py").write_text(
        env.get_template("test_infra").render(pkg=pkg, bc=bc, Entity=entity_class),
        encoding="utf-8",
    )

    # Generate interface layer test
    (pkg_root / f"tests/interfaces/http/test_{entity_name}.py").write_text(
        env.get_template("test_http").render(pkg=pkg, name=entity_name),
        encoding="utf-8",
    )


def _insert_line_once(
    text: str, needle: str, anchor: str, fallback_pattern: str | None = None
) -> str:
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
