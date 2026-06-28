# 2026-06-26: Background Browse Decks Actions

## Summary

- What changed: Browse Decks now loads the catalog and subscribes through Anki `QueryOp`.
- Why: Avoid blocking the Qt UI while the add-on waits for platform API responses.

## Scope

- Files/modules touched: `anki_concursos/gui/deck_browser.py`.
- User-visible behavior: Refresh and Subscribe show Anki progress instead of freezing the dialog.
- Internal behavior: API requests moved from direct dialog callbacks to background operations.

## Before

`Browse Decks` called `list_subscribable_decks()` and `subscribe()` directly in the Qt callback thread.

## After

`Browse Decks` disables Refresh while loading, runs catalog/subscription API calls via `QueryOp`, then updates the table on success.

## Implementation Notes

- Key decisions: Kept install behavior unchanged because `DeckInstaller` already owns its background operation.
- Anki APIs/hooks touched: `aqt.operations.QueryOp`.
- Backend API contracts touched: None.
- Storage/config changes: None.

## Verification

- Automated checks: Passed `/tmp/anki-addon-pytest-venv/bin/python -m pytest` (57 tests), `compileall`, and `validate_addon.py`.
- Manual Anki checks: Not run in this environment.
- Not run: Real login/catalog/subscription flow in Anki.

## Risks

- Known risks: Requires real Anki UI smoke test to confirm progress dialog and button callbacks behave correctly in the host Qt event loop.
- Rollback notes: Revert this file to direct API calls if QueryOp integration misbehaves.

## Follow-ups

- N/A
