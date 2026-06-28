# 2026-06-26: Unsubscribe Local Cleanup Foreign Key Fix

## Summary

- What changed: Deleting local deck sync tracking now removes related sync logs before deleting `remote_decks`.
- Why: Unsubscribe could cancel on the backend but fail locally with `FOREIGN KEY constraint failed`.

## Scope

- Files/modules touched: `anki_concursos/storage/database.py`, `anki_concursos/gui/status_dialog.py`, `anki_concursos/tests/test_storage.py`.
- User-visible behavior: Unsubscribe no longer shows a false failure after the backend cancellation succeeds.
- Internal behavior: My Subscriptions also forgets local tracking for decks no longer present in active backend subscriptions.

## Before

`DatabaseManager.delete_deck()` deleted cards and then the deck row, but `sync_log` still referenced that deck.

## After

`DatabaseManager.delete_deck()` deletes `remote_cards`, `sync_log`, and then `remote_decks` in one transaction.

## Implementation Notes

- Key decisions: Existing Anki notes/decks are still kept; only add-on sync metadata is deleted.
- Anki APIs/hooks touched: None.
- Backend API contracts touched: None.
- Storage/config changes: Sync logs for an unsubscribed deck are removed with local tracking.

## Verification

- Automated checks: Passed targeted storage tests, full `/tmp/anki-addon-pytest-venv/bin/python -m pytest` (58 tests), `compileall`, and `validate_addon.py`.
- Manual Anki checks: Not run in this environment.
- Not run: Real unsubscribe retry in Anki.

## Risks

- Known risks: Historical sync log rows for unsubscribed decks are removed locally.
- Rollback notes: Restore the prior `delete_deck()` ordering if log retention becomes required.

## Follow-ups

- N/A
