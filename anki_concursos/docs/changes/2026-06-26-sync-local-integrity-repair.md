# Sync local integrity repair

- What changed: Sync now repairs safe local metadata issues before contacting the platform.
- Why: Old or interrupted local state can leave `remote_cards` or `sync_log` rows pointing at missing `remote_decks`, which can break later sync and unsubscribe flows.
- Files/modules touched: `anki_concursos/storage/database.py`, `anki_concursos/sync/engine.py`, `anki_concursos/tests/test_storage.py`, `anki_concursos/tests/test_sync.py`.
- User-visible behavior: When rows are repaired, the final sync message includes `🧰 Repaired ... local sync metadata rows.`
- Internal behavior: `DatabaseManager.repair_integrity()` deletes orphan add-on metadata rows, then runs SQLite `PRAGMA integrity_check` and `PRAGMA foreign_key_check`.
- Backend API contracts touched: None.
- Storage/config changes: No schema change.

## Before

Sync trusted local SQLite metadata before fetching remote subscription and release data.

## After

Sync performs a local integrity repair/check first. Only add-on metadata is modified; existing Anki notes and decks are not deleted.

## Validation

- Automated checks: focused storage/sync tests and compile checks.
- Manual checks: not run in Anki.

## Risks

- Historical sync logs for already-missing local deck rows are removed.
- SQLite corruption still aborts sync instead of attempting unsafe repair.
