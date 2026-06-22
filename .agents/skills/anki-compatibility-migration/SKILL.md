---
name: anki-compatibility-migration
description: Use this skill when an add-on breaks on a specific Anki version, when migrating from Qt5 to Qt6, when adapting changed hooks or renamed APIs after an Anki upgrade, or when removing deprecated code from a previously supported version window; it builds a verified compatibility matrix and centralizes proven branches in compat.py.
---

# Anki Compatibility and Migration

## Goal

Support an explicit set of Anki versions with verified APIs instead of accumulating speculative compatibility code.

## Workflow

1. Define the support window in concrete versions.
2. For each supported version, record:
   - bundled Python version;
   - Qt generation/build constraints;
   - required hooks/APIs;
   - dependency availability;
   - packaging metadata constraints.
3. Verify every changed symbol against source/stubs for each branch.
4. Prefer code that works through `aqt.qt` and stable public Anki APIs.
5. Centralize genuine differences in `compat.py` or small adapters.
6. Feature-detect only when the tested attribute accurately represents capability.
7. Fail early with a clear unsupported-version message when compatibility is impossible.
8. Remove legacy branches when the supported window no longer needs them.
9. Test at the oldest and newest supported versions, plus any known transition version.

## Compatibility adapter pattern

```python
# compat.py
# Imports and branches here must be backed by tests/source evidence.

def supported_feature(...) -> ...:
    if verified_new_capability:
        ...
    else:
        ...
```

Do not scatter `hasattr()` and version string checks throughout UI and domain modules.

## Version comparison rules

- Use a proper version parser or Anki-provided version helpers when verified.
- Do not compare version strings lexicographically.
- Do not infer compatibility from “it imports” alone.

## Constraints

- Do not promise support for an untested version.
- Do not import from `PyQt5`/`PyQt6` directly for routine UI compatibility.
- Do not preserve dead legacy hooks without a documented support reason.
- Do not add catch-all exceptions that hide version failures.
