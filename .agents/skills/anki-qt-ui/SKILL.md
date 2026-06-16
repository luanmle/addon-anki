---
name: anki-qt-ui
description: Use this skill when creating Anki menus, actions, dialogs, forms, preferences, toolbars, shortcuts, widgets, signals, or notifications; it enforces imports through aqt.qt, verified Qt compatibility, proper parenting and object lifetime, and separation from business logic.
---

# Anki Qt UI

## Goal

Build native Anki UI that survives supported Qt versions, follows Anki conventions, and does not leak business logic into widgets.

## Workflow

1. Verify the target Anki/Qt support matrix.
2. Import Qt classes and helpers from `aqt.qt`, never directly from `PyQt5` or `PyQt6` unless an explicitly verified exception is required.
3. Use verified Anki utilities such as `qconnect` and user-message helpers where appropriate.
4. Parent dialogs/widgets to an existing Anki window.
5. Preserve a reference to top-level widgets that would otherwise be garbage-collected.
6. Keep view code responsible for display and input only; call services for work.
7. Launch long operations with `anki-background-operations`.
8. Validate user input before closing/applying.
9. Support keyboard navigation, useful labels, and clear errors.
10. Manually test reopening, profile switching, closing Anki, and repeated action invocation.

## UI design rules

- Reuse Anki-provided parent windows and standard dialogs when possible.
- Do not block the event loop with polling or synchronous requests.
- Use explicit signal handlers instead of dense lambdas.
- Avoid generated `.ui` files unless the project has a repeatable Qt5/Qt6 build strategy.
- Store settings through `anki-config-storage`, not directly in widget state.

## Lifetime checks

Before completion, verify:

- the dialog remains visible after the function returns;
- reopening does not create hidden duplicate instances unless intended;
- closing releases resources and stops timers;
- callbacks do not reference deleted Qt objects.

## Constraints

- Do not use `from aqt.qt import *` in new production modules.
- Do not import directly from a PyQt version-specific package.
- Do not access Qt from background threads.
- Do not hardcode OS-specific paths, fonts, or dimensions without fallback behavior.
