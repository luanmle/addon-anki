---
name: anki-hooks-integrator
description: Use this skill when adding behavior to Anki lifecycle events, reviewer, browser, editor, deck browser, profile loading, sync, menus, or webviews; it verifies exact gui_hooks or hooks signatures and prefers documented new-style hooks over monkey-patching or legacy hook guesses.
---

# Anki Hooks Integrator

## Goal

Connect add-on behavior to Anki through verified hooks with correct signatures, lifecycle timing, and cleanup behavior.

## Workflow

1. Describe the event in product terms: what must happen, on which screen, before or after which Anki action.
2. Use `anki-api-source-verifier` to find the exact hook and signature.
3. Prefer `aqt.gui_hooks` or `anki.hooks` generated new-style hooks when available.
4. Distinguish:
   - regular hook: callback runs for side effects;
   - filter: callback must return the first argument, modified or unchanged.
5. Add type hints to every callback so mypy can detect signature errors.
6. Keep callbacks small; delegate expensive or domain work to services/operations.
7. Prevent duplicate registration when modules can be reloaded during development.
8. Test lifecycle assumptions manually in the exact screen and state.

## Hook registration pattern

```python
from __future__ import annotations

from aqt import gui_hooks

_registered = False


def on_verified_event(arg: VerifiedType) -> None:
    ...


def register_hooks() -> None:
    global _registered
    if _registered:
        return
    gui_hooks.<verified_hook>.append(on_verified_event)
    _registered = True
```

Use this as a shape only. The hook and callback signature must come from verified source.

## Decision rules

- If no suitable hook exists, first redesign around existing public operations/hooks.
- Monkey-patching is a last resort and must be isolated, guarded by version checks, reversible where possible, and covered by a compatibility test.
- Never modify a hook list from inside a callback currently being executed.
- Never perform network or large collection work directly in a GUI hook callback.

## Constraints

- Do not infer signatures from callback names.
- Do not mix legacy `addHook()` examples into modern code unless legacy support is explicitly required and verified.
- Do not register anonymous lambdas when they prevent removal, typing, or testing.
- Do not claim a hook fires in a lifecycle state without confirming it.
