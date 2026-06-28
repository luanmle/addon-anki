# Sync stale note id recovery

- What changed: Sync now validates locally stored `anki_note_id` values before updating, suspending, or deprecating notes.
- Why: Users can delete notes in Anki while the add-on still has old sync metadata. A stale note id could make sync think it updated a note that no longer exists.
- Files/modules touched: `anki_concursos/services/note_manager.py`, `anki_concursos/sync/engine.py`, `anki_concursos/tests/test_sync.py`.
- User-visible behavior: No new UI. Sync becomes more resilient when local notes were manually deleted.
- Internal behavior: If a stored note id no longer exists, sync searches the collection by `Card ID`. If no note is found, added/updated changes recreate the note, and removed/deprecated changes update local metadata without trying to suspend a missing note.
- Backend API contracts touched: None.
- Storage/config changes: No schema change.

## Before

Sync trusted `remote_cards.anki_note_id`. If that Anki note had been deleted, update/suspend/deprecate could silently fail while local release tracking advanced.

## After

Sync resolves the current Anki note before each card action. Stale ids do not block applying the server release.

## Validation

- Automated checks: focused sync tests and compile checks.
- Manual checks: not run in Anki.

## Risks

- If a user deletes a note and the server later sends an `updated` action, sync recreates it because the active server card still exists.
