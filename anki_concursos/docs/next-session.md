# Next session handoff

## Current addon state

Implemented so far:

- Login menu shows active email and lets user logout.
- Browse Decks and My Subscriptions use remote subscription state.
- Sync respects platform subscriptions and removes local tracking for unsubscribed decks.
- Sync/install repair safe local metadata issues before work.
- Sync/install detect duplicate local notes with same `Card ID`.
- Sync/install preserve `protected_fields`.
- Deck version/history UI exists in addon, with remote release history when backend supports it.
- Addon UI visible strings were standardized to PT-BR.
- Editor has `Sugerir alteração` button for notes installed/tracked by the platform.
- Suggestion dialog sends `POST /addon/cards/{card_id}/suggestions`.
- Suggestion dialog supports selecting fields to submit.
- Suggestion dialog shows textual `Antes/Depois` preview using local `remote_fields`.

## Test focus now

Manual Anki smoke test:

1. Login.
2. Install or sync a subscribed deck.
3. Open an installed note in the Editor.
4. Confirm `Sugerir alteração` button appears/enables only for tracked notes.
5. Edit a field.
6. Click `Sugerir alteração`.
7. Select/deselect fields.
8. Confirm preview updates.
9. Send with empty comment: must block.
10. Send with comment/source: must create pending suggestion in backend/admin.

Important edge cases:

- Note not installed by platform: button should be disabled or show tracked-note warning.
- Card installed before `remote_fields`: preview may show blank `Antes` until next sync/install.
- Protected local field: sync should not overwrite it; suggestion can still submit selected current field.
- Duplicate `Card ID`: sync/install should warn, not create duplicate notes silently.

## Known limitations

- No new-note suggestion flow yet.
- No tag diff submission yet.
- No list/status of user suggestions inside addon yet.
- No Browser bulk suggestion yet.
- No Reviewer entry point yet.
- Diff preview is text-only, not HTML rich diff.
- Media suggestions remain unsupported because product/backend do not support media yet.
- `pytest` unavailable in current system Python during implementation session.

## Recommended next blocks

1. New note suggestion
   - Add menu/editor flow for note with no local `remote_cards` row.
   - Ask/select destination subscribed deck.
   - Call `create_new_note_suggestion(deck_id, payload)`.

2. My suggestions/status
   - Add API client for user suggestion listing if backend endpoint exists or add endpoint if missing.
   - Add addon dialog listing `pending`, `accepted`, `rejected`, comments.

3. Tag diff
   - Store remote tags locally with card metadata or derive from current sync payload.
   - Send `added_tags` / `removed_tags` in suggestion payload.

4. Browser integration
   - Add Browser context action for selected notes.
   - Start with single-note selection; bulk after contract is clear.

5. Backfill `remote_fields`
   - Optional: command to fetch deck sync/state and populate missing snapshots for old installs.

## Files added recently

- `anki_concursos/gui/editor.py`
- `anki_concursos/gui/suggestion_dialog.py`
- `anki_concursos/services/suggestions.py`
- `anki_concursos/tests/test_suggestions.py`
- `anki_concursos/docs/changes/2026-06-27-editor-note-suggestions.md`
- `anki_concursos/docs/changes/2026-06-27-note-suggestion-diff-preview.md`

## Verification already run

- `python3 -m compileall` on changed addon files: passed.
- Pure smoke checks for suggestion helpers: passed.
- SQLite storage smoke with `aqt` stub: passed.
- `python3 -m pytest ...`: not run; `No module named pytest`.
