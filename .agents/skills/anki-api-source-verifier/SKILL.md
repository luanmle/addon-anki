---
name: anki-api-source-verifier
description: Use this skill whenever an Anki API, hook, callback signature, class, module path, Qt symbol, operation helper, or version requirement is uncertain; it requires inspecting the target Anki source, installed stubs, or official documentation instead of guessing names from memory.
---

# Anki API Source Verifier

## Goal

Prove that each Anki-specific symbol and callback signature exists for the target version before implementation.

## Workflow

1. Determine the target version from project metadata, user requirements, installed package metadata, or the running Anki environment.
2. Search in this order:
   1. existing repository usage and tests;
   2. installed `anki` and `aqt` packages/stubs;
   3. official Anki source matching the target tag;
   4. official add-on docs and official demos.
3. For hooks, inspect generated hook definitions and capture:
   - exact hook name;
   - exact callback parameters and types;
   - return contract for filters;
   - lifecycle timing;
   - minimum version if known.
4. For methods/classes, capture exact import path, callable signature, return type, thread constraints, and mutation/sync behavior.
5. Run `python scripts/inspect_anki_runtime.py ...` when the target packages are installed.
6. Create a small compatibility adapter when multiple supported versions expose different proven APIs.
7. If a symbol cannot be verified, stop using it. Report the gap and choose a documented alternative.

## Evidence note template

```text
Symbol: gui_hooks.<exact_name>
Verified in: <source path/tag/docs page>
Signature: (<exact parameters>) -> <return>
Lifecycle: <when it fires>
Minimum version: <verified value or unknown>
```

## Source discipline

- Pin GitHub source inspection to a release tag or commit compatible with the target Anki version.
- Treat blogs, forum snippets, generated answers, and old add-ons as leads, not proof.
- Prefer type hints and generated hook definitions over memory.
- Re-verify APIs during version upgrades.

## Constraints

- Never fabricate a close-sounding hook or method.
- Never silently substitute a legacy hook for a new-style hook.
- Never copy an example without checking its version context.
- Never state a minimum Anki version unless it is supported by evidence.
