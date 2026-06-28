# Local database check menu

- What changed: Added `Check Local Database` to the Anki Concursos menu.
- Why: Users and support need a way to run the local sync metadata repair/check without starting a remote sync.
- Files/modules touched: `anki_concursos/gui/menu.py`, `anki_concursos/tests/test_menu.py`.
- User-visible behavior: The menu action reports either no repairs, repaired row count, or the integrity error.
- Internal behavior: The action runs `DatabaseManager.repair_integrity()` through `QueryOp`.
- Backend API contracts touched: None.
- Storage/config changes: No schema change.

## Before

Local integrity repair ran only as part of sync/install flows.

## After

Users can manually check local sync metadata from the add-on menu.

## Validation

- Automated checks: focused menu tests and compile checks.
- Manual checks: not run in Anki.
