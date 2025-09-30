from __future__ import annotations
import re
from pathlib import Path
import typer
from rich import print as rprint

plugin = typer.Typer(help="Optional features")

# Constants
OPENAPI_IMPORT = "from .ext.openapi import configure_openapi"
API_INIT_CALL = "configure_openapi(app)"
FORGE_AUTO_IMPORTS = "# [forge:auto-imports]"
FORGE_AUTO_INIT = "# [forge:auto-init]"


def _detect_pkg() -> str:
    for p in Path("src").glob("*/main.py"):
        return p.parent.name
    raise SystemExit("pkg not found")


@plugin.command("openapi")
def openapi():
    """Install OpenAPI support with proper validation and error handling."""
    root = Path(".")
    if not (root / "pyproject.toml").exists():
        raise SystemExit("Run from project root")

    pkg = _detect_pkg()

    # Validate that api.py exists
    api_file = root / f"src/{pkg}/interfaces/http/api.py"
    if not api_file.exists():
        raise SystemExit(f"API file not found: {api_file}")

    # Create ext/openapi.py
    ext_dir = root / f"src/{pkg}/interfaces/http/ext"
    ext_dir.mkdir(parents=True, exist_ok=True)
    openapi_file = ext_dir / "openapi.py"

    if openapi_file.exists():
        rprint("[yellow]OpenAPI extension already exists, skipping creation")
    else:
        openapi_file.write_text(_OPENAPI_EXT, encoding="utf-8")
        rprint("[green]Created OpenAPI extension file")

    # Update dependencies
    if _update_pyproject_dependencies(root / "pyproject.toml"):
        rprint("[green]Updated pyproject.toml dependencies")
    else:
        rprint("[yellow]Dependencies already up to date")

    # Update API file
    rprint(f"[blue]Updating API file: {api_file}")
    if _update_api_file(api_file):
        rprint("[green]Updated API file with OpenAPI integration")
    else:
        rprint("[yellow]API file already configured")

    # Register existing controllers with OpenAPI
    _register_existing_controllers(root, pkg)

    rprint("[green]✓ OpenAPI installed.")
    rprint("[blue]Available routes:")
    rprint("[blue]  • Swagger UI: /docs/swagger-ui")
    rprint("[blue]  • ReDoc: /docs/redoc")
    rprint("[blue]  • OpenAPI spec: /docs/openapi.json")


def _update_pyproject_dependencies(pyproject_path: Path) -> bool:
    """Update pyproject.toml dependencies. Returns True if changes were made."""
    content = pyproject_path.read_text(encoding="utf-8")
    required_deps = ["flask-smorest", "marshmallow"]

    # Check if deps exist and track missing ones
    missing_deps: list[str] = []
    for dep in required_deps:
        # Look for the dependency with proper word boundaries
        if not re.search(rf'["\']({dep})["><=~!\s]', content):
            missing_deps.append(dep)

    if not missing_deps:
        return False

    # Add missing dependencies using simple string replacement
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if "dependencies = [" in line:
            # Handle single-line dependencies array
            if line.strip().endswith("]"):
                closing_bracket = line.rfind("]")
                deps_to_insert = "".join(f'"{dep}>=0",' for dep in missing_deps)
                lines[i] = line[:closing_bracket] + deps_to_insert + line[closing_bracket:]
            else:
                # Multi-line: add after the opening bracket
                for j, dep in enumerate(missing_deps):
                    lines.insert(i + 1 + j, f'    "{dep}>=0",')
            break

    pyproject_path.write_text("\n".join(lines), encoding="utf-8")
    return True


def _update_api_file(api_file: Path) -> bool:
    """Update api.py file to include OpenAPI. Returns True if changes were made."""
    content = api_file.read_text(encoding="utf-8")
    lines = content.split("\n")
    modified = False

    rprint("[blue]Checking if OpenAPI import exists...")
    if OPENAPI_IMPORT not in content:
        rprint("[blue]Adding OpenAPI import...")
        if _add_openapi_import(lines):
            modified = True
            rprint("[green]✓ Added OpenAPI import")
    else:
        rprint("[yellow]OpenAPI import already exists")

    rprint("[blue]Checking if configure_openapi(app) exists...")
    if API_INIT_CALL not in content:
        rprint("[blue]Adding configure_openapi(app) call...")
        if _add_api_init_call(lines):
            modified = True
            rprint("[green]✓ Added configure_openapi(app) call")
    else:
        rprint("[yellow]configure_openapi(app) already exists")

    if modified:
        api_file.write_text("\n".join(lines), encoding="utf-8")
        rprint("[green]✓ API file updated successfully")

    return modified


