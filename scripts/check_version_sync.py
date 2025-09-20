import re
import sys
import pathlib

root = pathlib.Path(__file__).resolve().parents[1]
pyproj = (root / "pyproject.toml").read_text(encoding="utf-8")
pkg = (root / "src/forge/__init__.py").read_text(encoding="utf-8")

m1 = re.search(r'\nversion\s*=\s*"([^"]+)"', pyproj)
m2 = re.search(r'__version__\s*=\s*"([^"]+)"', pkg)
if not (m1 and m2):
    print("Could not find version in pyproject.toml or src/forge/__init__.py")
    sys.exit(1)

v1, v2 = m1.group(1), m2.group(1)
if v1 != v2:
    print(f"Version mismatch: pyproject.toml={v1} vs __init__={v2}")
    sys.exit(2)

print(f"Version OK: {v1}")
