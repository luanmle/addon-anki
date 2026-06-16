#!/usr/bin/env python3
"""Conservative static audit for common Anki add-on hazards.

This tool reports findings; source verification and real-Anki tests remain required.
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
import re
import sys

IGNORED_DIRS = {".git", ".venv", "venv", "dist", "build", "__pycache__", ".mypy_cache", ".pytest_cache"}


@dataclass(frozen=True)
class Finding:
    level: str
    path: Path
    line: int
    message: str


class Visitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.findings: list[Finding] = []
        self.scope_depth = 0

    def add(self, level: str, node: ast.AST, message: str) -> None:
        self.findings.append(Finding(level, self.path, getattr(node, "lineno", 1), message))

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name.startswith(("PyQt5", "PyQt6")):
                self.add("ERROR", node, "Import Qt classes from aqt.qt, not directly from PyQt5/PyQt6")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if (node.module or "").startswith(("PyQt5", "PyQt6")):
            self.add("ERROR", node, "Import Qt classes from aqt.qt, not directly from PyQt5/PyQt6")
        if node.module == "anki.hooks" and any(alias.name == "addHook" for alias in node.names):
            self.add("WARN", node, "Legacy addHook detected; verify that no new-style hook covers this use case")
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope_depth += 1
        self.generic_visit(node)
        self.scope_depth -= 1

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if self.scope_depth == 0 and node.attr == "col" and isinstance(node.value, ast.Name) and node.value.id == "mw":
            self.add("ERROR", node, "mw.col accessed at module import time; wait until a collection is loaded")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = dotted_name(node.func)
        if name in {"requests.get", "requests.post", "requests.put", "requests.patch", "requests.delete", "httpx.get", "httpx.post"}:
            keyword_names = {kw.arg for kw in node.keywords}
            if "timeout" not in keyword_names:
                self.add("ERROR", node, f"HTTP call {name} has no explicit timeout")
            self.add("WARN", node, f"Confirm {name} runs in an Anki background operation, not the UI thread")
        if name.endswith(".db.execute") or name.endswith(".db.executemany"):
            literal = first_string_arg(node)
            if literal and re.search(r"\b(insert|update|delete|alter|drop|create)\b", literal, re.I):
                self.add("ERROR", node, "Direct SQL mutation/schema operation detected; use public Collection APIs")
            else:
                self.add("WARN", node, "Direct database access detected; document why a public Collection API is insufficient")
        self.generic_visit(node)


def dotted_name(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def first_string_arg(node: ast.Call) -> str | None:
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        return node.args[0].value
    return None


def python_files(root: Path):
    for path in root.rglob("*.py"):
        if not any(part in IGNORED_DIRS for part in path.parts):
            yield path


def audit_json(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for name in ("config.json", "manifest.json"):
        for path in root.rglob(name):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                findings.append(Finding("ERROR", path, 1, f"Invalid JSON: {exc}"))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.exists():
        parser.error(f"Path does not exist: {root}")

    findings: list[Finding] = []
    for path in python_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            findings.append(Finding("ERROR", path, exc.lineno or 1, f"Syntax error: {exc.msg}"))
            continue
        visitor = Visitor(path)
        visitor.visit(tree)
        findings.extend(visitor.findings)
    findings.extend(audit_json(root))

    for finding in sorted(findings, key=lambda f: (str(f.path), f.line, f.level)):
        print(f"{finding.level}: {finding.path}:{finding.line}: {finding.message}")

    errors = sum(f.level == "ERROR" for f in findings)
    warnings = sum(f.level == "WARN" for f in findings)
    print(f"Audit complete: {errors} error(s), {warnings} warning(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
