from pathlib import Path


def ensure_init_files(root: Path, rel_dirs: list[str]) -> None:
    for d in rel_dirs:
        p = root / d
        p.mkdir(parents=True, exist_ok=True)
        f = p / "__init__.py"
        if not f.exists():
            f.write_text("", encoding="utf-8")
