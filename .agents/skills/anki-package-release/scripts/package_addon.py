#!/usr/bin/env python3
"""Build a clean .ankiaddon archive with add-on files at archive root."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import zipfile

EXCLUDED_DIRS = {".git", ".venv", "venv", "tests", "test", "__pycache__", ".mypy_cache", ".pytest_cache", "dist", "build"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log"}
EXCLUDED_NAMES = {"meta.json", ".env", ".DS_Store"}


def should_include(path: Path, package_dir: Path) -> bool:
    rel = path.relative_to(package_dir)
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return False
    if path.name in EXCLUDED_NAMES or path.suffix in EXCLUDED_SUFFIXES:
        return False
    return path.is_file()


def validate_json(package_dir: Path, name: str) -> None:
    path = package_dir / name
    if path.exists():
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"Invalid {name}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    package_dir = args.package_dir.resolve()
    output = args.output.resolve()
    if not (package_dir / "__init__.py").is_file():
        print("Package directory must contain __init__.py", file=sys.stderr)
        return 2
    try:
        validate_json(package_dir, "config.json")
        validate_json(package_dir, "manifest.json")
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 3

    files = sorted(path for path in package_dir.rglob("*") if should_include(path, package_dir))
    if not files:
        print("No files to package", file=sys.stderr)
        return 4

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, path.relative_to(package_dir).as_posix())

    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        if "__init__.py" not in names:
            print("Archive validation failed: __init__.py is not at archive root", file=sys.stderr)
            output.unlink(missing_ok=True)
            return 5
        if any(name.startswith(package_dir.name + "/") for name in names):
            print("Archive validation failed: top-level package folder was included", file=sys.stderr)
            output.unlink(missing_ok=True)
            return 6

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