def _add_openapi_import(lines: list[str]) -> bool:
    """Add OpenAPI import to the lines. Returns True if modified."""
    # Check if already exists
    if any(OPENAPI_IMPORT in line for line in lines):
        return False

    # Try forge marker first
    for i, line in enumerate(lines):
        if FORGE_AUTO_IMPORTS in line:
            lines[i] = f"{OPENAPI_IMPORT}\n{FORGE_AUTO_IMPORTS}"
            return True

    # Find insertion point after imports or at beginning
    insert_idx = _find_import_insertion_point(lines)
    lines.insert(insert_idx, OPENAPI_IMPORT)
    return True


def _find_import_insertion_point(lines: list[str]) -> int:
    """Find the best place to insert an import statement."""
    # Find last import line
    last_import_idx = -1
    for i, line in enumerate(lines):
        if line.strip() and ("import " in line or "from " in line) and not line.startswith("#"):
            last_import_idx = i

    if last_import_idx >= 0:
        return last_import_idx + 1

    # If no imports found, add after initial comments
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith("#"):
            return i

    # Fallback: beginning of file
    return 0


def _add_api_init_call(lines: list[str]) -> bool:
    """Add configure_openapi(app) call. Returns True if modified."""
    # Check if already exists
    if any(API_INIT_CALL in line for line in lines):
        return False

    for i, line in enumerate(lines):
        if "def register_http(app" in line:
            # Look for forge marker
            for j in range(i + 1, len(lines)):
                if FORGE_AUTO_INIT in lines[j]:
                    # Insert before the existing content, after the marker
                    lines.insert(j + 1, f"    {API_INIT_CALL}")
                    return True
                elif lines[j].strip() and not lines[j].startswith("    #"):
                    # Insert before first non-comment line in function
                    lines.insert(j, f"    {API_INIT_CALL}")
                    return True
            break
    return False


_OPENAPI_EXT = """
from __future__ import annotations
from flask_smorest import Api
from flask import Flask

# Global API instance para que los blueprints puedan registrarse
openapi_api = None

def configure_openapi(app: Flask):
    \"\"\"Configure OpenAPI/Swagger documentation.\"\"\"
    global openapi_api
    
    # Configure app settings for flask-smorest
    app.config.update({
        'API_TITLE': 'Flask API',
        'API_VERSION': 'v1',
        'OPENAPI_VERSION': '3.0.3',
        'OPENAPI_URL_PREFIX': f'/docs',
        'OPENAPI_SWAGGER_UI_PATH': '/swagger-ui',
        'OPENAPI_SWAGGER_UI_URL': 'https://cdn.jsdelivr.net/npm/swagger-ui-dist/',
        'OPENAPI_REDOC_PATH': '/redoc',
        'OPENAPI_REDOC_URL': 'https://cdn.jsdelivr.net/npm/redoc@2.0.0/bundles/redoc.standalone.js',
        'OPENAPI_JSON_PATH': '/openapi.json'
    })
    
    # Create and initialize API instance
    openapi_api = Api()
    openapi_api.init_app(app)
    
    # Register any existing blueprints that were created with flask-smorest
    _register_existing_blueprints(app)
    
    return openapi_api

def get_api_instance():
    \"\"\"Get the global API instance for blueprint registration.\"\"\"
    return openapi_api

def _register_existing_blueprints(app: Flask):
    \"\"\"Register existing controller blueprints with the API instance.\"\"\"
    if not openapi_api:
        return
        
    # Look for blueprints that were created with flask-smorest
    for blueprint in app.blueprints.values():
        # Check if this is a flask-smorest blueprint by looking for specific attributes
        if hasattr(blueprint, '_spec') or 'swagger-ui' in str(blueprint.url_prefix or ''):
            continue  # Skip already registered or system blueprints
            
        # Register the blueprint with the API if it looks like a controller blueprint
        if blueprint.url_prefix and blueprint.url_prefix.startswith('/'):
            try:
                openapi_api.register_blueprint(blueprint)
            except Exception:
                # Blueprint might already be registered or incompatible
                pass
"""


