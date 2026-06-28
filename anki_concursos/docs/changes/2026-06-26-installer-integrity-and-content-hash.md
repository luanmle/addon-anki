# Installer integrity and content hash

- What changed: Direct deck installation now runs the local metadata integrity repair before fetching and applying a deck.
- Why: Installing from `Browse Decks` or `My Subscriptions` should not bypass the same safe local repair used by `Sync Now`.
- Files/modules touched: `anki_concursos/sync/installer.py`, `anki_concursos/tests/test_sync.py`.
- User-visible behavior: If local metadata rows are repaired during direct install, the install success message includes `🧰 Repaired ... local sync metadata rows.`
- Internal behavior: Direct install now persists server `content_hash` values into `remote_cards`.
- Backend API contracts touched: None.
- Storage/config changes: No schema change.

## Before

Direct install fetched manifest/sync data and applied cards without first repairing local metadata, and stored installed card `content_hash` as `None`.

## After

Direct install repairs safe local metadata first and stores the server content hash for installed cards.

## Validation

- Automated checks: focused sync/installer tests and compile checks.
- Manual checks: not run in Anki.
