#!/usr/bin/env python3
"""Inspect installed Anki/aqt symbols without guessing APIs.

Examples:
  python inspect_anki_runtime.py module aqt.gui_hooks
  python inspect_anki_runtime.py symbol aqt.gui_hooks reviewer_did_show_question
  python inspect_anki_runtime.py signature aqt.operations QueryOp
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import sys
from importlib import metadata


def load_module(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:
        raise SystemExit(f"Unable to import {name!r}: {exc}") from exc


def package_versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for package in ("anki", "aqt"):
        try:
            result[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            result[package] = "not installed"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("module", "symbol", "signature", "versions"))
    parser.add_argument("module", nargs="?")
    parser.add_argument("symbol", nargs="?")
    args = parser.parse_args()

    if args.mode == "versions":
        print(json.dumps(package_versions(), indent=2))
        return 0
    if not args.module:
        parser.error("module is required for this mode")

    module = load_module(args.module)
    if args.mode == "module":
        public = sorted(name for name in dir(module) if not name.startswith("_"))
        print("\n".join(public))
        return 0
    if not args.symbol:
        parser.error("symbol is required for symbol/signature mode")
    if not hasattr(module, args.symbol):
        print(f"{args.module}.{args.symbol} was not found", file=sys.stderr)
        return 2

    value = getattr(module, args.symbol)
    if args.mode == "symbol":
        print(repr(value))
        print(f"type={type(value)!r}")
        print(f"module={getattr(value, '__module__', None)!r}")
        print(f"doc={inspect.getdoc(value)!r}")
        return 0

    try:
        signature = inspect.signature(value)
    except (TypeError, ValueError) as exc:
        print(f"Signature unavailable: {exc}", file=sys.stderr)
        return 3
    print(f"{args.module}.{args.symbol}{signature}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
