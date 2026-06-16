#!/usr/bin/env python3
"""Create a conservative Anki add-on package without overwriting files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

PACKAGE_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

FILES: dict[str, str] = {
    "__init__.py": '"""Anki add-on entry point."""\n\nfrom .bootstrap import register_addon\n\nregister_addon()\n',
    "bootstrap.py": ("\"\"\"Register hooks and UI actions. Keep imports/startup side effects minimal.\"\"\"\n\n"
                     "from __future__ import annotations\n\n"
                     "_registered = False\n\n\n"
                     "def register_addon() -> None:\n"
                     "    global _registered\n"
                     "    if _registered:\n"
                     "        return\n"
                     "    # Add only source-verified hook/menu registration here.\n"
                     "    _registered = True\n"),
    "config.json": "{}\n",
    "config.md": "# Configuration\n\nDocument each supported setting here.\n",
    "py.typed": "",
    "user_files/README.txt": "Files in this directory are preserved when the add-on is upgraded.\n",
    "services/__init__.py": '"""Application/domain services independent from Anki UI."""\n',
    "anki_adapters/__init__.py": '"""Source-verified adapters around anki/aqt APIs."""\n',
    "tests/__init__.py": "",
    "tests/test_smoke.py": ("from __future__ import annotations\n\n\n"
                            "def test_placeholder() -> None:\n"
                            "    assert True\n"),
}


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path, help="Parent directory for the package")
    parser.add_argument("--name", required=True, help="Human-readable add-on name")
    parser.add_argument("--package", required=True, help="Python/add-on package directory name")
    parser.add_argument("--with-web", action="store_true")
    parser.add_argument("--with-remote", action="store_true")
    args = parser.parse_args()

    if not PACKAGE_RE.fullmatch(args.package):
        parser.error("--package must be a valid Python identifier")

    package_dir = args.target.resolve() / args.package
    if package_dir.exists() and any(package_dir.iterdir()):
        print(f"Refusing to overwrite non-empty directory: {package_dir}", file=sys.stderr)
        return 2
    package_dir.mkdir(parents=True, exist_ok=True)

    files = dict(FILES)
    manifest = {"package": args.package, "name": args.name}
    files["manifest.json"] = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    if args.with_web:
        files["web/app.js"] = "// Register this asset through a source-verified setWebExports pattern.\n"
        files["web/app.css"] = f".{args.package.replace('_', '-')}-root {{}}\n"
    if args.with_remote:
        files["remote/__init__.py"] = '"""Typed remote API boundary."""\n'
        files["remote/client.py"] = ("\"\"\"HTTP client placeholder. Add timeouts and run calls in background operations.\"\"\"\n\n"
                                     "from __future__ import annotations\n")

    try:
        for relative, content in files.items():
            write_new(package_dir / relative, content)
    except FileExistsError as exc:
        print(f"Refusing to overwrite existing file: {exc}", file=sys.stderr)
        return 3

    print(package_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
