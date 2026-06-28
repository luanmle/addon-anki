# 2026-06-26: Sync Respects Remote Subscriptions

## Summary

- What changed: Sync Now checks active platform subscriptions before syncing local tracked decks.
- Why: A deck canceled on the platform should stop syncing locally without throwing manifest/sync authorization errors.

## Scope

- Files/modules touched: `anki_concursos/sync/engine.py`, `anki_concursos/tests/test_sync.py`.
- User-visible behavior: Sync Now forgets local sync tracking for decks no longer subscribed and keeps existing Anki cards/decks.
- Internal behavior: Existing local decks are filtered by active `GET /subscriptions` results before manifest/sync fetches.

## Before

Sync Now attempted to fetch manifest and changes for every local `remote_decks` row, even if the platform subscription had been canceled elsewhere.

## After

Sync Now lists subscriptions first, deletes local sync metadata for unsubscribed decks, skips their remote sync fetch, and continues syncing/installing active subscriptions. The final sync message now reports the install and cleanup counts when those actions happen.

## Implementation Notes

- Key decisions: This deletes only add-on SQLite tracking, not Anki notes/decks.
- Anki APIs/hooks touched: Existing `QueryOp` flow only.
- Backend API contracts touched: Existing `GET /subscriptions`.
- Storage/config changes: Uses existing `DatabaseManager.delete_deck()`.

## Verification

- Automated checks: Passed `compileall`, focused `test_sync.py` (23 tests), full `/tmp/anki-addon-pytest-venv/bin/python -m pytest` (59 tests), and `validate_addon.py`.
- Manual Anki checks: Not run in this environment.
- Not run: Real platform cancel from web followed by Sync Now in Anki.

## Risks

- Known risks: If `GET /subscriptions` is unavailable, Sync Now fails before local deck sync because active entitlement cannot be verified.
- Rollback notes: Restore per-local-deck sync before subscription reconciliation.

## Follow-ups

- N/A
