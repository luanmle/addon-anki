# Duplicate Card ID detection

- What changed: Sync and direct install now detect duplicate local Anki notes with the same remote `Card ID`.
- Why: Duplicate local notes can make sync update only one copy while another stale copy remains visible to the user.
- Files/modules touched: `anki_concursos/services/note_manager.py`, `anki_concursos/sync/engine.py`, `anki_concursos/sync/installer.py`, `anki_concursos/tests/test_sync.py`.
- User-visible behavior: Sync/install success messages include `⚠️ Found duplicate local notes for ... Card ID...` when duplicates are detected.
- Internal behavior: The add-on still updates the first note returned by Anki. It does not delete or suspend duplicate notes automatically.
- Backend API contracts touched: None.
- Storage/config changes: No schema change.

## Before

`find_note_by_card_id()` returned the first matching note and duplicate matches were silent.

## After

The note manager exposes all matching note ids. Sync/install warn when more than one local note has the same `Card ID`.

## Validation

- Automated checks: focused sync/installer tests and compile checks.
- Manual checks: not run in Anki.

## Risks

- Warning only. Users still need a manual cleanup workflow for duplicate notes.
