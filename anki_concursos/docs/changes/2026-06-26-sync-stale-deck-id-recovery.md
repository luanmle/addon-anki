# Sync stale deck id recovery

- What changed: Sync now validates locally stored `anki_deck_id` values before creating new notes during an incremental sync.
- Why: Users can delete or rename/remove local Anki decks while the add-on still tracks the old deck id. Creating a new note with a stale deck id can fail or place cards incorrectly.
- Files/modules touched: `anki_concursos/services/deck_manager.py`, `anki_concursos/sync/engine.py`, `anki_concursos/tests/test_sync.py`.
- User-visible behavior: No new UI. If the tracked Anki deck is missing, sync recreates the add-on deck path and continues.
- Internal behavior: `SyncEngine` resolves the current Anki deck id before `create_note()`. Missing ids are recreated through the existing `DeckManager.ensure_deck()` path and persisted back to `remote_decks`.
- Backend API contracts touched: None.
- Storage/config changes: No schema change.

## Before

Sync trusted `remote_decks.anki_deck_id` when creating notes for new/updated cards.

## After

Sync checks the deck id against the Anki collection and recreates the deck when needed before creating notes.

## Validation

- Automated checks: focused sync tests and compile checks.
- Manual checks: not run in Anki.

## Risks

- If a user intentionally deleted the local Anki deck but remains subscribed, sync recreates it when the server sends a card that needs a local note.
