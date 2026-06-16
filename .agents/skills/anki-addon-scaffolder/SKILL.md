---
name: anki-addon-scaffolder
description: Use this skill when the user asks to create, initialize, scaffold, bootstrap, or reorganize an Anki add-on package; it generates a conservative modular structure with a thin entry point, configuration, tests, typing, and optional UI/network modules without inventing product-specific behavior.
---

# Anki Add-on Scaffolder

## Goal

Create a valid, minimal, modular add-on structure that is safe to extend and easy to test.

## Workflow

1. Inspect the workspace and do not overwrite existing files unless explicitly requested.
2. Choose a lowercase Python package directory name that is stable across releases.
3. Run:

```bash
python scripts/scaffold_addon.py <target-directory> --name "Display Name" --package package_name
```

4. Keep `__init__.py` limited to bootstrap and registration.
5. Add only modules required by the requested feature. Typical modules:
   - `bootstrap.py` for registration;
   - `config.py` for validated settings;
   - `ui/` for Qt;
   - `web/` for static web assets;
   - `services/` for application logic;
   - `anki_adapters/` for Anki-specific operations;
   - `remote/` for API clients;
   - `tests/` for pure logic.
6. Replace placeholders only after API verification.
7. Run the quality gate after scaffolding.

## Default structure

```text
package_name/
├── __init__.py
├── bootstrap.py
├── config.json
├── config.md
├── manifest.json
├── py.typed
├── user_files/README.txt
├── services/
├── anki_adapters/
└── tests/
```

Web and remote folders are opt-in so a simple add-on does not receive unnecessary complexity.

## Bootstrap rules

- Imports must not require `mw.col` during startup.
- Registration functions must be idempotent within a process.
- Collection-dependent work must wait for an appropriate action/hook.
- Use explicit imports; avoid wildcard imports in generated production code.

## Constraints

- Do not put business logic in `__init__.py`.
- Do not assume a collection/profile is loaded at import time.
- Do not add dependencies that the user did not request.
- Do not overwrite an existing package without a backup or explicit instruction.
