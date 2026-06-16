---
name: anki-addon-orchestrator
description: Use this skill for broad Anki add-on requests in English or Portuguese, including criar extensão, desenvolver add-on, add feature, refactor plugin, plan architecture, or review an existing add-on; it coordinates the specialized Anki skills and prevents implementation before APIs and lifecycle assumptions are verified.
---

# Anki Add-on Orchestrator

## Goal

Turn a broad add-on request into a verified, version-aware implementation while loading only the specialized skills needed for the affected Anki domains.

## Workflow

1. Inspect the repository before writing code.
   - Identify the add-on package root, entry point, configuration, tests, build scripts, and target Anki versions.
   - Read existing conventions instead of replacing them with generic boilerplate.
2. Restate the requested behavior as observable acceptance criteria.
3. Produce a domain map:
   - lifecycle/hooks;
   - collection and media;
   - Qt UI;
   - webview/reviewer/editor;
   - background work and networking;
   - configuration/storage;
   - compatibility;
   - testing/release.
4. Activate `anki-api-source-verifier` before using any Anki symbol not already proven in the repository.
5. Activate only the relevant implementation skills from the domain map.
6. Prefer a thin `__init__.py` that registers integrations and delegates real logic to modules.
7. Implement the smallest coherent vertical slice first.
8. Run `anki-testing-quality-gate` before claiming completion.
9. Run `anki-package-release` only when a distributable artifact is requested.

## Required evidence

For every Anki-specific integration, record at least one of:

- symbol found in the installed `anki`/`aqt` package or stubs for the target version;
- official hook definition in `genhooks.py` or `genhooks_gui.py`;
- official documentation or demo matching the target version;
- pre-existing, tested usage in this repository.

When evidence is missing, mark the item as unverified and continue with an isolated adapter or TODO. Never present a guessed API as working code.

## Architecture defaults

- Keep UI, application services, remote clients, persistence, and Anki adapters separate.
- Pass IDs and plain data across background boundaries; reacquire Anki objects inside the correct operation.
- Make remote synchronization resumable and idempotent.
- Centralize compatibility branches instead of scattering version checks.
- Avoid side effects during module import beyond safe hook/menu registration.

## Completion format

Report:

1. files changed;
2. verified Anki APIs/hooks and their evidence;
3. behavior implemented;
4. automated checks run and results;
5. manual checks still required inside Anki;
6. compatibility assumptions and known risks.

## Constraints

- Do not invent hook names, callback signatures, classes, methods, enum members, module paths, or minimum versions.
- Do not directly modify Anki's source files or built-in database schema.
- Do not perform long-running work on the UI thread.
- Do not claim an add-on works merely because Python syntax is valid.
- Do not rewrite unrelated code while implementing a focused request.