def _register_existing_controllers(root: Path, pkg: str) -> None:
    """Register existing controller blueprints with OpenAPI."""
    api_file = root / f"src/{pkg}/interfaces/http/api.py"
    if not api_file.exists():
        return

    # Find all existing controller files
    controllers_path = root / f"src/{pkg}/interfaces/http"
    controller_files = list(controllers_path.glob("**/controller.py"))

    if not controller_files:
        rprint("[yellow]No existing controllers found")
        return

    rprint(f"[blue]Found {len(controller_files)} existing controllers")

    # Update api.py to register existing controllers with OpenAPI
    content = api_file.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Extract controller info
    controllers: list[tuple[str, str]] = []
    for controller_file in controller_files:
        rel_path = controller_file.relative_to(controllers_path)
        path_parts = rel_path.parts[:-1]  # Remove 'controller.py'

        if len(path_parts) >= 2:
            bc, entity = path_parts[0], path_parts[1]
            controllers.append((bc, entity))

    if not controllers:
        rprint("[yellow]No valid controllers found")
        return

    # Update register_http function to use OpenAPI
    modified = _update_register_http_for_openapi(lines, controllers)

    if modified:
        api_file.write_text("\n".join(lines), encoding="utf-8")
        rprint("[green]✓ Updated API file with OpenAPI registrations")
    else:
        rprint("[yellow]API file already configured for OpenAPI")


def _update_register_http_for_openapi(lines: list[str], controllers: list[tuple[str, str]]) -> bool:
    """Update register_http function to register blueprints with OpenAPI. Returns True if modified."""
    register_http_idx = _find_register_http_function(lines)
    if register_http_idx is None:
        return False

    openapi_call_idx = _find_and_update_openapi_call(lines, register_http_idx)
    if openapi_call_idx is None:
        return False

    existing_registrations = _get_existing_openapi_registrations(lines, openapi_call_idx)
    if existing_registrations:
        return False

    insert_idx = _find_insertion_point(lines, openapi_call_idx)
    return _add_openapi_registrations(lines, insert_idx, controllers)


def _find_register_http_function(lines: list[str]) -> int | None:
    """Find the register_http function. Returns its line index or None."""
    for i, line in enumerate(lines):
        if "def register_http(app" in line:
            return i
    return None


def _find_and_update_openapi_call(lines: list[str], start_idx: int) -> int | None:
    """Find and update configure_openapi call. Returns its line index or None."""
    for j in range(start_idx + 1, len(lines)):
        if "configure_openapi(app)" in lines[j]:
            if not lines[j].strip().startswith("api ="):
                lines[j] = lines[j].replace(
                    "configure_openapi(app)", "api = configure_openapi(app)"
                )
            return j
        elif _is_end_of_function_section(lines[j]):
            break
    return None


def _get_existing_openapi_registrations(lines: list[str], start_idx: int) -> list[str]:
    """Get existing OpenAPI registrations after the given index."""
    registrations: list[str] = []
    for j in range(start_idx + 1, len(lines)):
        if "api.register_blueprint(" in lines[j]:
            registrations.append(lines[j])
        elif _is_end_of_function_section(lines[j]):
            break
    return registrations


def _find_insertion_point(lines: list[str], openapi_call_idx: int) -> int:
    """Find the best insertion point for OpenAPI registrations."""
    insert_idx = openapi_call_idx + 1

    for j in range(openapi_call_idx + 1, len(lines)):
        if "init_" in lines[j] and "_controller(container)" in lines[j]:
            insert_idx = j + 1
        elif "app.register_blueprint(api_bp)" in lines[j]:
            return j
        elif _is_end_of_function_section(lines[j]):
            break

    return insert_idx


def _add_openapi_registrations(
    lines: list[str], insert_idx: int, controllers: list[tuple[str, str]]
) -> bool:
    """Add OpenAPI registrations for controllers. Returns True if modified."""
    lines.insert(insert_idx, "")
    lines.insert(insert_idx + 1, "    # Register existing controllers with OpenAPI")
    insert_idx += 2

    for bc, entity in controllers:
        bp_name = f"{bc}_{entity}_bp"
        reg_line = f"    if hasattr({bp_name}, 'doc'):"
        conditional_reg = f"        api.register_blueprint({bp_name})"

        if reg_line not in lines:
            lines.insert(insert_idx, reg_line)
            lines.insert(insert_idx + 1, conditional_reg)
            insert_idx += 2

    lines.insert(insert_idx, "")
    return True


def _is_end_of_function_section(line: str) -> bool:
    """Check if line indicates end of current function section."""
    return bool(
        line.strip() and not line.startswith("    ") and not line.startswith("#") and line != ""
    )
