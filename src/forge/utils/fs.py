"""
Filesystem utilities for Forge CLI.

This module provides helper functions for filesystem operations commonly needed
during code generation and project setup. It focuses on Python package structure
management, particularly ensuring proper package initialization files.

Key features:
- Automatic directory creation with parent directory support
- Python package initialization (__init__.py) file management
- Batch directory and package setup operations
- Safe file operations with proper encoding handling
"""

from pathlib import Path


def ensure_init_files(root: Path, rel_dirs: list[str]) -> None:
    """
    Ensure directories exist with proper Python package initialization.

    Creates the specified directories (and any necessary parent directories)
    and ensures each directory has an __init__.py file to make it a proper
    Python package. This is essential for the generated code structure to
    be importable.

    Args:
        root: Root path where the directories should be created
        rel_dirs: List of relative directory paths from the root.
                 These will be created as Python packages with __init__.py files.

    Example:
        root = Path("src/myapp")
        rel_dirs = ["domain/users", "app/users", "infra/users"]
        ensure_init_files(root, rel_dirs)

        This creates:
        src/myapp/domain/__init__.py
        src/myapp/domain/users/__init__.py
        src/myapp/app/__init__.py
        src/myapp/app/users/__init__.py
        src/myapp/infra/__init__.py
        src/myapp/infra/users/__init__.py

    Behavior:
        - Creates directories recursively (like mkdir -p)
        - Only creates __init__.py if it doesn't already exist
        - Uses UTF-8 encoding for all files
        - Creates empty __init__.py files by default

    Note:
        This function is idempotent - it can be called multiple times safely
        without overwriting existing files or causing errors.
    """
    for dir_path in rel_dirs:
        # Create the full directory path
        full_path = root / dir_path
        full_path.mkdir(parents=True, exist_ok=True)

        # Ensure __init__.py exists in the target directory
        init_file = full_path / "__init__.py"
        if not init_file.exists():
            init_file.write_text("", encoding="utf-8")

        # Also ensure all parent directories have __init__.py files
        _ensure_parent_init_files(root, full_path)


def _ensure_parent_init_files(root: Path, target_path: Path) -> None:
    """
    Ensure all parent directories between root and target have __init__.py files.

    This helper function walks up the directory tree from the target path
    back to the root, ensuring each intermediate directory is a proper
    Python package with an __init__.py file.

    Args:
        root: The root path (stopping point for package creation)
        target_path: The deepest path that needs package initialization

    Example:
        root = Path("src/myapp")
        target_path = Path("src/myapp/domain/users/repositories")

        This ensures __init__.py exists in:
        - src/myapp/domain/
        - src/myapp/domain/users/
        - src/myapp/domain/users/repositories/
    """
    current_path = target_path

    # Walk up the directory tree until we reach the root
    while current_path != root and root in current_path.parents:
        parent_path = current_path.parent

        # Skip if we've reached the root
        if parent_path == root:
            break

        # Ensure parent directory has __init__.py
        parent_init = parent_path / "__init__.py"
        if not parent_init.exists():
            parent_init.write_text("", encoding="utf-8")

        current_path = parent_path
