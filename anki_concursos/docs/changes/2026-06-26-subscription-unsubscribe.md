# 2026-06-26: Subscription Unsubscribe Action

## Summary

- What changed: My Subscriptions now exposes an Unsubscribe action per active remote subscription.
- Why: Users need a way to cancel a platform subscription from the add-on, not only install missing local decks.

## Scope

- Files/modules touched: `anki_concursos/gui/status_dialog.py`.
- User-visible behavior: The subscriptions table has separate Install and Subscription actions.
- Internal behavior: Unsubscribe calls the backend cancel endpoint and removes the add-on's local sync tracking for that deck.

## Before

Subscribed decks could be installed from My Subscriptions, but there was no add-on path to cancel the remote subscription.

## After

Clicking Unsubscribe confirms the action, calls `ApiClient.unsubscribe()`, deletes the local `remote_decks` and `remote_cards` tracking rows, and refreshes the table. Existing Anki cards remain in the user's collection.

## Implementation Notes

- Key decisions: The add-on forgets sync metadata only; it does not delete Anki notes or decks.
- Anki APIs/hooks touched: `aqt.operations.QueryOp`, `QMessageBox`.
- Backend API contracts touched: Existing `POST /subscriptions/{deck_id}/cancel` via `ApiClient.unsubscribe()`.
- Storage/config changes: Existing `DatabaseManager.delete_deck()` is used to stop future local sync for the canceled subscription.

## Verification

- Automated checks: Passed `/tmp/anki-addon-pytest-venv/bin/python -m pytest` (57 tests), `compileall`, and `validate_addon.py`.
- Manual Anki checks: Not run in this environment.
- Not run: Real unsubscribe flow against the platform from Anki.

## Risks

- Known risks: If the backend cancel succeeds but local SQLite delete fails, the user may need to retry or clear local data.
- Rollback notes: Remove the Unsubscribe column and related handlers.

## Follow-ups

- Consider a backend `DELETE /subscriptions/{deck_id}` alias for clearer REST semantics.
