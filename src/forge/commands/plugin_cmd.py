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

    rprint("[green]✓ OpenAPI installed.")
    rprint("[blue]Available routes:")
    rprint("[blue]  • Swagger UI: /docs-[unique-id]/swagger-ui")
    rprint("[blue]  • ReDoc: /docs-[unique-id]/redoc")
    rprint("[blue]  • OpenAPI spec: /docs-[unique-id]/openapi.json")
    rprint("[yellow]Note: [unique-id] will be a generated 8-character identifier")


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
import uuid

# Global API instance para que los blueprints puedan registrarse
openapi_api = None

def configure_openapi(app):
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
    
    return openapi_api

def get_api_instance():
    \"\"\"Get the global API instance for blueprint registration.\"\"\"
    return openapi_api
"""
