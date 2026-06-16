---
name: anki-package-release
description: Use this skill when building, exporting, distributing, publishing, or validating an Anki .ankiaddon package; it creates an archive without the top-level folder, excludes caches and development files, validates manifest/config JSON, and records compatibility and release checks.
---

# Anki Package and Release

## Goal

Produce a clean, installable `.ankiaddon` archive with correct root layout and traceable release evidence.

## Workflow

1. Run `anki-testing-quality-gate` first.
2. Confirm the package directory contains `__init__.py` and all runtime resources.
3. Validate `config.json` and `manifest.json` when present.
4. Remove/exclude `__pycache__`, `.pyc`, tests, local environments, secrets, logs, and build output.
5. Run:

```bash
python scripts/package_addon.py <addon-package-directory> --output dist/addon-name.ankiaddon
```

6. Inspect archive contents. Files must be at archive root, not nested under the package folder.
7. Install the generated file into a clean test profile.
8. Verify startup, configuration, feature flow, restart, and uninstall/upgrade behavior.
9. Record supported Anki versions and release notes.
10. For distribution outside AnkiWeb, ensure the required manifest metadata is present and accurate.

## Release checklist

- no credentials or local URLs;
- no user-specific `meta.json`;
- no development-only dependencies missing from the archive;
- licenses included for vendored dependencies/assets;
- configuration defaults documented;
- migrations tested from the previous released version;
- archive hash optionally recorded for reproducibility.

## Constraints

- Do not include the package directory itself as the top archive entry.
- Do not include `__pycache__` or compiled bytecode.
- Do not publish before clean-profile installation succeeds.
- Do not infer AnkiWeb metadata requirements from third-party examples; verify official sharing docs.
